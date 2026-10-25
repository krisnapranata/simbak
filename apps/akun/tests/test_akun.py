from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.akun.peran import Peran
from apps.akun.permissions import bisa_lihat_semua_bab, punya_peran

pytestmark = pytest.mark.django_db

PASSWORD = "rahasia-kuat-123"


def _masuk(client, user, password=PASSWORD):
    return client.post(reverse("akun:masuk"), {"username": user.username, "password": password})


def test_halaman_login_terbuka_tanpa_login(client):
    assert client.get(reverse("akun:masuk")).status_code == 200


def test_halaman_lain_wajib_login(client):
    for url in [reverse("beranda"), reverse("standar:bab_list"), reverse("standar:impor")]:
        resp = client.get(url)
        assert resp.status_code == 302
        assert resp.url.startswith(reverse("akun:masuk"))


def test_login_berhasil(client, buat_user):
    user = buat_user(Peran.KOMITE_MUTU)
    resp = _masuk(client, user)
    assert resp.status_code == 302
    assert client.get(reverse("beranda")).status_code == 200


def test_tamu_surveior_masa_aktif_habis_ditolak(client, buat_user):
    user = buat_user(Peran.TAMU_SURVEIOR, aktif_sampai=timezone.now() - timedelta(minutes=1))
    resp = _masuk(client, user)
    assert resp.status_code == 200
    assert "_auth_user_id" not in client.session


def test_tamu_surveior_masih_aktif_boleh_login(client, buat_user):
    user = buat_user(Peran.TAMU_SURVEIOR, aktif_sampai=timezone.now() + timedelta(days=1))
    assert _masuk(client, user).status_code == 302


def test_sesi_berjalan_berakhir_saat_masa_aktif_habis(client, buat_user):
    user = buat_user(Peran.TAMU_SURVEIOR, aktif_sampai=timezone.now() + timedelta(days=1))
    client.force_login(user)
    assert client.get(reverse("beranda")).status_code == 200
    user.aktif_sampai = timezone.now() - timedelta(seconds=1)
    user.save()
    assert client.get(reverse("beranda")).status_code == 302


def test_login_dibatasi_axes(client, buat_user):
    user = buat_user()
    for _ in range(5):
        _masuk(client, user, password="salah")
    resp = _masuk(client, user)
    assert resp.status_code != 302
    assert "_auth_user_id" not in client.session


def test_fixture_peran_awal_idempoten():
    call_command("loaddata", "peran_awal", verbosity=0)
    call_command("loaddata", "peran_awal", verbosity=0)
    assert set(Group.objects.values_list("name", flat=True)) == set(Peran.values)
    assert (
        Group.objects.get(name=Peran.SUPER_ADMIN)
        .permissions.filter(codename="change_elemenpenilaian")
        .exists()
    )


def test_cek_peran(buat_user):
    direktur = buat_user(Peran.DIREKTUR)
    anggota = buat_user(Peran.ANGGOTA_POKJA)
    assert punya_peran(direktur, Peran.DIREKTUR)
    assert bisa_lihat_semua_bab(direktur)
    assert not bisa_lihat_semua_bab(anggota)


def test_kunci_login_per_user_bukan_per_ip(client, buat_user):
    """Di belakang proxy semua pengguna bisa ber-IP sama; satu orang salah sandi tidak
    boleh mengunci orang lain."""
    korban, lain = buat_user(), buat_user()
    for _ in range(5):
        _masuk(client, korban, password="salah")
    assert _masuk(client, korban).status_code != 302
    client.logout()
    assert _masuk(client, lain).status_code == 302


def test_ip_klien_dari_header_proxy(rf):
    from apps.inti.utils import ip_klien

    req = rf.get("/", HTTP_X_REAL_IP="10.1.2.3", REMOTE_ADDR="172.18.0.5")
    assert ip_klien(req) == "10.1.2.3"
