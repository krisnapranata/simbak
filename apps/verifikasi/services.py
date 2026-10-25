"""Satu-satunya tempat transisi status dokumen. Setiap transisi membuat LogVerifikasi.

draft → diajukan → diverifikasi_komite → disetujui → (kedaluwarsa | dicabut)
           ↘ dikembalikan (dengan catatan) → draft
"""

import datetime

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mass_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.akun.models import User
from apps.akun.peran import Peran
from apps.dokumen.models import Dokumen, StatusDokumen
from apps.inti.models import PengaturanSistem

from . import permissions as izin
from .models import LogVerifikasi, Notifikasi, PengingatTerkirim

S = StatusDokumen


class TransisiTidakValid(Exception):
    pass


ATURAN = {
    "ajukan": ({S.DRAFT}, S.DIAJUKAN, izin.bisa_ajukan),
    "verifikasi": ({S.DIAJUKAN}, S.DIVERIFIKASI_KOMITE, izin.bisa_verifikasi),
    "setujui": ({S.DIVERIFIKASI_KOMITE}, S.DISETUJUI, izin.bisa_setujui),
    "kembalikan": ({S.DIAJUKAN, S.DIVERIFIKASI_KOMITE}, S.DIKEMBALIKAN, izin.bisa_kembalikan),
    "kembali_ke_draft": ({S.DIKEMBALIKAN}, S.DRAFT, izin.bisa_kembali_ke_draft),
    "mulai_revisi": ({S.DISETUJUI, S.KEDALUWARSA}, S.DRAFT, izin.bisa_mulai_revisi),
    "tandai_kedaluwarsa": ({S.DISETUJUI}, S.KEDALUWARSA, None),
    "cabut": ({S.DISETUJUI, S.KEDALUWARSA}, S.DICABUT, izin.bisa_cabut),
}

# Aksi yang ditampilkan sebagai tombol di halaman dokumen (urutan tampilan).
AKSI_UI = {
    "ajukan": "Ajukan verifikasi",
    "verifikasi": "Verifikasi (komite)",
    "setujui": "Setujui",
    "kembalikan": "Kembalikan",
    "cabut": "Cabut",
}
AKSI_WAJIB_CATATAN = {"kembalikan", "cabut"}


def aksi_tersedia(user, dokumen) -> list[tuple[str, str]]:
    hasil = []
    for aksi, label in AKSI_UI.items():
        asal, _, cek = ATURAN[aksi]
        if dokumen.status in asal and cek(user, dokumen):
            hasil.append((aksi, label))
    return hasil


def _transisi(*, dokumen, user, aksi, catatan="") -> Dokumen:
    asal, tujuan, cek = ATURAN[aksi]
    dok = Dokumen.objects.select_for_update().select_related("versi_aktif").get(pk=dokumen.pk)
    if cek is not None and (user is None or not cek(user, dok)):
        raise PermissionDenied
    if dok.status not in asal:
        raise TransisiTidakValid(
            f"Aksi '{aksi}' tidak dapat dilakukan pada dokumen berstatus "
            f"{dok.get_status_display()}."
        )
    if aksi in AKSI_WAJIB_CATATAN and not catatan.strip():
        raise TransisiTidakValid("Catatan wajib diisi.")
    dari = dok.status
    dok.status = tujuan
    dok.save(update_fields=["status", "diubah_pada"])
    LogVerifikasi.objects.create(
        dokumen=dok, dari_status=dari, ke_status=tujuan, user=user, catatan=catatan.strip()
    )
    return dok


# ---------------------------------------------------------------------------
# Notifikasi
# ---------------------------------------------------------------------------


def _url_dokumen(dokumen) -> str:
    return reverse("dokumen:detail", args=[dokumen.pk])


def pengguna_peran(*peran):
    return User.objects.filter(groups__name__in=peran, is_active=True)


def pengelola_pokja(dokumen):
    """Ketua pokja dokumen + pembuat + penanggung jawab."""
    ketua = User.objects.filter(
        groups__name=Peran.KETUA_POKJA, pokja=dokumen.pokja_id, is_active=True
    )
    lain = User.objects.filter(
        pk__in=[dokumen.dibuat_oleh_id, dokumen.penanggung_jawab_id], is_active=True
    )
    return ketua | lain


def kirim_notifikasi(*, penerima, judul: str, url: str = "", kecuali=None, email=True):
    """Buat notifikasi in-app dan kirim email (judul + tautan) setelah transaksi selesai."""
    penerima = [u for u in {u.pk: u for u in penerima}.values() if u != kecuali]
    if not penerima:
        return []
    notif = Notifikasi.objects.bulk_create(
        [Notifikasi(penerima=u, judul=judul[:255], url=url) for u in penerima]
    )
    if email:
        alamat = [u.email for u in penerima if u.email]
        if alamat:
            pesan = f"{judul}\n\nBuka di SIMBAK: {settings.URL_DASAR}{url}\n"
            surat = [(f"[SIMBAK] {judul}", pesan, settings.DEFAULT_FROM_EMAIL, [a]) for a in alamat]
            transaction.on_commit(lambda: send_mass_mail(surat, fail_silently=True))
    return notif


# ---------------------------------------------------------------------------
# Transisi
# ---------------------------------------------------------------------------


@transaction.atomic
def ajukan(*, dokumen, user, catatan="") -> Dokumen:
    if not dokumen.versi_aktif_id:
        raise TransisiTidakValid("Dokumen belum memiliki file.")
    dok = _transisi(dokumen=dokumen, user=user, aksi="ajukan", catatan=catatan)
    kirim_notifikasi(
        penerima=pengguna_peran(Peran.KOMITE_MUTU),
        judul=f"Dokumen diajukan untuk verifikasi: {dok.judul}",
        url=_url_dokumen(dok),
        kecuali=user,
    )
    return dok


@transaction.atomic
def verifikasi(*, dokumen, user, catatan="") -> Dokumen:
    dok = _transisi(dokumen=dokumen, user=user, aksi="verifikasi", catatan=catatan)
    penerima = (
        pengguna_peran(Peran.DIREKTUR) if dok.adalah_regulasi else pengguna_peran(Peran.KOMITE_MUTU)
    )
    kirim_notifikasi(
        penerima=penerima,
        judul=f"Dokumen menunggu persetujuan: {dok.judul}",
        url=_url_dokumen(dok),
        kecuali=user,
    )
    return dok


@transaction.atomic
def setujui(*, dokumen, user, catatan="") -> Dokumen:
    dok = _transisi(dokumen=dokumen, user=user, aksi="setujui", catatan=catatan)
    kirim_notifikasi(
        penerima=pengelola_pokja(dok),
        judul=f"Dokumen disetujui: {dok.judul}",
        url=_url_dokumen(dok),
        kecuali=user,
    )
    return dok


@transaction.atomic
def kembalikan(*, dokumen, user, catatan) -> Dokumen:
    dok = _transisi(dokumen=dokumen, user=user, aksi="kembalikan", catatan=catatan)
    kirim_notifikasi(
        penerima=pengelola_pokja(dok),
        judul=f"Dokumen dikembalikan untuk diperbaiki: {dok.judul}",
        url=_url_dokumen(dok),
        kecuali=user,
    )
    return dok


@transaction.atomic
def kembali_ke_draft(*, dokumen, user, catatan="") -> Dokumen:
    return _transisi(dokumen=dokumen, user=user, aksi="kembali_ke_draft", catatan=catatan)


@transaction.atomic
def mulai_revisi(*, dokumen, user, catatan="") -> Dokumen:
    return _transisi(dokumen=dokumen, user=user, aksi="mulai_revisi", catatan=catatan)


@transaction.atomic
def cabut(*, dokumen, user, catatan) -> Dokumen:
    dok = _transisi(dokumen=dokumen, user=user, aksi="cabut", catatan=catatan)
    kirim_notifikasi(
        penerima=pengelola_pokja(dok),
        judul=f"Dokumen dicabut: {dok.judul}",
        url=_url_dokumen(dok),
        kecuali=user,
    )
    return dok


@transaction.atomic
def tandai_kedaluwarsa(*, dokumen, catatan="Melewati tanggal review.") -> Dokumen:
    dok = _transisi(dokumen=dokumen, user=None, aksi="tandai_kedaluwarsa", catatan=catatan)
    kirim_notifikasi(
        penerima=pengelola_pokja(dok),
        judul=f"Dokumen kedaluwarsa, perlu direview: {dok.judul}",
        url=_url_dokumen(dok),
    )
    return dok


JALANKAN = {
    "ajukan": ajukan,
    "verifikasi": verifikasi,
    "setujui": setujui,
    "kembalikan": kembalikan,
    "cabut": cabut,
}


# ---------------------------------------------------------------------------
# Notifikasi in-app
# ---------------------------------------------------------------------------


def tandai_dibaca(*, notifikasi: Notifikasi, user) -> Notifikasi:
    if notifikasi.penerima_id != user.pk:
        raise PermissionDenied
    if notifikasi.dibaca_pada is None:
        notifikasi.dibaca_pada = timezone.now()
        notifikasi.save(update_fields=["dibaca_pada"])
    return notifikasi


def tandai_semua_dibaca(*, user) -> int:
    return Notifikasi.objects.filter(penerima=user, dibaca_pada__isnull=True).update(
        dibaca_pada=timezone.now()
    )


# ---------------------------------------------------------------------------
# Pengingat (dijalankan terjadwal lewat `manage.py kirim_pengingat`)
# ---------------------------------------------------------------------------


def proses_kedaluwarsa(*, hari_ini: datetime.date) -> list[Dokumen]:
    dokumen = Dokumen.objects.filter(
        status=S.DISETUJUI, tanggal_review_berikutnya__lt=hari_ini
    ).select_related("pokja")
    return [tandai_kedaluwarsa(dokumen=d) for d in dokumen]


def kirim_pengingat_jatuh_tempo(*, hari_ini: datetime.date) -> list[tuple[Dokumen, int]]:
    """Kirim satu pengingat per ambang (mis. H-90, H-60, H-30) untuk dokumen disetujui."""
    ambang = PengaturanSistem.ambil().daftar_hari_pengingat
    if not ambang:
        return []
    batas = hari_ini + datetime.timedelta(days=max(ambang))
    dokumen = Dokumen.objects.filter(
        status=S.DISETUJUI,
        tanggal_review_berikutnya__gte=hari_ini,
        tanggal_review_berikutnya__lte=batas,
    )
    terkirim = []
    for dok in dokumen:
        sisa = (dok.tanggal_review_berikutnya - hari_ini).days
        a = min(x for x in ambang if x >= sisa)
        with transaction.atomic():
            _, baru = PengingatTerkirim.objects.get_or_create(
                dokumen=dok, ambang_hari=a, tanggal_jatuh_tempo=dok.tanggal_review_berikutnya
            )
            if baru:
                kirim_notifikasi(
                    penerima=pengelola_pokja(dok),
                    judul=f"Dokumen jatuh tempo review dalam {sisa} hari: {dok.judul}",
                    url=_url_dokumen(dok),
                )
                terkirim.append((dok, a))
    return terkirim
