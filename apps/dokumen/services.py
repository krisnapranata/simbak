"""Logika bisnis dokumen bukti: buat, versi baru, ubah, tautkan EP, hapus lunak, log unduhan."""

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from apps.inti.models import PengaturanSistem
from apps.inti.services import hapus_lunak
from apps.inti.utils import tambah_bulan
from apps.inti.validators import validasi_upload

from .models import BuktiEP, Dokumen, DokumenVersi, LogUnduhan, StatusDokumen
from .permissions import (
    bisa_edit_dokumen,
    bisa_hapus_dokumen,
    bisa_kelola_pokja,
    bisa_lepas_bukti,
    bisa_tautkan_ep,
    bisa_unggah_versi,
)

FIELD_METADATA = [
    "nomor",
    "judul",
    "jenis_dokumen",
    "pokja",
    "unit",
    "penanggung_jawab",
    "tanggal_terbit",
    "tanggal_review_berikutnya",
    "mengandung_data_pasien",
    "keterangan",
]


def validasi_file_bukti(file):
    return validasi_upload(file, ekstensi=settings.UPLOAD_EKSTENSI_BUKTI)


def _isi_tanggal_review(dokumen: Dokumen):
    if dokumen.adalah_regulasi and dokumen.tanggal_terbit and not dokumen.tanggal_review_berikutnya:
        bulan = PengaturanSistem.ambil().periode_review_regulasi_bulan
        dokumen.tanggal_review_berikutnya = tambah_bulan(dokumen.tanggal_terbit, bulan)


def _sha256(file) -> str:
    h = hashlib.sha256()
    file.seek(0)
    for chunk in file.chunks():
        h.update(chunk)
    file.seek(0)
    return h.hexdigest()


def _simpan_versi(dokumen: Dokumen, *, user, file, catatan_perubahan) -> DokumenVersi:
    mime = validasi_file_bukti(file)
    sha = _sha256(file)
    if dokumen.versi_aktif_id and dokumen.versi_aktif.sha256 == sha:
        raise ValidationError("File sama persis dengan versi aktif.")
    terakhir = dokumen.versi.aggregate(n=Max("nomor_versi"))["n"] or 0
    versi = DokumenVersi(
        dokumen=dokumen,
        nomor_versi=terakhir + 1,
        nama_file_asli=Path(file.name).name[:255],
        mime=mime,
        ukuran=file.size,
        sha256=sha,
        catatan_perubahan=catatan_perubahan,
        diunggah_oleh=user,
    )
    versi.file = file
    versi.save()
    dokumen.versi_aktif = versi
    dokumen.save(update_fields=["versi_aktif", "diubah_pada"])
    return versi


@transaction.atomic
def buat_dokumen(
    *, user, data: dict, file, catatan_perubahan="", ep=None, jenis_bukti=None
) -> Dokumen:
    """Buat dokumen draft beserta versi pertama; opsional langsung ditautkan ke satu EP."""
    if not bisa_kelola_pokja(user, data["pokja"].pk):
        raise PermissionDenied
    if ep is not None and jenis_bukti not in ep.jenis_bukti:
        raise ValidationError(f"EP {ep} tidak memerlukan bukti jenis {jenis_bukti}.")
    validasi_file_bukti(file)
    dokumen = Dokumen(**{k: v for k, v in data.items() if k in FIELD_METADATA})
    dokumen.dibuat_oleh = user
    dokumen.status = StatusDokumen.DRAFT
    _isi_tanggal_review(dokumen)
    dokumen.save()
    _simpan_versi(
        dokumen, user=user, file=file, catatan_perubahan=catatan_perubahan or "Versi awal"
    )
    if ep is not None:
        tautkan_ep(dokumen=dokumen, ep=ep, jenis_bukti=jenis_bukti, user=user)
    return dokumen


@transaction.atomic
def ubah_dokumen(*, dokumen: Dokumen, user, data: dict) -> Dokumen:
    from apps.verifikasi.services import kembali_ke_draft

    dokumen = Dokumen.objects.select_for_update().get(pk=dokumen.pk)
    if not bisa_edit_dokumen(user, dokumen):
        raise PermissionDenied
    if "pokja" in data and not bisa_kelola_pokja(user, data["pokja"].pk):
        raise PermissionDenied
    for field, nilai in data.items():
        if field in FIELD_METADATA:
            setattr(dokumen, field, nilai)
    _isi_tanggal_review(dokumen)
    dokumen.save()
    if dokumen.status == StatusDokumen.DIKEMBALIKAN:
        dokumen = kembali_ke_draft(dokumen=dokumen, user=user, catatan="Metadata diperbaiki.")
    return dokumen


@transaction.atomic
def unggah_versi(*, dokumen: Dokumen, user, file, catatan_perubahan) -> DokumenVersi:
    """Versi lama tidak pernah dihapus. Revisi dokumen disetujui/kedaluwarsa → kembali ke draft."""
    from apps.verifikasi.services import kembali_ke_draft, mulai_revisi

    dokumen = Dokumen.objects.select_for_update().get(pk=dokumen.pk)
    if not bisa_unggah_versi(user, dokumen):
        raise PermissionDenied
    versi = _simpan_versi(dokumen, user=user, file=file, catatan_perubahan=catatan_perubahan)
    if dokumen.status == StatusDokumen.DIKEMBALIKAN:
        kembali_ke_draft(dokumen=dokumen, user=user, catatan=f"Versi {versi.nomor_versi} diunggah.")
    elif dokumen.status in (StatusDokumen.DISETUJUI, StatusDokumen.KEDALUWARSA):
        mulai_revisi(dokumen=dokumen, user=user, catatan=f"Revisi: versi {versi.nomor_versi}.")
    return versi


def tautkan_ep(*, dokumen: Dokumen, ep, jenis_bukti, user, keterangan="") -> BuktiEP:
    if not bisa_tautkan_ep(user, dokumen, ep):
        raise PermissionDenied
    if jenis_bukti not in ep.jenis_bukti:
        raise ValidationError(f"EP {ep} tidak memerlukan bukti jenis {jenis_bukti}.")
    bukti, dibuat = BuktiEP.objects.get_or_create(
        dokumen=dokumen,
        elemen_penilaian=ep,
        jenis_bukti=jenis_bukti,
        defaults={"keterangan": keterangan, "dibuat_oleh": user},
    )
    if not dibuat:
        raise ValidationError("Dokumen sudah ditautkan ke EP ini dengan jenis bukti yang sama.")
    return bukti


def lepas_bukti(*, bukti: BuktiEP, user):
    if not bisa_lepas_bukti(user, bukti):
        raise PermissionDenied
    bukti.delete()


def hapus_dokumen(*, dokumen: Dokumen, user) -> Dokumen:
    """Hapus lunak; file dan versi tetap tersimpan."""
    if not bisa_hapus_dokumen(user, dokumen):
        raise PermissionDenied
    return hapus_lunak(obj=dokumen)


def catat_unduhan(*, versi: DokumenVersi, user, ip=None, keterangan="") -> LogUnduhan | None:
    """Unduhan dokumen berisi data pasien selalu dicatat."""
    if not versi.dokumen.mengandung_data_pasien:
        return None
    return LogUnduhan.objects.create(versi=versi, user=user, ip=ip, keterangan=keterangan)
