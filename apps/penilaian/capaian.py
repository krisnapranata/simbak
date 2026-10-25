"""Perhitungan capaian penilaian dan kelengkapan bukti (read-only, untuk dashboard & survei).

capaian (%) = Σ skor EP dinilai / (jumlah EP dinilai dan bukan TDD × 10) × 100
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.dokumen.models import BuktiEP, StatusDokumen
from apps.inti.models import PengaturanSistem
from apps.inti.utils import tambah_bulan
from apps.standar.models import ElemenPenilaian, JenisBukti

from .models import KriteriaPredikat, PenilaianEP


@dataclass
class Capaian:
    jumlah_ep: int = 0
    dinilai: int = 0
    tdd: int = 0
    total_skor: int = 0
    ep_lengkap: int = 0

    @property
    def pembagi(self) -> int:
        return (self.dinilai - self.tdd) * 10

    @property
    def persen(self) -> float | None:
        """None bila belum ada EP yang dinilai (selain TDD)."""
        return round(self.total_skor / self.pembagi * 100, 1) if self.pembagi else None

    @property
    def persen_dinilai(self) -> float:
        return round(self.dinilai / self.jumlah_ep * 100, 1) if self.jumlah_ep else 0.0

    @property
    def persen_lengkap(self) -> float:
        return round(self.ep_lengkap / self.jumlah_ep * 100, 1) if self.jumlah_ep else 0.0

    def __add__(self, other: "Capaian") -> "Capaian":
        return Capaian(
            self.jumlah_ep + other.jumlah_ep,
            self.dinilai + other.dinilai,
            self.tdd + other.tdd,
            self.total_skor + other.total_skor,
            self.ep_lengkap + other.ep_lengkap,
        )


def ep_aktif(bab_ids):
    return ElemenPenilaian.objects.filter(
        standar__bab_id__in=bab_ids, standar__dihapus_pada__isnull=True
    )


STATUS_DALAM_PROSES = (
    StatusDokumen.DRAFT,
    StatusDokumen.DIAJUKAN,
    StatusDokumen.DIVERIFIKASI_KOMITE,
    StatusDokumen.DIKEMBALIKAN,
)


def _peta_bukti(ep_qs, **filter_dokumen) -> dict[int, set[str]]:
    baris = (
        BuktiEP.objects.filter(
            elemen_penilaian__in=ep_qs, dokumen__dihapus_pada__isnull=True, **filter_dokumen
        )
        .values_list("elemen_penilaian_id", "jenis_bukti")
        .distinct()
    )
    hasil = defaultdict(set)
    for ep_id, jenis in baris:
        hasil[ep_id].add(jenis)
    return hasil


def bukti_disetujui(ep_qs) -> dict[int, set[str]]:
    """EP → himpunan jenis bukti yang punya minimal satu dokumen disetujui."""
    return _peta_bukti(ep_qs, dokumen__status=StatusDokumen.DISETUJUI)


def bukti_dalam_proses(ep_qs) -> dict[int, set[str]]:
    """EP → jenis bukti yang dokumennya sedang draft/diajukan/diverifikasi/dikembalikan."""
    return _peta_bukti(ep_qs, dokumen__status__in=STATUS_DALAM_PROSES)


@dataclass
class KekuranganEP:
    ep: ElemenPenilaian
    kurang: list[str]  # jenis wajib yang belum punya bukti disetujui
    proses: list[str]  # bagian dari `kurang` yang sudah ada dokumennya, tinggal diverifikasi

    @property
    def belum_ada(self) -> list[str]:
        return [j for j in self.kurang if j not in self.proses]


def kekurangan_bukti(ep_qs) -> list[KekuranganEP]:
    """EP yang belum lengkap bukti disetujuinya, urut bab → standar → EP (3 query)."""
    disetujui, proses = bukti_disetujui(ep_qs), bukti_dalam_proses(ep_qs)
    hasil = []
    daftar = ep_qs.select_related("standar__bab__pokja").order_by(
        "standar__bab__kelompok__urutan",
        "standar__bab__urutan",
        "standar__urutan",
        "standar__kode",
        "urutan",
        "kode",
    )
    for ep in daftar:
        ok = disetujui.get(ep.pk, set())
        kurang = [j for j in ep.jenis_bukti if j not in ok]
        if kurang:
            jalan = proses.get(ep.pk, set())
            hasil.append(KekuranganEP(ep, kurang, [j for j in kurang if j in jalan]))
    return hasil


def ep_lengkap_bukti(ep_qs) -> set[int]:
    """EP lengkap bila setiap jenis bukti yang diwajibkan punya ≥1 bukti disetujui.
    jenis_bukti berupa JSON list sehingga perbandingan himpunan dilakukan di Python (2 query)."""
    tercakup = bukti_disetujui(ep_qs)
    return {
        ep_id
        for ep_id, wajib in ep_qs.values_list("id", "jenis_bukti")
        if set(wajib) <= tercakup.get(ep_id, set())
    }


def capaian_per_bab(*, periode, bab_qs) -> list[tuple]:
    """[(bab, Capaian)] untuk bab dalam queryset (sudah disaring hak akses oleh pemanggil)."""
    daftar_bab = list(bab_qs.select_related("kelompok", "pokja"))
    hasil = {b.pk: Capaian() for b in daftar_bab}
    ep_qs = ep_aktif(hasil.keys())

    for row in ep_qs.values("standar__bab_id").annotate(n=Count("id")):
        hasil[row["standar__bab_id"]].jumlah_ep = row["n"]

    if periode is not None:
        agregat = (
            PenilaianEP.objects.filter(periode=periode, elemen_penilaian__in=ep_qs)
            .values("elemen_penilaian__standar__bab_id")
            .annotate(
                n_dinilai=Count("id"),
                n_tdd=Count("id", filter=Q(tdd=True)),
                n_skor=Coalesce(Sum("skor", filter=Q(tdd=False)), 0),
            )
        )
        for row in agregat:
            c = hasil[row["elemen_penilaian__standar__bab_id"]]
            c.dinilai, c.tdd, c.total_skor = row["n_dinilai"], row["n_tdd"], row["n_skor"]

    lengkap = ep_lengkap_bukti(ep_qs)
    if lengkap:
        for row in ep_qs.filter(id__in=lengkap).values("standar__bab_id").annotate(n=Count("id")):
            hasil[row["standar__bab_id"]].ep_lengkap = row["n"]

    return [(b, hasil[b.pk]) for b in daftar_bab]


def capaian_per_pokja(baris_bab) -> list[tuple]:
    """Agregasi pembilang/penyebut per pokja (bukan rata-rata persentase)."""
    per_pokja: dict = {}
    for bab, cap in baris_bab:
        kunci = bab.pokja
        per_pokja[kunci] = per_pokja.get(kunci, Capaian()) + cap
    return sorted(per_pokja.items(), key=lambda x: (x[0] is None, x[0].kode if x[0] else ""))


def total(baris_bab) -> Capaian:
    return sum((cap for _, cap in baris_bab), Capaian())


def evaluasi_predikat(baris_bab):
    """(predikat | None, sudah_diatur). Bab tanpa penilaian dianggap 0%."""
    kriteria = list(KriteriaPredikat.objects.prefetch_related("syarat__bab_wajib"))
    if not kriteria:
        return None, False
    persen = {bab.pk: (cap.persen or 0) for bab, cap in baris_bab}
    for k in kriteria:
        syarat = list(k.syarat.all())
        if syarat and all(_syarat_terpenuhi(s, persen) for s in syarat):
            return k, True
    return None, True


def _syarat_terpenuhi(syarat, persen: dict[int, float]) -> bool:
    memenuhi = {pk for pk, p in persen.items() if p >= float(syarat.min_capaian)}
    perlu = syarat.min_jumlah_bab or len(persen)
    wajib = {b.pk for b in syarat.bab_wajib.all()}
    return len(memenuhi) >= perlu and wajib <= memenuhi


def ep_tanpa_bukti(ep_qs):
    ada_bukti = BuktiEP.objects.filter(
        elemen_penilaian=OuterRef("pk"), dokumen__dihapus_pada__isnull=True
    )
    return ep_qs.filter(~Exists(ada_bukti))


def dokumen_jatuh_tempo(dokumen_qs, *, hari_ini=None, maks_hari=90):
    """Dokumen disetujui yang direview dalam `maks_hari` ke depan (+ atribut `sisa_hari`)."""
    hari_ini = hari_ini or timezone.localdate()
    qs = dokumen_qs.filter(
        status=StatusDokumen.DISETUJUI,
        tanggal_review_berikutnya__gte=hari_ini,
        tanggal_review_berikutnya__lte=hari_ini + datetime.timedelta(days=maks_hari),
    ).order_by("tanggal_review_berikutnya")
    hasil = list(qs.select_related("pokja"))
    for d in hasil:
        d.sisa_hari = (d.tanggal_review_berikutnya - hari_ini).days
    return hasil


def bukti_pelaksanaan_usang(dokumen_qs, *, periode):
    """Dokumen yang ditautkan sebagai bukti D tetapi terbit lebih lama dari batas usia
    terhadap tanggal survei periode aktif."""
    if periode is None or periode.tanggal_survei is None:
        return dokumen_qs.none()
    bulan = PengaturanSistem.ambil().batas_usia_bukti_bulan
    batas = tambah_bulan(periode.tanggal_survei, -bulan)
    return (
        dokumen_qs.filter(
            bukti__jenis_bukti=JenisBukti.DOKUMEN,
            tanggal_terbit__lt=batas,
        )
        .exclude(status__in=[StatusDokumen.DICABUT])
        .distinct()
    )
