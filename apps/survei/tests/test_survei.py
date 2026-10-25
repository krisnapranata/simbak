import io
import zipfile

import pytest
from django.urls import reverse

from apps.akun.peran import Peran
from apps.dokumen.models import LogUnduhan, StatusDokumen
from apps.dokumen.tests.factories import BuktiEPFactory
from apps.standar.tests.factories import BabFactory, ElemenPenilaianFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(pokja):
    bab = BabFactory(pokja=pokja)
    ep = ElemenPenilaianFactory(standar__bab=bab, jenis_bukti=["R", "D"])
    disetujui = BuktiEPFactory(
        elemen_penilaian=ep,
        jenis_bukti="R",
        dokumen__status=StatusDokumen.DISETUJUI,
        dokumen__judul="Kebijakan contoh",
    )
    pasien = BuktiEPFactory(
        elemen_penilaian=ep,
        jenis_bukti="D",
        dokumen__status=StatusDokumen.DISETUJUI,
        dokumen__judul="Laporan contoh berisi data pasien",
        dokumen__mengandung_data_pasien=True,
    )
    BuktiEPFactory(
        elemen_penilaian=ep,
        jenis_bukti="D",
        dokumen__status=StatusDokumen.DRAFT,
        dokumen__judul="Draft contoh",
    )
    return {"bab": bab, "ep": ep, "disetujui": disetujui.dokumen, "pasien": pasien.dokumen}


def test_telusur_hanya_bukti_disetujui(client, buat_user, data):
    client.force_login(buat_user(Peran.SURVEIOR_INTERNAL))
    resp = client.get(reverse("survei:bab", args=[data["bab"].pk]))
    assert resp.status_code == 200
    assert "Kebijakan contoh" in resp.text and "Laporan contoh" in resp.text
    assert "Draft contoh" not in resp.text


def test_tamu_tidak_melihat_dokumen_data_pasien(client, buat_user, data):
    client.force_login(buat_user(Peran.TAMU_SURVEIOR))
    resp = client.get(reverse("survei:bab", args=[data["bab"].pk]))
    assert "Kebijakan contoh" in resp.text
    assert "Laporan contoh" not in resp.text


def test_bab_pokja_lain_404(client, buat_user, data):
    client.force_login(buat_user(Peran.ANGGOTA_POKJA))
    for nama in ["survei:bab", "survei:pdf", "survei:zip"]:
        assert client.get(reverse(nama, args=[data["bab"].pk])).status_code == 404


def test_ekspor_pdf(client, buat_user, data):
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    resp = client.get(reverse("survei:pdf", args=[data["bab"].pk]))
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_ekspor_zip_berisi_file_dan_mencatat_data_pasien(client, buat_user, data):
    user = buat_user(Peran.KOMITE_MUTU)
    client.force_login(user)
    resp = client.get(reverse("survei:zip", args=[data["bab"].pk]))
    arsip = zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content)))
    nama = arsip.namelist()
    assert any(n.endswith("_ringkasan.pdf") for n in nama)
    ep = data["ep"]
    assert any(n.startswith(f"{ep.standar.kode}/EP {ep.kode}/R/") for n in nama)
    assert len([n for n in nama if not n.endswith("ringkasan.pdf")]) == 2  # draft tidak ikut
    assert LogUnduhan.objects.filter(user=user, keterangan="ekspor ZIP").count() == 1
