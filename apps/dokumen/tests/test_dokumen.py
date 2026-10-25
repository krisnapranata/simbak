import datetime
import io
import zipfile

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.akun.peran import Peran
from apps.dokumen import services
from apps.dokumen.models import BuktiEP, DokumenVersi, JenisDokumen, LogUnduhan, StatusDokumen
from apps.dokumen.permissions import queryset_dokumen_untuk
from apps.standar.tests.factories import ElemenPenilaianFactory

from .factories import BuktiEPFactory, DokumenFactory, file_pdf, isi_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def ep(pokja):
    return ElemenPenilaianFactory(standar__bab__pokja=pokja, jenis_bukti=["R", "D"])


@pytest.fixture
def anggota(buat_user, pokja):
    return buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja])


def _data(pokja, **kw):
    return {"judul": "SPO contoh", "jenis_dokumen": JenisDokumen.SPO, "pokja": pokja, **kw}


# --- Service ------------------------------------------------------------------


def test_buat_dokumen_menyimpan_versi_privat_dengan_nama_acak(anggota, pokja, ep):
    dok = services.buat_dokumen(
        user=anggota,
        data=_data(pokja),
        file=file_pdf("SPO Cuci Tangan.pdf"),
        ep=ep,
        jenis_bukti="R",
    )
    versi = dok.versi_aktif
    assert dok.status == StatusDokumen.DRAFT
    assert versi.nomor_versi == 1
    assert versi.nama_file_asli == "SPO Cuci Tangan.pdf"
    assert versi.file.name.startswith("bukti/") and "Cuci" not in versi.file.name
    assert len(versi.sha256) == 64
    assert str(settings.MEDIA_ROOT) not in versi.file.path
    assert BuktiEP.objects.filter(dokumen=dok, elemen_penilaian=ep, jenis_bukti="R").exists()


def test_tanggal_review_regulasi_otomatis(anggota, pokja):
    dok = services.buat_dokumen(
        user=anggota,
        data=_data(pokja, tanggal_terbit=datetime.date(2026, 1, 31)),
        file=file_pdf(),
    )
    assert dok.tanggal_review_berikutnya == datetime.date(2029, 1, 31)


def test_versi_baru_tidak_menghapus_versi_lama(anggota, pokja):
    dok = services.buat_dokumen(user=anggota, data=_data(pokja), file=file_pdf())
    v1 = dok.versi_aktif
    v2 = services.unggah_versi(dokumen=dok, user=anggota, file=file_pdf(), catatan_perubahan="rev")
    dok.refresh_from_db()
    assert v2.nomor_versi == 2 and dok.versi_aktif == v2
    assert DokumenVersi.objects.filter(pk=v1.pk).exists()
    assert v1.file.storage.exists(v1.file.name)


def test_versi_identik_ditolak(anggota, pokja):
    isi = isi_pdf()
    dok = services.buat_dokumen(user=anggota, data=_data(pokja), file=file_pdf(isi=isi))
    with pytest.raises(ValidationError, match="sama persis"):
        services.unggah_versi(
            dokumen=dok, user=anggota, file=file_pdf(isi=isi), catatan_perubahan="x"
        )


@pytest.mark.parametrize(
    "file",
    [
        SimpleUploadedFile("virus.exe", b"MZ\x90\x00"),
        SimpleUploadedFile("palsu.pdf", b"teks biasa yang mengaku pdf"),
        SimpleUploadedFile("makro.docm", b"PK\x03\x04"),
    ],
)
def test_upload_tidak_valid_ditolak(anggota, pokja, file):
    with pytest.raises(ValidationError):
        services.buat_dokumen(user=anggota, data=_data(pokja), file=file)


def test_docx_bermakro_ditolak(anggota, pokja):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
        z.writestr("word/vbaProject.bin", b"\x00")
    with pytest.raises(ValidationError):
        services.buat_dokumen(
            user=anggota, data=_data(pokja), file=SimpleUploadedFile("a.docx", buf.getvalue())
        )


def test_satu_dokumen_banyak_ep_tanpa_menyalin_file(anggota, pokja, ep):
    dok = services.buat_dokumen(user=anggota, data=_data(pokja), file=file_pdf())
    ep2 = ElemenPenilaianFactory(standar__bab__pokja=pokja, jenis_bukti=["R"])
    services.tautkan_ep(dokumen=dok, ep=ep, jenis_bukti="D", user=anggota)
    services.tautkan_ep(dokumen=dok, ep=ep2, jenis_bukti="R", user=anggota)
    assert dok.bukti.count() == 2
    assert DokumenVersi.objects.filter(dokumen=dok).count() == 1


def test_tautkan_jenis_tidak_diwajibkan_atau_duplikat_ditolak(anggota, pokja, ep):
    dok = services.buat_dokumen(user=anggota, data=_data(pokja), file=file_pdf())
    with pytest.raises(ValidationError):
        services.tautkan_ep(dokumen=dok, ep=ep, jenis_bukti="S", user=anggota)
    services.tautkan_ep(dokumen=dok, ep=ep, jenis_bukti="R", user=anggota)
    with pytest.raises(ValidationError):
        services.tautkan_ep(dokumen=dok, ep=ep, jenis_bukti="R", user=anggota)


def test_pokja_lain_tidak_boleh_buat_atau_tautkan(buat_user, anggota, pokja, ep):
    dok = services.buat_dokumen(user=anggota, data=_data(pokja), file=file_pdf())
    orang_lain = buat_user(Peran.ANGGOTA_POKJA)
    with pytest.raises(PermissionDenied):
        services.buat_dokumen(user=orang_lain, data=_data(pokja), file=file_pdf())
    with pytest.raises(PermissionDenied):
        services.tautkan_ep(dokumen=dok, ep=ep, jenis_bukti="D", user=orang_lain)


def test_revisi_dokumen_disetujui_kembali_ke_draft(buat_user, pokja):
    ketua = buat_user(Peran.KETUA_POKJA, pokja=[pokja])
    dok = DokumenFactory(pokja=pokja, status=StatusDokumen.DISETUJUI)
    anggota = buat_user(Peran.ANGGOTA_POKJA, pokja=[pokja])
    with pytest.raises(PermissionDenied):
        services.unggah_versi(dokumen=dok, user=anggota, file=file_pdf(), catatan_perubahan="x")
    services.unggah_versi(dokumen=dok, user=ketua, file=file_pdf(), catatan_perubahan="revisi")
    dok.refresh_from_db()
    assert dok.status == StatusDokumen.DRAFT
    assert dok.log_verifikasi.get().dari_status == StatusDokumen.DISETUJUI


def test_hapus_lunak_hanya_draft(anggota, pokja):
    dok = DokumenFactory(pokja=pokja, dibuat_oleh=anggota)
    services.hapus_dokumen(dokumen=dok, user=anggota)
    assert not queryset_dokumen_untuk(anggota).filter(pk=dok.pk).exists()
    assert DokumenVersi.objects.filter(dokumen=dok).exists()
    disetujui = DokumenFactory(pokja=pokja, status=StatusDokumen.DISETUJUI)
    with pytest.raises(PermissionDenied):
        services.hapus_dokumen(dokumen=disetujui, user=anggota)


# --- Hak akses & view --------------------------------------------------------


def test_queryset_pokja_hanya_milik_atau_tertaut(buat_user, anggota, pokja, ep):
    milik = DokumenFactory(pokja=pokja)
    lain = DokumenFactory()
    tertaut = DokumenFactory()
    BuktiEPFactory(dokumen=tertaut, elemen_penilaian=ep)
    assert set(queryset_dokumen_untuk(anggota)) == {milik, tertaut}
    assert set(queryset_dokumen_untuk(buat_user(Peran.KOMITE_MUTU))) == {milik, lain, tertaut}
    assert not queryset_dokumen_untuk(buat_user()).exists()


def test_tamu_hanya_dokumen_disetujui_tanpa_data_pasien(buat_user):
    tamu = buat_user(Peran.TAMU_SURVEIOR)
    ok = DokumenFactory(status=StatusDokumen.DISETUJUI)
    DokumenFactory(status=StatusDokumen.DISETUJUI, mengandung_data_pasien=True)
    DokumenFactory(status=StatusDokumen.DRAFT)
    assert list(queryset_dokumen_untuk(tamu)) == [ok]


def test_detail_dan_unduh_dokumen_lain_404(client, anggota):
    lain = DokumenFactory()
    client.force_login(anggota)
    assert client.get(reverse("dokumen:detail", args=[lain.pk])).status_code == 404
    url = reverse("dokumen:unduh", args=[lain.pk, lain.versi_aktif_id])
    assert client.get(url).status_code == 404


def test_unduh_mengirim_nama_asli_dan_mencatat_data_pasien(client, buat_user):
    dok = DokumenFactory(mengandung_data_pasien=True)
    user = buat_user(Peran.KOMITE_MUTU)
    client.force_login(user)
    resp = client.get(reverse("dokumen:unduh", args=[dok.pk, dok.versi_aktif_id]))
    assert resp.status_code == 200
    assert "Contoh Asli.pdf" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert b"".join(resp.streaming_content).startswith(b"%PDF")
    assert LogUnduhan.objects.filter(versi=dok.versi_aktif, user=user).count() == 1


def test_unduh_tanpa_data_pasien_tidak_dicatat(client, buat_user):
    dok = DokumenFactory()
    client.force_login(buat_user(Peran.KOMITE_MUTU))
    client.get(reverse("dokumen:unduh", args=[dok.pk, dok.versi_aktif_id]))
    assert not LogUnduhan.objects.exists()


def test_tamu_tidak_boleh_unduh_versi_lama(client, buat_user):
    dok = DokumenFactory(status=StatusDokumen.DISETUJUI)
    lama = dok.versi_aktif
    baru = DokumenVersi.objects.create(
        dokumen=dok,
        nomor_versi=2,
        file=file_pdf(),
        nama_file_asli="b.pdf",
        mime="application/pdf",
        ukuran=10,
        sha256="0" * 64,
        diunggah_oleh=dok.dibuat_oleh,
    )
    dok.versi_aktif = baru
    dok.save()
    client.force_login(buat_user(Peran.TAMU_SURVEIOR))
    assert client.get(reverse("dokumen:unduh", args=[dok.pk, lama.pk])).status_code == 404
    assert client.get(reverse("dokumen:unduh", args=[dok.pk, baru.pk])).status_code == 200


@pytest.mark.parametrize("peran", [Peran.SURVEIOR_INTERNAL, Peran.DIREKTUR, Peran.TAMU_SURVEIOR])
def test_peran_baca_saja_tidak_bisa_unggah(client, buat_user, peran):
    client.force_login(buat_user(peran))
    assert client.get(reverse("dokumen:baru")).status_code == 403


def test_alur_unggah_lewat_form_dengan_ep(client, anggota, pokja, ep):
    client.force_login(anggota)
    resp = client.get(reverse("dokumen:baru"), {"ep": ep.pk, "jenis": "D"})
    assert resp.status_code == 200
    resp = client.post(
        reverse("dokumen:baru"),
        {
            "judul": "Notulen rapat contoh",
            "jenis_dokumen": JenisDokumen.NOTULEN,
            "pokja": pokja.pk,
            "mengandung_data_pasien": "False",
            "file": file_pdf(),
            "ep": ep.pk,
            "jenis_bukti": "D",
        },
    )
    assert resp.status_code == 302, resp.context["form"].errors
    dok = anggota.dokumen_dibuat.get()
    assert dok.bukti.get().jenis_bukti == "D"
    assert client.get(reverse("dokumen:detail", args=[dok.pk])).status_code == 200


def test_form_wajib_memilih_data_pasien(client, anggota, pokja):
    client.force_login(anggota)
    resp = client.post(
        reverse("dokumen:baru"),
        {"judul": "x", "jenis_dokumen": JenisDokumen.SPO, "pokja": pokja.pk, "file": file_pdf()},
    )
    assert "mengandung_data_pasien" in resp.context["form"].errors


def test_ubah_hanya_saat_draft(client, anggota, pokja):
    dok = DokumenFactory(pokja=pokja, status=StatusDokumen.DIAJUKAN)
    client.force_login(anggota)
    assert client.get(reverse("dokumen:ubah", args=[dok.pk])).status_code == 403


def test_tautkan_dan_lepas_via_htmx(client, anggota, pokja, ep):
    dok = DokumenFactory(pokja=pokja)
    client.force_login(anggota)
    hx = {"HX-Request": "true"}
    resp = client.get(reverse("dokumen:cari_ep", args=[dok.pk]), {"q": ep.standar.kode}, headers=hx)
    assert ep in resp.context["hasil"]
    resp = client.post(
        reverse("dokumen:tautkan", args=[dok.pk]),
        {"elemen_penilaian": ep.pk, "jenis_bukti": "R"},
        headers=hx,
    )
    assert resp.status_code == 200 and not resp.context["galat"]
    bukti = dok.bukti.get()
    resp = client.post(reverse("dokumen:lepas", args=[dok.pk, bukti.pk]), headers=hx)
    assert not dok.bukti.exists()


def test_list_tersaring_dan_filter_htmx(client, anggota, pokja):
    milik = DokumenFactory(pokja=pokja, judul="Panduan contoh A")
    DokumenFactory(judul="Panduan contoh B")
    client.force_login(anggota)
    resp = client.get(reverse("dokumen:list"), {"q": "Panduan"}, headers={"HX-Request": "true"})
    assert list(resp.context["daftar_dokumen"]) == [milik]


def test_pratinjau_inline_pdf_dan_gambar_terisolasi(client, buat_user):
    dok = DokumenFactory(mengandung_data_pasien=True)
    user = buat_user(Peran.KOMITE_MUTU)
    client.force_login(user)
    url = reverse("dokumen:unduh", args=[dok.pk, dok.versi_aktif_id])
    resp = client.get(url, {"lihat": "1"})
    assert resp["Content-Disposition"].startswith("inline")
    assert "Content-Security-Policy" not in resp
    assert LogUnduhan.objects.get(user=user).keterangan == "lihat"

    versi = dok.versi_aktif
    versi.mime = "image/png"
    versi.save()
    assert "sandbox" in client.get(url, {"lihat": "1"})["Content-Security-Policy"]
    versi.mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    versi.save()
    assert client.get(url, {"lihat": "1"})["Content-Disposition"].startswith("attachment")
