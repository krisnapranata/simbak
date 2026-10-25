import zipfile
from pathlib import Path

import magic
from django.conf import settings
from django.core.exceptions import ValidationError


def validasi_upload(file, *, ekstensi: dict[str, set[str]], maks_mb: int | None = None):
    """Validasi ekstensi, MIME asli (python-magic), dan ukuran file upload.

    `ekstensi` memetakan ekstensi (tanpa titik, huruf kecil) ke himpunan MIME yang diterima.
    """
    maks_mb = maks_mb or settings.UPLOAD_MAKS_MB
    ext = Path(file.name).suffix.lower().lstrip(".")
    if ext not in ekstensi:
        daftar = ", ".join(sorted(ekstensi))
        raise ValidationError(f"Ekstensi .{ext} tidak diizinkan. Hanya: {daftar}.")
    if file.size > maks_mb * 1024 * 1024:
        raise ValidationError(f"Ukuran file melebihi batas {maks_mb} MB.")

    posisi = file.tell()
    file.seek(0)
    mime = magic.from_buffer(file.read(4096), mime=True)
    file.seek(posisi)
    if mime not in ekstensi[ext]:
        raise ValidationError("Isi file tidak sesuai dengan ekstensinya.")
    if ext in EKSTENSI_OOXML:
        _tolak_makro_ooxml(file)
    return mime


EKSTENSI_OOXML = {"docx", "xlsx", "pptx"}


def _tolak_makro_ooxml(file):
    """Tolak dokumen Office yang menyimpan makro (vbaProject.bin) meski berekstensi docx/xlsx."""
    posisi = file.tell()
    file.seek(0)
    try:
        with zipfile.ZipFile(file) as arsip:
            nama = arsip.namelist()
    except zipfile.BadZipFile as e:
        raise ValidationError("File Office rusak atau tidak valid.") from e
    finally:
        file.seek(posisi)
    if any(n.lower().endswith("vbaproject.bin") for n in nama):
        raise ValidationError("File berisi makro tidak diizinkan.")
