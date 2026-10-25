import datetime
import io

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from openpyxl import load_workbook

from apps.akun.peran import Peran
from apps.penilaian import services as penilaian_services
from apps.penilaian.models import PeriodeAkreditasi
from apps.pps import services
from apps.pps.models import RencanaPerbaikan
from apps.standar.tests.factories import BabFactory, ElemenPenilaianFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def periode():
    return PeriodeAkreditasi.objects.create(
        nama="Periode contoh", tanggal_mulai=datetime.date(2026, 1, 1), aktif=True
    )


@pytest.fixture
def ep(pokja):
    return ElemenPenilaianFactory(standar__bab=BabFactory(pokja=pokja))


def _pps(ep, periode, user, **kw):
    return RencanaPerbaikan.objects.create(
        periode=periode,
        elemen_penilaian=ep,
        rekomendasi="Rekomendasi contoh",
        dibuat_oleh=user,
        **kw,
    )


def test_ketua_buat_pps_bab_sendiri_saja(client, buat_user, pokja, ep, periode):
    ketua = buat_user(Peran.KETUA_POKJA, pokja=[pokja])
    client.force_login(ketua)
    data = {"periode": periode.pk, "rekomendasi": "Rekomendasi contoh", "status": "rencana"}
    assert client.post(reverse("pps:baru"), {**data, "elemen_penilaian": ep.pk}).status_code == 302
    lain = ElemenPenilaianFactory()
    resp = client.post(reverse("pps:baru"), {**data, "elemen_penilaian": lain.pk})
    assert "elemen_penilaian" in resp.context["form"].errors
    assert RencanaPerbaikan.objects.count() == 1


def test_anggota_dan_surveior_tidak_bisa_buat(client, buat_user, pokja):
    for peran in [Peran.ANGGOTA_POKJA, Peran.SURVEIOR_INTERNAL]:
        client.force_login(buat_user(peran, pokja=[pokja]))
        assert client.get(reverse("pps:baru")).status_code == 403


def test_pj_hanya_ubah_status_dan_progres(client, buat_user, pokja, ep, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    pj = buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja])
    pps = _pps(ep, periode, komite, pj=pj)
    client.force_login(pj)
    resp = client.get(reverse("pps:ubah", args=[pps.pk]))
    assert set(resp.context["form"].fields) == {"status", "catatan_progres"}
    client.post(reverse("pps:ubah", args=[pps.pk]), {"status": "berjalan", "catatan_progres": "OK"})
    pps.refresh_from_db()
    assert pps.status == "berjalan"
    pps.rekomendasi = "diubah"
    with pytest.raises(PermissionDenied):
        services.simpan_pps(user=pj, pps=pps, field_diubah=["rekomendasi"])


def test_pps_tersaring_per_akses(client, buat_user, pokja, ep, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    milik = _pps(ep, periode, komite)
    lain = _pps(ElemenPenilaianFactory(), periode, komite)
    client.force_login(buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja]))
    assert list(client.get(reverse("pps:list")).context["daftar_pps"]) == [milik]
    assert client.get(reverse("pps:ubah", args=[lain.pk])).status_code == 404


def test_buat_dari_penilaian_idempoten(buat_user, pokja, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    bab = BabFactory(pokja=pokja)
    skor = {}
    for nilai in [10, 5, 0, "tdd"]:
        e = ElemenPenilaianFactory(standar__bab=bab)
        penilaian_services.nilai_ep(user=komite, periode=periode, ep=e, nilai=nilai)
        skor[e.pk] = nilai
    assert services.buat_dari_penilaian(user=komite, periode=periode) == 2
    assert services.buat_dari_penilaian(user=komite, periode=periode) == 0
    assert {skor[p.elemen_penilaian_id] for p in RencanaPerbaikan.objects.all()} == {5, 0}
    with pytest.raises(PermissionDenied):
        services.buat_dari_penilaian(user=buat_user(Peran.KETUA_POKJA), periode=periode)


def test_ekspor_excel(client, buat_user, ep, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    _pps(ep, periode, komite, tenggat=datetime.date(2026, 6, 1))
    client.force_login(komite)
    wb = load_workbook(io.BytesIO(client.get(reverse("pps:ekspor")).content))
    baris = list(wb["PPS"].values)
    assert baris[0][0] == "Bab" and baris[1][3] == "Rekomendasi contoh"


def test_filter_pps_yang_saya_pegang(client, buat_user, ep, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    milik = _pps(ep, periode, komite, pj=komite)
    _pps(ep, periode, komite)
    client.force_login(komite)
    assert list(client.get(reverse("pps:list"), {"pj": "saya"}).context["daftar_pps"]) == [milik]
