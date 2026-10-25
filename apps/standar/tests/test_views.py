import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.akun.peran import Peran
from apps.standar.models import ElemenPenilaian, LogImporStandar
from apps.standar.permissions import queryset_bab_untuk

from .factories import BabFactory, ElemenPenilaianFactory

pytestmark = pytest.mark.django_db

PERAN_LIHAT_SEMUA = [
    Peran.SUPER_ADMIN,
    Peran.DIREKTUR,
    Peran.KOMITE_MUTU,
    Peran.SURVEIOR_INTERNAL,
    Peran.TAMU_SURVEIOR,
]
PERAN_POKJA = [Peran.KETUA_POKJA, Peran.ANGGOTA_POKJA]


@pytest.fixture
def dua_bab(pokja):
    return BabFactory(pokja=pokja), BabFactory()


@pytest.mark.parametrize("peran", PERAN_LIHAT_SEMUA)
def test_peran_lihat_semua_melihat_semua_bab(client, buat_user, dua_bab, peran):
    client.force_login(buat_user(peran))
    resp = client.get(reverse("standar:bab_list"))
    assert resp.status_code == 200
    assert set(resp.context["daftar_bab"]) == set(dua_bab)


@pytest.mark.parametrize("peran", PERAN_POKJA)
def test_peran_pokja_hanya_bab_pokjanya(client, buat_user, dua_bab, pokja, peran):
    bab_sendiri, bab_lain = dua_bab
    client.force_login(buat_user(peran, pokja=[pokja]))

    resp = client.get(reverse("standar:bab_list"))
    assert list(resp.context["daftar_bab"]) == [bab_sendiri]
    assert client.get(reverse("standar:bab_detail", args=[bab_sendiri.pk])).status_code == 200
    # bab pokja lain: 404, bukan 403, agar keberadaannya tidak bocor
    assert client.get(reverse("standar:bab_detail", args=[bab_lain.pk])).status_code == 404


def test_user_tanpa_peran_tidak_melihat_bab(buat_user, dua_bab):
    assert not queryset_bab_untuk(buat_user()).exists()


def test_detail_bab_menampilkan_ep_aktif_saja(client, buat_user):
    ep = ElemenPenilaianFactory(uraian="Uraian EP contoh tampil")
    ElemenPenilaianFactory(
        standar=ep.standar, uraian="Uraian EP contoh nonaktif", dihapus_pada="2026-01-01T00:00Z"
    )
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    resp = client.get(reverse("standar:bab_detail", args=[ep.standar.bab.pk]))
    assert "Uraian EP contoh tampil" in resp.text
    assert "Uraian EP contoh nonaktif" not in resp.text


def test_filter_htmx_mengembalikan_partial(client, buat_user, dua_bab):
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    resp = client.get(
        reverse("standar:bab_list"), {"q": dua_bab[0].kode}, headers={"HX-Request": "true"}
    )
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert list(resp.context["daftar_bab"]) == [dua_bab[0]]


# --- Impor lewat web --------------------------------------------------------


@pytest.mark.parametrize("peran", [Peran.SUPER_ADMIN, Peran.KOMITE_MUTU])
def test_impor_boleh_untuk_admin_dan_komite(client, buat_user, peran):
    client.force_login(buat_user(peran))
    assert client.get(reverse("standar:impor")).status_code == 200
    assert client.get(reverse("standar:impor_template")).status_code == 200


@pytest.mark.parametrize(
    "peran",
    [
        Peran.DIREKTUR,
        Peran.KETUA_POKJA,
        Peran.ANGGOTA_POKJA,
        Peran.SURVEIOR_INTERNAL,
        Peran.TAMU_SURVEIOR,
    ],
)
def test_impor_ditolak_untuk_peran_lain(client, buat_user, peran):
    client.force_login(buat_user(peran))
    assert client.get(reverse("standar:impor")).status_code == 403
    assert client.get(reverse("standar:impor_template")).status_code == 403


def _unggah(client, path, **extra):
    data = {"file": SimpleUploadedFile("starkes.xlsx", path.read_bytes()), **extra}
    return client.post(reverse("standar:impor"), data)


def test_alur_impor_pratinjau_lalu_konfirmasi(client, buat_user, buat_excel):
    user = buat_user(Peran.KOMITE_MUTU)
    client.force_login(user)

    resp = _unggah(client, buat_excel())
    log = LogImporStandar.objects.get()
    assert resp.url == reverse("standar:impor_pratinjau", args=[log.pk])
    assert log.status == LogImporStandar.Status.PRATINJAU
    assert log.diimpor_oleh == user
    assert log.ringkasan["ep"]["dibuat"] == 3
    assert not ElemenPenilaian.objects.exists()  # pratinjau belum menyimpan
    assert client.get(resp.url).context["bisa_proses"]

    client.post(reverse("standar:impor_konfirmasi", args=[log.pk]))
    log.refresh_from_db()
    assert log.status == LogImporStandar.Status.BERHASIL
    assert not log.file  # file sementara dihapus
    assert ElemenPenilaian.objects.count() == 3

    # konfirmasi kedua tidak memproses ulang
    client.post(reverse("standar:impor_konfirmasi", args=[log.pk]))
    assert LogImporStandar.objects.get().status == LogImporStandar.Status.BERHASIL


def test_impor_file_error_langsung_gagal_validasi(client, buat_user, buat_excel):
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    ep = [["TKRS", "TKRS 1", "Uraian standar contoh", "", "a", "Uraian EP contoh", "Q", 1]]
    _unggah(client, buat_excel(ep=ep))
    log = LogImporStandar.objects.get()
    assert log.status == LogImporStandar.Status.GAGAL_VALIDASI
    assert log.galat and not log.file


def test_impor_tolak_file_bukan_xlsx(client, buat_user, tmp_path):
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    palsu = tmp_path / "palsu.xlsx"
    palsu.write_bytes(b"ini teks, bukan excel")
    resp = _unggah(client, palsu)
    assert resp.status_code == 200
    assert resp.context["form"].errors["file"]
    assert not LogImporStandar.objects.exists()


def test_hanya_pengunggah_yang_bisa_konfirmasi_atau_batal(client, buat_user, buat_excel):
    pengunggah = buat_user(Peran.KOMITE_MUTU)
    client.force_login(pengunggah)
    _unggah(client, buat_excel())
    log = LogImporStandar.objects.get()

    client.force_login(buat_user(Peran.KOMITE_MUTU))
    assert client.post(reverse("standar:impor_konfirmasi", args=[log.pk])).status_code == 403
    assert client.post(reverse("standar:impor_batal", args=[log.pk])).status_code == 403
    assert LogImporStandar.objects.get().status == LogImporStandar.Status.PRATINJAU

    client.force_login(buat_user(Peran.ANGGOTA_POKJA))
    assert client.post(reverse("standar:impor_konfirmasi", args=[log.pk])).status_code == 403


def test_batalkan_impor(client, buat_user, buat_excel):
    client.force_login(buat_user(Peran.SUPER_ADMIN))
    _unggah(client, buat_excel())
    log = LogImporStandar.objects.get()
    client.post(reverse("standar:impor_batal", args=[log.pk]))
    log.refresh_from_db()
    assert log.status == LogImporStandar.Status.DIBATALKAN
    assert not log.file
    assert not ElemenPenilaian.objects.exists()
