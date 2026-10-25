import pytest
from django.core.management import CommandError, call_command

from apps.akun.models import Pokja, User
from apps.akun.peran import Peran
from apps.dokumen.models import Dokumen, DokumenVersi, StatusDokumen
from apps.dokumen.tests.factories import DokumenFactory, file_pdf
from apps.inti import data_contoh
from apps.penilaian.models import PeriodeAkreditasi
from apps.pps.models import RencanaPerbaikan
from apps.standar.models import Bab, ElemenPenilaian
from apps.verifikasi.models import LogVerifikasi

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def pdf_cepat(monkeypatch):
    monkeypatch.setattr(data_contoh, "_pdf", lambda judul, catatan="": file_pdf(f"{judul}.pdf"))


def test_isi_membuat_data_lengkap_lewat_workflow(settings):
    settings.DEBUG = True
    call_command("data_contoh", "isi", verbosity=0)
    assert User.objects.filter(username__startswith="demo.").count() == len(data_contoh.PENGGUNA)
    assert ElemenPenilaian.objects.count() == 18
    status = set(Dokumen.objects.values_list("status", flat=True))
    assert {
        "draft",
        "diajukan",
        "diverifikasi_komite",
        "disetujui",
        "dikembalikan",
        "kedaluwarsa",
    } <= status
    assert LogVerifikasi.objects.exists()
    assert PeriodeAkreditasi.objects.get(aktif=True).nama.startswith("[CONTOH]")
    assert RencanaPerbaikan.objects.exists()
    assert Bab.objects.get(kode="TKRS").pokja.kode == "DEMO-TKRS"
    with pytest.raises(CommandError, match="sudah ada"):
        call_command("data_contoh", "isi", verbosity=0)


def test_hapus_hanya_data_contoh(settings, buat_user, django_capture_on_commit_callbacks):
    settings.DEBUG = True
    asli_user = buat_user(Peran.KOMITE_MUTU, username="komite.asli")
    asli_dok = DokumenFactory(pokja=Pokja.objects.create(kode="POKJA-ASLI", nama="Asli"))
    call_command("data_contoh", "isi", verbosity=0)
    # data asli yang ditautkan ke akun contoh tetap aman
    asli_dok.penanggung_jawab = User.objects.get(username="demo.komite")
    asli_dok.save()
    file_contoh = [v.file.name for v in DokumenVersi.objects.exclude(dokumen=asli_dok)]
    storage = DokumenVersi.objects.first().file.storage

    with django_capture_on_commit_callbacks(execute=True):
        call_command("data_contoh", "hapus", verbosity=0)

    assert not User.objects.filter(username__startswith="demo.").exists()
    assert not ElemenPenilaian.semua.exists()
    assert not PeriodeAkreditasi.semua.exists()
    assert list(Dokumen.semua.all()) == [asli_dok]
    asli_dok.refresh_from_db()
    assert asli_dok.penanggung_jawab is None and asli_dok.versi_aktif is not None
    assert User.objects.filter(pk=asli_user.pk).exists()
    assert Bab.objects.get(kode="TKRS").pokja is None
    assert not any(storage.exists(n) for n in file_contoh)


def test_reset_dan_tolak_saat_produksi(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG=False"):
        call_command("data_contoh", "reset", verbosity=0)
    call_command("data_contoh", "reset", "--paksa", verbosity=0)
    call_command("data_contoh", "reset", "--paksa", verbosity=0)
    assert Dokumen.objects.filter(status=StatusDokumen.KEDALUWARSA).count() == 1


def test_produksi_memakai_sandi_acak_bukan_sandi_publik(settings, capsys):
    settings.DEBUG = False
    call_command("data_contoh", "isi", "--paksa")
    keluaran = capsys.readouterr().out
    admin = User.objects.get(username="demo.admin")
    assert not admin.check_password(data_contoh.PASSWORD)
    sandi = keluaran.rsplit("kata sandi: ", 1)[1].strip()
    assert admin.check_password(sandi)


def test_kata_sandi_ditentukan_sendiri(settings):
    settings.DEBUG = False
    call_command("data_contoh", "isi", "--paksa", "--kata-sandi", "LatihanRS-2026", verbosity=0)
    assert User.objects.get(username="demo.komite").check_password("LatihanRS-2026")
    with pytest.raises(CommandError, match="minimal 10"):
        call_command("data_contoh", "reset", "--paksa", "--kata-sandi", "pendek", verbosity=0)
