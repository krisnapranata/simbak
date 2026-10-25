import datetime

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.akun.peran import Peran
from apps.dokumen import services as dokumen_services
from apps.dokumen.models import JenisDokumen, StatusDokumen
from apps.dokumen.tests.factories import DokumenFactory
from apps.verifikasi import services
from apps.verifikasi.models import LogVerifikasi, Notifikasi, PengingatTerkirim
from apps.verifikasi.permissions import queryset_antrian_untuk
from apps.verifikasi.services import TransisiTidakValid

pytestmark = pytest.mark.django_db
S = StatusDokumen


@pytest.fixture
def peran(buat_user, pokja):
    return {
        "ketua": buat_user(Peran.KETUA_POKJA, pokja=[pokja], email="ketua@contoh.test"),
        "anggota": buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja]),
        "komite": buat_user(Peran.KOMITE_MUTU, email="komite@contoh.test"),
        "direktur": buat_user(Peran.DIREKTUR, email="direktur@contoh.test"),
    }


def test_alur_regulasi_lengkap(peran, pokja, django_capture_on_commit_callbacks):
    dok = DokumenFactory(pokja=pokja, jenis_dokumen=JenisDokumen.SPO, judul="SPO contoh")
    with django_capture_on_commit_callbacks(execute=True):
        dok = services.ajukan(dokumen=dok, user=peran["ketua"])
    assert dok.status == S.DIAJUKAN
    assert Notifikasi.objects.filter(penerima=peran["komite"]).exists()
    assert mail.outbox and "SPO contoh" in mail.outbox[0].subject
    assert "/dokumen/" in mail.outbox[0].body

    dok = services.verifikasi(dokumen=dok, user=peran["komite"])
    assert Notifikasi.objects.filter(penerima=peran["direktur"]).exists()
    with pytest.raises(PermissionDenied):  # regulasi: final oleh direktur
        services.setujui(dokumen=dok, user=peran["komite"])
    dok = services.setujui(dokumen=dok, user=peran["direktur"])
    assert dok.status == S.DISETUJUI
    assert list(
        LogVerifikasi.objects.filter(dokumen=dok).order_by("id").values_list("ke_status", flat=True)
    ) == [S.DIAJUKAN, S.DIVERIFIKASI_KOMITE, S.DISETUJUI]


def test_bukti_pelaksanaan_disetujui_komite(peran, pokja):
    dok = DokumenFactory(
        pokja=pokja, jenis_dokumen=JenisDokumen.NOTULEN, status=S.DIVERIFIKASI_KOMITE
    )
    assert services.setujui(dokumen=dok, user=peran["komite"]).status == S.DISETUJUI


def test_anggota_tidak_bisa_ajukan(peran, pokja):
    dok = DokumenFactory(pokja=pokja)
    with pytest.raises(PermissionDenied):
        services.ajukan(dokumen=dok, user=peran["anggota"])


def test_transisi_tidak_valid(peran, pokja):
    dok = DokumenFactory(pokja=pokja)
    with pytest.raises(TransisiTidakValid):
        services.verifikasi(dokumen=dok, user=peran["komite"])
    tanpa_file = DokumenFactory(pokja=pokja, dengan_file=False)
    with pytest.raises(TransisiTidakValid, match="file"):
        services.ajukan(dokumen=tanpa_file, user=peran["ketua"])
    assert not LogVerifikasi.objects.exists()


def test_kembalikan_wajib_catatan_lalu_edit_kembali_ke_draft(peran, pokja):
    dok = DokumenFactory(pokja=pokja, status=S.DIAJUKAN)
    with pytest.raises(TransisiTidakValid, match="Catatan"):
        services.kembalikan(dokumen=dok, user=peran["komite"], catatan=" ")
    dok = services.kembalikan(dokumen=dok, user=peran["komite"], catatan="Lengkapi tanda tangan")
    assert dok.status == S.DIKEMBALIKAN
    assert Notifikasi.objects.filter(penerima=peran["ketua"]).exists()
    dok = dokumen_services.ubah_dokumen(dokumen=dok, user=peran["anggota"], data={"nomor": "01"})
    assert dok.status == S.DRAFT


def test_aksi_view(client, peran, pokja):
    dok = DokumenFactory(pokja=pokja)
    url = reverse("verifikasi:aksi", args=[dok.pk, "ajukan"])
    client.force_login(peran["anggota"])
    client.post(url)
    dok.refresh_from_db()
    assert dok.status == S.DRAFT
    client.force_login(peran["ketua"])
    assert client.post(url).status_code == 302
    dok.refresh_from_db()
    assert dok.status == S.DIAJUKAN
    assert client.post(reverse("verifikasi:aksi", args=[dok.pk, "hapus_semua"])).status_code == 404
    lain = DokumenFactory()
    assert client.post(reverse("verifikasi:aksi", args=[lain.pk, "ajukan"])).status_code == 404


def test_antrian_per_peran(peran, pokja):
    diajukan = DokumenFactory(pokja=pokja, status=S.DIAJUKAN)
    regulasi = DokumenFactory(
        pokja=pokja, status=S.DIVERIFIKASI_KOMITE, jenis_dokumen=JenisDokumen.SPO
    )
    laporan = DokumenFactory(
        pokja=pokja, status=S.DIVERIFIKASI_KOMITE, jenis_dokumen=JenisDokumen.LAPORAN
    )
    draft = DokumenFactory(pokja=pokja)
    assert set(queryset_antrian_untuk(peran["komite"])) == {diajukan, laporan}
    assert set(queryset_antrian_untuk(peran["direktur"])) == {regulasi, laporan}
    assert set(queryset_antrian_untuk(peran["ketua"])) == {draft}
    assert not queryset_antrian_untuk(peran["anggota"]).exists()


def test_notifikasi_hanya_milik_sendiri(client, peran):
    notif = Notifikasi.objects.create(penerima=peran["komite"], judul="x", url="/dokumen/")
    client.force_login(peran["ketua"])
    assert client.post(reverse("verifikasi:baca", args=[notif.pk])).status_code == 404
    client.force_login(peran["komite"])
    assert client.get(reverse("beranda")).context["jumlah_notifikasi"] == 1
    assert client.post(reverse("verifikasi:baca", args=[notif.pk])).url == "/dokumen/"
    notif.refresh_from_db()
    assert notif.dibaca_pada is not None


def test_kirim_pengingat(peran, pokja):
    hari_ini = timezone.localdate()
    lewat = DokumenFactory(
        pokja=pokja, status=S.DISETUJUI, tanggal_review_berikutnya=hari_ini - datetime.timedelta(1)
    )
    dekat = DokumenFactory(
        pokja=pokja, status=S.DISETUJUI, tanggal_review_berikutnya=hari_ini + datetime.timedelta(25)
    )
    call_command("kirim_pengingat", "--dry-run")
    lewat.refresh_from_db()
    assert lewat.status == S.DISETUJUI and not PengingatTerkirim.objects.exists()

    call_command("kirim_pengingat")
    call_command("kirim_pengingat")
    lewat.refresh_from_db()
    assert lewat.status == S.KEDALUWARSA
    log = lewat.log_verifikasi.get()
    assert log.user is None and log.ke_status == S.KEDALUWARSA
    pengingat = PengingatTerkirim.objects.get()
    assert (pengingat.dokumen, pengingat.ambang_hari) == (dekat, 30)
    assert (
        Notifikasi.objects.filter(penerima=peran["ketua"], judul__contains="25 hari").count() == 1
    )
