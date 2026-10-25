import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.akun.models import Unit
from apps.inti.services import hapus_lunak, pulihkan
from apps.inti.validators import validasi_upload

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.mark.django_db
def test_soft_delete_disaring_manager_default():
    unit = Unit.objects.create(kode="U1", nama="Unit Contoh")
    hapus_lunak(obj=unit)
    assert not Unit.objects.filter(pk=unit.pk).exists()
    assert Unit.semua.filter(pk=unit.pk).exists()
    pulihkan(obj=unit)
    assert Unit.objects.filter(pk=unit.pk).exists()


def test_storage_privat_tanpa_url():
    with pytest.raises(NotImplementedError):
        storages["privat"].url("apa.pdf")


def test_validasi_upload_menerima_file_sesuai():
    f = SimpleUploadedFile("a.pdf", PDF)
    assert validasi_upload(f, ekstensi={"pdf": {"application/pdf"}}) == "application/pdf"


def test_validasi_upload_menolak_ekstensi():
    with pytest.raises(ValidationError):
        validasi_upload(SimpleUploadedFile("a.exe", b"MZ"), ekstensi={"pdf": {"application/pdf"}})


def test_validasi_upload_menolak_mime_palsu():
    f = SimpleUploadedFile("a.pdf", b"bukan pdf, hanya teks biasa")
    with pytest.raises(ValidationError, match="tidak sesuai"):
        validasi_upload(f, ekstensi={"pdf": {"application/pdf"}})


def test_validasi_upload_menolak_ukuran():
    f = SimpleUploadedFile("a.pdf", PDF + b" " * (1024 * 1024))
    with pytest.raises(ValidationError, match="Ukuran"):
        validasi_upload(f, ekstensi={"pdf": {"application/pdf"}}, maks_mb=1)


@pytest.mark.django_db
def test_healthcheck_tanpa_login(client):
    resp = client.get("/sehat/")
    assert resp.status_code == 200 and resp.content == b"ok"
