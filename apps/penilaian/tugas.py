"""'Tugas Saya': daftar pekerjaan yang menunggu user, disusun dari peran dan pokjanya."""

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from apps.akun.models import User
from apps.akun.peran import Peran
from apps.akun.permissions import (
    adalah_komite_atau_admin,
    adalah_peran_pokja,
    id_pokja_user,
    punya_peran,
)
from apps.dokumen.models import Dokumen, StatusDokumen
from apps.pps.models import RencanaPerbaikan
from apps.standar.models import Bab, ElemenPenilaian
from apps.verifikasi.permissions import queryset_antrian_untuk

from .capaian import ep_aktif, kekurangan_bukti
from .models import KriteriaPredikat, PeriodeAkreditasi, TargetPokja
from .permissions import queryset_target_untuk
from .target import evaluasi as evaluasi_target


@dataclass
class Tugas:
    judul: str
    jumlah: int
    url: str
    keterangan: str = ""
    penting: bool = False


def tugas_untuk(user, periode) -> list[Tugas]:
    hasil: list[Tugas] = []

    def tambah(judul, jumlah, url, keterangan="", penting=False):
        if jumlah:
            hasil.append(Tugas(judul, jumlah, url, keterangan, penting))

    url_dokumen = reverse("dokumen:list")

    # Verifikator: komite, direktur, admin
    if adalah_komite_atau_admin(user) or punya_peran(user, Peran.DIREKTUR):
        n = (
            queryset_antrian_untuk(user)
            .exclude(status__in=[StatusDokumen.DRAFT, StatusDokumen.DIKEMBALIKAN])
            .count()
        )
        tambah(
            "Dokumen menunggu verifikasi/persetujuan Anda",
            n,
            reverse("verifikasi:antrian"),
            "Periksa isi dokumen, lalu verifikasi, setujui, atau kembalikan dengan catatan.",
            penting=True,
        )

    # Target pokja yang tertinggal dari jadwal
    if periode is not None:
        tertinggal = [
            h
            for h in evaluasi_target(queryset_target_untuk(user).filter(periode=periode))
            if h.tertinggal
        ]
        terlambat = sum(1 for h in tertinggal if h.status == TargetPokja.Status.TERLAMBAT)
        pokja_sendiri = adalah_peran_pokja(user) and not (
            adalah_komite_atau_admin(user) or punya_peran(user, Peran.DIREKTUR)
        )
        tambah(
            "Target pokja Anda tertinggal dari jadwal"
            if pokja_sendiri
            else "Target pokja tertinggal",
            len(tertinggal),
            f"{reverse('penilaian:target_list')}?periode={periode.pk}",
            (f"{terlambat} sudah lewat tenggat. " if terlambat else "")
            + "Lihat target, capaian sekarang, dan capaian yang seharusnya.",
            penting=True,
        )

    # Pokja
    if adalah_peran_pokja(user):
        pokja = id_pokja_user(user)
        dok = Dokumen.objects.filter(pokja__in=pokja)
        tambah(
            "Dokumen dikembalikan, perlu diperbaiki",
            dok.filter(status=StatusDokumen.DIKEMBALIKAN).count(),
            f"{url_dokumen}?status={StatusDokumen.DIKEMBALIKAN}",
            "Baca catatan verifikator di halaman dokumen, perbaiki, lalu ajukan ulang.",
            penting=True,
        )
        tambah(
            "Dokumen kedaluwarsa, perlu direview",
            dok.filter(status=StatusDokumen.KEDALUWARSA).count(),
            f"{url_dokumen}?status={StatusDokumen.KEDALUWARSA}",
            "Unggah versi terbaru setelah direview; dokumen akan diverifikasi ulang.",
            penting=True,
        )
        if punya_peran(user, Peran.KETUA_POKJA):
            tambah(
                "Draft dokumen siap diajukan",
                dok.filter(status=StatusDokumen.DRAFT, versi_aktif__isnull=False).count(),
                f"{url_dokumen}?status={StatusDokumen.DRAFT}",
                "Periksa draft dari anggota pokja, lalu klik 'Ajukan verifikasi'.",
            )
        bab_ids = list(Bab.objects.filter(pokja__in=pokja).values_list("id", flat=True))
        ep_qs = ep_aktif(bab_ids)
        kurang = kekurangan_bukti(ep_qs)
        tambah(
            "EP pokja Anda yang buktinya belum lengkap",
            len(kurang),
            reverse("penilaian:kekurangan"),
            "Unggah bukti yang kurang, atau ajukan dokumen yang masih draft.",
        )
        if punya_peran(user, Peran.KETUA_POKJA) and periode is not None and not periode.terkunci:
            tambah(
                "EP belum dinilai pada periode ini",
                ep_qs.exclude(penilaian__periode=periode).count(),
                reverse("penilaian:bab_list"),
                "Isi skor penilaian mandiri (10/5/0/TDD) beserta fakta dan analisis.",
            )

    # Penanggung jawab PPS
    pps = RencanaPerbaikan.objects.filter(pj=user).exclude(status=RencanaPerbaikan.Status.SELESAI)
    terlambat = pps.filter(tenggat__lt=timezone.localdate()).count()
    tambah(
        "Rencana perbaikan (PPS) yang Anda pegang",
        pps.count(),
        f"{reverse('pps:list')}?pj=saya",
        f"{terlambat} sudah lewat tenggat." if terlambat else "Perbarui status dan progresnya.",
        penting=bool(terlambat),
    )
    return hasil


@dataclass
class Langkah:
    judul: str
    selesai: bool
    url: str
    keterangan: str


def langkah_persiapan(user) -> list[Langkah]:
    """Checklist penyiapan sistem untuk komite/admin. Kosong bila user bukan pengelola."""
    if not adalah_komite_atau_admin(user):
        return []
    admin = user.is_staff

    def url_admin(nama):
        return reverse(nama) if admin else ""

    bab_tanpa_pokja = Bab.objects.filter(pokja__isnull=True).count()
    return [
        Langkah(
            "Impor master standar dan EP",
            ElemenPenilaian.objects.exists(),
            reverse("standar:impor"),
            "Unduh template Excel, isi dari dokumen resmi STARKES, lalu impor.",
        ),
        Langkah(
            "Tetapkan pokja untuk setiap bab",
            bab_tanpa_pokja == 0,
            url_admin("admin:standar_bab_changelist"),
            f"{bab_tanpa_pokja} bab belum punya pokja."
            if bab_tanpa_pokja
            else "Semua bab punya pokja.",
        ),
        Langkah(
            "Masukkan pengguna ke grup peran dan pokjanya",
            User.objects.filter(pokja__isnull=False).exists(),
            url_admin("admin:akun_user_changelist"),
            "Ketua/anggota pokja hanya melihat bab pokjanya.",
        ),
        Langkah(
            "Buat dan aktifkan periode akreditasi",
            PeriodeAkreditasi.objects.filter(aktif=True).exists(),
            reverse("penilaian:periode_list"),
            "Penilaian mandiri dan dashboard dihitung per periode aktif.",
        ),
        Langkah(
            "Isi kriteria predikat kelulusan",
            KriteriaPredikat.objects.exists(),
            url_admin("admin:penilaian_kriteriapredikat_changelist"),
            "Sesuai aturan lembaga akreditasi; dipakai untuk perkiraan predikat di dashboard.",
        ),
    ]
