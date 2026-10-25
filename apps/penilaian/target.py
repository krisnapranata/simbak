"""Target bertahap per pokja: evaluasi status terhadap jadwal, CRUD, dan notifikasi.

Status sebuah target pada hari H:
- Tercapai     : capaian aktual ≥ nilai target (kapan pun).
- Terlambat    : H > tenggat dan belum tercapai.
- Sesuai jadwal: aktual ≥ harapan(H), yaitu target × (hari berjalan / total hari)
                 dari tanggal mulai sampai tenggat (kemajuan linier).
- Berisiko     : aktual < harapan(H).
"""

import datetime
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.akun.models import User
from apps.akun.peran import Peran
from apps.inti.services import hapus_lunak
from apps.standar.models import Bab
from apps.verifikasi.services import kirim_notifikasi

from .capaian import Capaian, capaian_per_bab, capaian_per_pokja
from .models import TargetPokja
from .permissions import bisa_kelola_target

S = TargetPokja.Status
U = TargetPokja.Ukuran

WARNA_STATUS = {
    S.TERCAPAI: "bg-success-subtle text-success-emphasis",
    S.SESUAI: "bg-primary-subtle text-primary-emphasis",
    S.BERISIKO: "bg-warning-subtle text-warning-emphasis",
    S.TERLAMBAT: "bg-danger-subtle text-danger-emphasis",
}
URUTAN_STATUS = [S.TERLAMBAT, S.BERISIKO, S.SESUAI, S.TERCAPAI]


@dataclass
class HasilTarget:
    target: TargetPokja
    aktual: float
    harapan: float
    status: str
    sisa_hari: int

    @property
    def label_status(self) -> str:
        return S(self.status).label

    @property
    def warna(self) -> str:
        return WARNA_STATUS[self.status]

    @property
    def nilai_target(self) -> float:
        return float(self.target.nilai_target)

    @property
    def hari_lewat(self) -> int:
        return max(-self.sisa_hari, 0)

    @property
    def tertinggal(self) -> bool:
        return self.status in (S.BERISIKO, S.TERLAMBAT)


def nilai_aktual(cap: Capaian, ukuran) -> float:
    if ukuran == U.KELENGKAPAN_BUKTI:
        return cap.persen_lengkap
    if ukuran == U.PROGRES_PENILAIAN:
        return cap.persen_dinilai
    return cap.persen or 0.0


def harapan_pada(target: TargetPokja, hari_ini: datetime.date) -> float:
    """Capaian yang seharusnya sudah diraih hari ini bila kemajuan linier."""
    nilai = float(target.nilai_target)
    total = (target.tenggat - target.mulai).days
    if total <= 0:
        return nilai
    jalan = min(max((hari_ini - target.mulai).days, 0), total)
    return round(nilai * jalan / total, 1)


def tentukan_status(*, nilai_target, aktual, harapan, hari_ini, tenggat) -> str:
    if aktual >= float(nilai_target):
        return S.TERCAPAI
    if hari_ini > tenggat:
        return S.TERLAMBAT
    if aktual >= harapan:
        return S.SESUAI
    return S.BERISIKO


def evaluasi(target_qs, *, hari_ini=None) -> list[HasilTarget]:
    """Evaluasi semua target dalam queryset. Capaian dihitung sekali per periode."""
    hari_ini = hari_ini or timezone.localdate()
    daftar = list(target_qs.select_related("pokja", "periode"))
    per_periode: dict[int, dict[int, Capaian]] = {}
    for periode_id in {t.periode_id for t in daftar}:
        targets = [t for t in daftar if t.periode_id == periode_id]
        pokja_ids = {t.pokja_id for t in targets}
        baris = capaian_per_bab(
            periode=targets[0].periode, bab_qs=Bab.objects.filter(pokja_id__in=pokja_ids)
        )
        per_periode[periode_id] = {p.pk: c for p, c in capaian_per_pokja(baris) if p is not None}

    hasil = []
    for t in daftar:
        cap = per_periode[t.periode_id].get(t.pokja_id, Capaian())
        aktual = nilai_aktual(cap, t.ukuran)
        harapan = harapan_pada(t, hari_ini)
        hasil.append(
            HasilTarget(
                target=t,
                aktual=aktual,
                harapan=harapan,
                status=tentukan_status(
                    nilai_target=t.nilai_target,
                    aktual=aktual,
                    harapan=harapan,
                    hari_ini=hari_ini,
                    tenggat=t.tenggat,
                ),
                sisa_hari=(t.tenggat - hari_ini).days,
            )
        )
    hasil.sort(key=lambda h: (URUTAN_STATUS.index(h.status), h.target.tenggat))
    return hasil


def ringkas(hasil: list[HasilTarget]) -> list[tuple[str, str, str, int]]:
    """[(kode, label, warna, jumlah)] per status, urut dari yang paling perlu perhatian."""
    return [
        (s.value, s.label, WARNA_STATUS[s], sum(1 for h in hasil if h.status == s))
        for s in URUTAN_STATUS
    ]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@transaction.atomic
def buat_target_banyak(
    *,
    user,
    periode,
    daftar_pokja,
    ukuran,
    nilai_target,
    tenggat,
    tanggal_mulai=None,
    keterangan="",
) -> tuple[int, int]:
    """Buat target yang sama untuk beberapa pokja sekaligus. Mengembalikan (dibuat, diperbarui).

    Target dengan kunci sama (periode, pokja, ukuran, tenggat) diperbarui nilainya,
    termasuk yang pernah dihapus (dipulihkan).
    """
    if not bisa_kelola_target(user):
        raise PermissionDenied
    dibuat = diperbarui = 0
    for pokja in daftar_pokja:
        target = TargetPokja.semua.filter(
            periode=periode, pokja=pokja, ukuran=ukuran, tenggat=tenggat
        ).first()
        if target is None:
            TargetPokja.objects.create(
                periode=periode,
                pokja=pokja,
                ukuran=ukuran,
                nilai_target=nilai_target,
                tenggat=tenggat,
                tanggal_mulai=tanggal_mulai,
                keterangan=keterangan,
                dibuat_oleh=user,
            )
            dibuat += 1
        else:
            target.nilai_target = nilai_target
            target.tanggal_mulai = tanggal_mulai
            target.keterangan = keterangan
            target.dihapus_pada = None
            target.status_dinotifikasi = ""
            target.save()
            diperbarui += 1
    return dibuat, diperbarui


def simpan_target(*, user, target: TargetPokja) -> TargetPokja:
    if not bisa_kelola_target(user):
        raise PermissionDenied
    target.status_dinotifikasi = ""  # evaluasi ulang notifikasi setelah target diubah
    target.save()
    return target


def hapus_target(*, user, target: TargetPokja) -> TargetPokja:
    if not bisa_kelola_target(user):
        raise PermissionDenied
    return hapus_lunak(obj=target)


# ---------------------------------------------------------------------------
# Notifikasi (dipanggil harian oleh `manage.py kirim_pengingat`)
# ---------------------------------------------------------------------------


def _penerima(target: TargetPokja, status: str):
    penerima = list(
        User.objects.filter(
            pokja=target.pokja_id,
            groups__name__in=[Peran.KETUA_POKJA, Peran.ANGGOTA_POKJA],
            is_active=True,
        )
    )
    if status == S.TERLAMBAT:
        penerima += list(User.objects.filter(groups__name=Peran.KOMITE_MUTU, is_active=True))
    return penerima


def kirim_notifikasi_target(*, hari_ini: datetime.date) -> list[HasilTarget]:
    """Beri tahu pokja (dan komite bila terlambat) HANYA saat status berubah menjadi
    berisiko/terlambat, supaya tidak mengirim pesan yang sama setiap hari."""
    qs = TargetPokja.objects.filter(periode__aktif=True)
    terkirim = []
    url = reverse("penilaian:target_list")
    for h in evaluasi(qs, hari_ini=hari_ini):
        t = h.target
        if h.status == t.status_dinotifikasi:
            continue
        if h.tertinggal:
            judul = (
                f"Target {t.pokja.kode} {h.label_status.lower()}: {t.get_ukuran_display()} "
                f"{h.aktual:.0f}% dari target {h.nilai_target:.0f}% (tenggat {t.tenggat:%d-%m-%Y})"
            )
            kirim_notifikasi(penerima=_penerima(t, h.status), judul=judul, url=url)
            terkirim.append(h)
        t.status_dinotifikasi = h.status
        t.save(update_fields=["status_dinotifikasi", "diubah_pada"])
    return terkirim
