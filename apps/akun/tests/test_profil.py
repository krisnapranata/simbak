import pytest
from django.urls import reverse

from apps.akun.peran import Peran

pytestmark = pytest.mark.django_db


def test_profil_dan_panduan(client, buat_user, pokja):
    client.force_login(buat_user(Peran.KETUA_POKJA, pokja=[pokja]))
    resp = client.get(reverse("akun:profil"))
    assert resp.context["daftar_peran"] == ["Ketua Pokja"]
    resp = client.get(reverse("panduan"))
    assert resp.context["peran_saya"] == [Peran.KETUA_POKJA]
    assert "Ajukan verifikasi" in resp.text


def test_ganti_kata_sandi_tetap_login(client, buat_user):
    user = buat_user()
    client.force_login(user)
    resp = client.post(
        reverse("akun:kata_sandi"),
        {
            "old_password": "rahasia-kuat-123",
            "new_password1": "Sandi-Baru-Panjang-2026",
            "new_password2": "Sandi-Baru-Panjang-2026",
        },
    )
    assert resp.url == reverse("akun:profil")
    user.refresh_from_db()
    assert user.check_password("Sandi-Baru-Panjang-2026")
    assert client.get(reverse("akun:profil")).status_code == 200


def test_kata_sandi_pendek_ditolak(client, buat_user):
    client.force_login(buat_user())
    resp = client.post(
        reverse("akun:kata_sandi"),
        {
            "old_password": "rahasia-kuat-123",
            "new_password1": "Pendek1!",
            "new_password2": "Pendek1!",
        },
    )
    assert resp.status_code == 200 and resp.context["form"].errors


def test_halaman_error_ramah(client, buat_user):
    client.force_login(buat_user(Peran.ANGGOTA_POKJA))
    resp = client.get(reverse("penilaian:periode_list"))
    assert resp.status_code == 403 and "tidak berhak" in resp.text
    resp = client.get("/tidak-ada/")
    assert resp.status_code == 404 and "Halaman tidak ditemukan" in resp.text
