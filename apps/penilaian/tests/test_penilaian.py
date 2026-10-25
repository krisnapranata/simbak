import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.akun.peran import Peran
from apps.dokumen.models import StatusDokumen
from apps.dokumen.permissions import queryset_dokumen_untuk
from apps.dokumen.tests.factories import BuktiEPFactory, DokumenFactory
from apps.penilaian import capaian, services
from apps.penilaian.models import KriteriaPredikat, PenilaianEP, PeriodeAkreditasi, SyaratPredikat
from apps.standar.models import Bab
from apps.standar.tests.factories import BabFactory, ElemenPenilaianFactory, StandarFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def periode():
    return PeriodeAkreditasi.objects.create(
        nama="Periode contoh",
        tanggal_mulai=datetime.date(2026, 1, 1),
        tanggal_survei=datetime.date(2026, 12, 1),
        aktif=True,
        status=PeriodeAkreditasi.Status.PENILAIAN_MANDIRI,
    )


@pytest.fixture
def bab(pokja):
    return BabFactory(pokja=pokja)


@pytest.fixture
def ketua(buat_user, pokja):
    return buat_user(Peran.KETUA_POKJA, pokja=[pokja])


def _ep(bab, jenis=("R",)):
    return ElemenPenilaianFactory(standar=StandarFactory(bab=bab), jenis_bukti=list(jenis))


def test_rumus_capaian_tdd_dikeluarkan_dari_pembagi(ketua, periode, bab):
    ep = [_ep(bab) for _ in range(5)]
    for e, nilai in zip(ep, [10, 5, "tdd", 0], strict=False):  # ep[4] belum dinilai
        services.nilai_ep(user=ketua, periode=periode, ep=e, nilai=nilai)

    ((_, c),) = capaian.capaian_per_bab(periode=periode, bab_qs=Bab.objects.filter(pk=bab.pk))
    assert (c.jumlah_ep, c.dinilai, c.tdd, c.total_skor) == (5, 4, 1, 15)
    assert c.persen == 50.0  # 15 / (3 × 10)


def test_belum_dinilai_tdd_dan_nol_dibedakan(ketua, periode, bab):
    e = _ep(bab)
    services.nilai_ep(user=ketua, periode=periode, ep=e, nilai="tdd")
    p = PenilaianEP.objects.get()
    assert p.tdd and p.skor is None
    services.nilai_ep(user=ketua, periode=periode, ep=e, nilai="0")
    p.refresh_from_db()
    assert not p.tdd and p.skor == 0
    services.nilai_ep(user=ketua, periode=periode, ep=e, nilai="")
    assert not PenilaianEP.objects.exists()


def test_skor_tidak_valid_dan_constraint(ketua, periode, bab):
    e = _ep(bab)
    with pytest.raises(ValidationError):
        services.nilai_ep(user=ketua, periode=periode, ep=e, nilai="7")
    with pytest.raises(IntegrityError), transaction.atomic():
        PenilaianEP.objects.create(
            periode=periode, elemen_penilaian=e, tdd=True, skor=10, dinilai_oleh=ketua
        )


def test_hak_menilai(buat_user, ketua, periode, bab, pokja):
    e = _ep(bab)
    for user in [
        buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja]),
        buat_user(Peran.KETUA_POKJA),
        buat_user(Peran.SURVEIOR_INTERNAL),
        buat_user(Peran.DIREKTUR),
    ]:
        with pytest.raises(PermissionDenied):
            services.nilai_ep(user=user, periode=periode, ep=e, nilai=10)
    services.nilai_ep(user=buat_user(Peran.KOMITE_MUTU), periode=periode, ep=e, nilai=10)
    periode.status = PeriodeAkreditasi.Status.SELESAI
    periode.save()
    with pytest.raises(ValidationError):
        services.nilai_ep(user=ketua, periode=periode, ep=e, nilai=5)


def test_kelengkapan_bukti_butuh_semua_jenis_disetujui(bab):
    e = _ep(bab, jenis=("R", "D"))
    BuktiEPFactory(elemen_penilaian=e, jenis_bukti="R", dokumen__status=StatusDokumen.DISETUJUI)
    BuktiEPFactory(elemen_penilaian=e, jenis_bukti="D", dokumen__status=StatusDokumen.DRAFT)
    ep_qs = capaian.ep_aktif([bab.pk])
    assert capaian.ep_lengkap_bukti(ep_qs) == set()
    BuktiEPFactory(elemen_penilaian=e, jenis_bukti="D", dokumen__status=StatusDokumen.DISETUJUI)
    assert capaian.ep_lengkap_bukti(ep_qs) == {e.pk}
    assert not capaian.ep_tanpa_bukti(ep_qs).exists()


def test_capaian_per_pokja_menjumlahkan_bukan_rata_rata(ketua, periode, bab, pokja):
    bab2 = BabFactory(pokja=pokja)
    services.nilai_ep(user=ketua, periode=periode, ep=_ep(bab), nilai=10)
    for _ in range(3):
        services.nilai_ep(user=ketua, periode=periode, ep=_ep(bab2), nilai=0)
    baris = capaian.capaian_per_bab(periode=periode, bab_qs=Bab.objects.all())
    ((p, c),) = capaian.capaian_per_pokja(baris)
    assert p == pokja and c.persen == 25.0  # 10 / 40, bukan (100 + 0) / 2


def test_evaluasi_predikat_dari_database(ketua, periode, bab, pokja):
    bab2 = BabFactory(pokja=pokja)
    services.nilai_ep(user=ketua, periode=periode, ep=_ep(bab), nilai=10)
    services.nilai_ep(user=ketua, periode=periode, ep=_ep(bab2), nilai=5)
    baris = capaian.capaian_per_bab(periode=periode, bab_qs=Bab.objects.all())
    assert capaian.evaluasi_predikat(baris) == (None, False)

    tinggi = KriteriaPredikat.objects.create(nama="Predikat A", urutan=1)
    SyaratPredikat.objects.create(kriteria=tinggi, min_capaian=80)  # semua bab ≥ 80
    rendah = KriteriaPredikat.objects.create(nama="Predikat B", urutan=2)
    s = SyaratPredikat.objects.create(kriteria=rendah, min_capaian=80, min_jumlah_bab=1)
    s.bab_wajib.add(bab)
    assert capaian.evaluasi_predikat(baris) == (rendah, True)


def test_satu_periode_aktif(buat_user, periode):
    komite = buat_user(Peran.KOMITE_MUTU)
    baru = PeriodeAkreditasi.objects.create(nama="Baru", tanggal_mulai=datetime.date(2027, 1, 1))
    services.aktifkan_periode(user=komite, periode=baru)
    assert list(PeriodeAkreditasi.objects.filter(aktif=True)) == [baru]
    with pytest.raises(PermissionDenied):
        services.aktifkan_periode(user=buat_user(Peran.KETUA_POKJA), periode=periode)


def test_tamu_dengan_izin_periode_melihat_data_pasien(buat_user, periode):
    tamu = buat_user(Peran.TAMU_SURVEIOR)
    dok = DokumenFactory(status=StatusDokumen.DISETUJUI, mengandung_data_pasien=True)
    assert not queryset_dokumen_untuk(tamu).filter(pk=dok.pk).exists()
    periode.tamu_boleh_data_pasien.add(tamu)
    assert queryset_dokumen_untuk(tamu).filter(pk=dok.pk).exists()


# --- View ------------------------------------------------------------------


@pytest.mark.parametrize("peran", list(Peran))
def test_dashboard_terbuka_untuk_semua_peran(client, buat_user, periode, bab, peran):
    _ep(bab)
    client.force_login(buat_user(peran))
    resp = client.get(reverse("beranda"))
    assert resp.status_code == 200
    assert resp.context["periode"] == periode


def test_dashboard_tanpa_periode(client, buat_user):
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    assert client.get(reverse("beranda")).status_code == 200


def test_halaman_penilaian_bab_dan_akses(client, buat_user, ketua, periode, bab):
    e = _ep(bab)
    client.force_login(ketua)
    resp = client.get(reverse("penilaian:bab", args=[bab.pk]))
    assert resp.status_code == 200 and resp.context["bisa_nilai"]
    assert client.get(reverse("penilaian:bab", args=[BabFactory().pk])).status_code == 404

    hx = {"HX-Request": "true"}
    url = reverse("penilaian:nilai", args=[periode.pk, e.pk])
    resp = client.post(url, {"nilai": "5", "fakta_analisis": "Fakta contoh"}, headers=hx)
    assert resp.status_code == 200 and resp.context["ep"].nilai.skor == 5

    client.force_login(buat_user(Peran.SURVEIOR_INTERNAL))
    resp = client.post(url, {"nilai": "10"}, headers=hx)
    assert resp.context["galat"]
    assert PenilaianEP.objects.get().skor == 5
    resp = client.post(
        reverse("penilaian:catatan", args=[periode.pk, e.pk]), {"isi": "Catatan contoh"}, headers=hx
    )
    assert resp.context["ep"].catatan_periode[0].isi == "Catatan contoh"


def test_kelola_periode_hanya_komite_admin(client, buat_user):
    client.force_login(buat_user(Peran.KETUA_POKJA))
    assert client.get(reverse("penilaian:periode_list")).status_code == 403
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    resp = client.post(
        reverse("penilaian:periode_baru"),
        {"nama": "2027", "tanggal_mulai": "2027-01-01", "status": "persiapan", "aktif": "on"},
    )
    assert resp.status_code == 302
    assert PeriodeAkreditasi.objects.get().aktif
