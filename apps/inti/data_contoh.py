"""Data contoh untuk latihan/demo. Semua data dibuat lewat service aplikasi sehingga log
verifikasi, notifikasi, dan riwayat terisi seperti pemakaian nyata.

Penanda data contoh (dipakai saat menghapus, data asli tidak tersentuh):
- username diawali `demo.`, kode unit/pokja diawali `DEMO-`
- kode standar diakhiri ` (contoh)`, nama periode diawali `[CONTOH]`

Teks standar/EP adalah placeholder, BUKAN isi resmi STARKES. Tidak ada data pasien.
"""

import datetime
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

from apps.akun.models import Pokja, Unit, User
from apps.akun.peran import Peran
from apps.dokumen import services as dokumen_services
from apps.dokumen.models import BuktiEP, Dokumen, DokumenVersi, JenisDokumen, LogUnduhan
from apps.inti.utils import tambah_bulan
from apps.penilaian import services as penilaian_services
from apps.penilaian import target as target_svc
from apps.penilaian.models import CatatanPenilaian, PenilaianEP, PeriodeAkreditasi, TargetPokja
from apps.pps import services as pps_services
from apps.pps.models import RencanaPerbaikan
from apps.standar.models import Bab, ElemenPenilaian, ItemWawancara, LogImporStandar, Standar
from apps.verifikasi import services as verifikasi
from apps.verifikasi.models import LogVerifikasi, Notifikasi, PengingatTerkirim

PREFIX_USER = "demo."
PREFIX_KODE = "DEMO-"
SUFIKS_STANDAR = " (contoh)"
PREFIX_PERIODE = "[CONTOH]"
PASSWORD = "SimbakContoh2026"  # hanya untuk development; produksi memakai sandi acak

UNIT = [
    ("DEMO-IGD", "Instalasi Gawat Darurat (contoh)"),
    ("DEMO-RI", "Instalasi Rawat Inap (contoh)"),
    ("DEMO-FAR", "Instalasi Farmasi (contoh)"),
    ("DEMO-MUTU", "Komite Mutu (contoh)"),
]
# kode bab → kode pokja contoh
POKJA = {"TKRS": "DEMO-TKRS", "PMKP": "DEMO-PMKP", "SKP": "DEMO-SKP"}

# username, nama depan, peran, pokja (kode bab), unit
PENGGUNA = [
    ("demo.admin", "Admin Contoh", [Peran.SUPER_ADMIN], [], "DEMO-MUTU"),
    ("demo.direktur", "Direktur Contoh", [Peran.DIREKTUR], [], None),
    ("demo.komite", "Komite Mutu Contoh", [Peran.KOMITE_MUTU], [], "DEMO-MUTU"),
    ("demo.ketua.tkrs", "Ketua TKRS Contoh", [Peran.KETUA_POKJA], ["TKRS"], None),
    ("demo.anggota.tkrs", "Anggota TKRS Contoh", [Peran.ANGGOTA_POKJA], ["TKRS"], None),
    ("demo.ketua.pmkp", "Ketua PMKP Contoh", [Peran.KETUA_POKJA], ["PMKP"], "DEMO-MUTU"),
    ("demo.anggota.pmkp", "Anggota PMKP Contoh", [Peran.ANGGOTA_POKJA], ["PMKP"], "DEMO-MUTU"),
    ("demo.ketua.skp", "Ketua SKP Contoh", [Peran.KETUA_POKJA], ["SKP"], "DEMO-RI"),
    ("demo.anggota.skp", "Anggota SKP Contoh", [Peran.ANGGOTA_POKJA], ["SKP"], "DEMO-IGD"),
    ("demo.surveior", "Surveior Internal Contoh", [Peran.SURVEIOR_INTERNAL], [], None),
    ("demo.tamu", "Tamu Surveior Contoh", [Peran.TAMU_SURVEIOR], [], None),
]

# Per bab: 2 standar × 3 EP. Jenis bukti per EP (R/D/O/W/S).
POLA_EP = [["R"], ["R", "D"], ["D", "W"], ["R", "D", "O"], ["D", "S"], ["W"]]
# Skor penilaian mandiri per EP (None = biarkan belum dinilai)
POLA_SKOR = {
    "TKRS": [10, 10, 5, 10, 0, "tdd"],
    "PMKP": [10, 5, 5, None, 0, 10],
    "SKP": [10, 10, 10, 5, None, None],
}


class DataContohSudahAda(Exception):
    pass


def ada_data_contoh() -> bool:
    return User.objects.filter(username__startswith=PREFIX_USER).exists()


# ---------------------------------------------------------------------------
# File contoh
# ---------------------------------------------------------------------------


def _pdf(judul: str, catatan: str = "") -> SimpleUploadedFile:
    from weasyprint import HTML

    html = f"""<html><body style="font-family:sans-serif">
    <p style="color:#b91c1c;font-weight:bold">DOKUMEN CONTOH – BUKAN DOKUMEN RESMI</p>
    <h1>{judul}</h1><p>{catatan}</p>
    <p>Dibuat otomatis oleh SIMBAK pada {timezone.localtime():%d-%m-%Y %H:%M} untuk latihan.
    Tidak berisi data pasien.</p></body></html>"""
    nama = judul.lower().replace(" ", "_")[:60] + ".pdf"
    return SimpleUploadedFile(nama, HTML(string=html).write_pdf(), "application/pdf")


def _png(judul: str) -> SimpleUploadedFile:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 360), (240, 253, 250))
    ImageDraw.Draw(img).text((20, 20), f"FOTO CONTOH\n{judul}", fill=(15, 118, 110))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return SimpleUploadedFile(judul.lower().replace(" ", "_")[:60] + ".png", buf.getvalue())


# ---------------------------------------------------------------------------
# Isi
# ---------------------------------------------------------------------------


def _master(log, kata_sandi):
    if not Bab.objects.filter(kode__in=POKJA).count() == len(POKJA):
        call_command("loaddata", "bab_starkes_awal", verbosity=0)
        log("Data awal bab STARKES dimuat.")
    unit = {k: Unit.objects.create(kode=k, nama=n) for k, n in UNIT}
    pokja = {}
    for kode_bab, kode_pokja in POKJA.items():
        bab = Bab.objects.get(kode=kode_bab)
        pokja[kode_bab] = Pokja.objects.create(kode=kode_pokja, nama=f"Pokja {bab.nama} (contoh)")
        if bab.pokja_id is None:
            bab.pokja = pokja[kode_bab]
            bab.save(update_fields=["pokja", "diubah_pada"])

    from django.contrib.auth.models import Group

    user = {}
    for username, nama, peran, pokja_bab, kode_unit in PENGGUNA:
        u = User(
            username=username,
            first_name=nama,
            email=f"{username}@contoh.test",
            unit=unit.get(kode_unit),
            is_staff=Peran.SUPER_ADMIN in peran,
        )
        if Peran.TAMU_SURVEIOR in peran:
            u.aktif_sampai = timezone.now() + datetime.timedelta(days=30)
        u.set_password(kata_sandi)
        u.save()
        u.groups.set([Group.objects.get_or_create(name=p)[0] for p in peran])
        u.pokja.set([pokja[b] for b in pokja_bab])
        user[username] = u
    for kode_bab, p in pokja.items():
        p.ketua = user[f"demo.ketua.{kode_bab.lower()}"]
        p.save(update_fields=["ketua", "diubah_pada"])
    log(f"{len(unit)} unit, {len(pokja)} pokja, {len(user)} pengguna dibuat.")

    ep = {}
    for kode_bab in POKJA:
        bab = Bab.objects.get(kode=kode_bab)
        daftar = []
        for i in range(2):
            std = Standar.objects.create(
                bab=bab,
                kode=f"{kode_bab} {i + 1}{SUFIKS_STANDAR}",
                uraian=f"[CONTOH] Uraian standar {kode_bab} {i + 1} untuk latihan. "
                "Bukan teks resmi STARKES.",
                maksud_tujuan="[CONTOH] Maksud dan tujuan contoh.",
                urutan=900 + i,
            )
            for j in range(3):
                jenis = POLA_EP[i * 3 + j]
                e = ElemenPenilaian.objects.create(
                    standar=std,
                    kode="abc"[j],
                    uraian=f"[CONTOH] Elemen penilaian {'abc'[j]} – memerlukan bukti "
                    f"{', '.join(jenis)}.",
                    jenis_bukti=jenis,
                    urutan=j + 1,
                )
                if "W" in jenis:
                    ItemWawancara.objects.create(
                        elemen_penilaian=e,
                        narasumber="Kepala ruangan (contoh)",
                        daftar_pertanyaan="1. Pertanyaan contoh?\n2. Pertanyaan contoh lain?",
                    )
                daftar.append(e)
        ep[kode_bab] = daftar
    log("6 standar dan 18 elemen penilaian contoh dibuat (TKRS, PMKP, SKP).")
    return unit, pokja, user, ep


def _dokumen(unit, pokja, user, ep, log):
    """Dokumen dalam berbagai status workflow, dibuat lewat service yang sama dengan UI."""
    hari_ini = timezone.localdate()
    komite, direktur = user["demo.komite"], user["demo.direktur"]
    jumlah = 0

    def buat(kode_bab, judul, jenis, ep_jenis, *, file=None, pasien=False, terbit=None, **kw):
        nonlocal jumlah
        anggota = user[f"demo.anggota.{kode_bab.lower()}"]
        e, j = ep_jenis[0]
        dok = dokumen_services.buat_dokumen(
            user=anggota,
            data={
                "judul": judul,
                "nomor": f"CONTOH/{kode_bab}/{jumlah + 1:03d}",
                "jenis_dokumen": jenis,
                "pokja": pokja[kode_bab],
                "unit": kw.get("unit"),
                "penanggung_jawab": user[f"demo.ketua.{kode_bab.lower()}"],
                "tanggal_terbit": terbit or hari_ini - datetime.timedelta(days=60),
                "mengandung_data_pasien": pasien,
                "keterangan": "Dokumen contoh untuk latihan.",
            },
            file=file or _pdf(judul),
            ep=e,
            jenis_bukti=j,
        )
        for e2, j2 in ep_jenis[1:]:
            dokumen_services.tautkan_ep(dokumen=dok, ep=e2, jenis_bukti=j2, user=anggota)
        jumlah += 1
        return dok

    def sampai(dok, status, kode_bab, catatan=""):
        """Jalankan alur verifikasi sampai status yang diinginkan."""
        ketua = user[f"demo.ketua.{kode_bab.lower()}"]
        dok = verifikasi.ajukan(dokumen=dok, user=ketua, catatan="Mohon diverifikasi.")
        if status == "diajukan":
            return dok
        if status == "dikembalikan":
            return verifikasi.kembalikan(dokumen=dok, user=komite, catatan=catatan)
        dok = verifikasi.verifikasi(dokumen=dok, user=komite, catatan="Sesuai format.")
        if status == "diverifikasi_komite":
            return dok
        penyetuju = direktur if dok.adalah_regulasi else komite
        return verifikasi.setujui(dokumen=dok, user=penyetuju, catatan="Disetujui.")

    for kode_bab, daftar in ep.items():
        a, b, c, d, e, f = daftar  # jenis: R | R,D | D,W | R,D,O | D,S | W
        tua = tambah_bulan(hari_ini, -35)  # review jatuh tempo ±1 bulan lagi
        sampai(
            buat(
                kode_bab,
                f"Kebijakan {kode_bab} contoh",
                JenisDokumen.KEBIJAKAN,
                [(a, "R"), (b, "R"), (d, "R")],
                terbit=tua,
            ),
            "disetujui",
            kode_bab,
        )
        sampai(
            buat(
                kode_bab,
                f"Notulen rapat {kode_bab} contoh",
                JenisDokumen.NOTULEN,
                [(b, "D"), (c, "D")],
            ),
            "disetujui",
            kode_bab,
        )
        sampai(
            buat(kode_bab, f"Laporan bulanan {kode_bab} contoh", JenisDokumen.LAPORAN, [(d, "D")]),
            "diajukan",
            kode_bab,
        )
        sampai(
            buat(kode_bab, f"Pedoman {kode_bab} contoh", JenisDokumen.PEDOMAN, [(d, "R")]),
            "diverifikasi_komite",
            kode_bab,
        )
        sampai(
            buat(kode_bab, f"Panduan {kode_bab} contoh", JenisDokumen.PANDUAN, [(a, "R")]),
            "dikembalikan",
            kode_bab,
            catatan="Lengkapi tanda tangan direktur dan nomor SK.",
        )
        buat(
            kode_bab,
            f"Foto kegiatan {kode_bab} contoh",
            JenisDokumen.FOTO,
            [(d, "O")],
            file=_png(f"Foto kegiatan {kode_bab}"),
            pasien=True,
        )

    # Kasus khusus (cukup sekali)
    usang = buat(
        "PMKP",
        "Notulen lama PMKP contoh",
        JenisDokumen.NOTULEN,
        [(ep["PMKP"][4], "D")],
        terbit=tambah_bulan(hari_ini, -30),
    )
    sampai(usang, "disetujui", "PMKP")

    kedaluwarsa = buat(
        "SKP",
        "SPO SKP contoh (lama)",
        JenisDokumen.SPO,
        [(ep["SKP"][1], "R")],
        terbit=tambah_bulan(hari_ini, -40),
    )
    kedaluwarsa = sampai(kedaluwarsa, "disetujui", "SKP")
    verifikasi.tandai_kedaluwarsa(dokumen=kedaluwarsa)

    revisi = buat("TKRS", "SPO TKRS contoh berversi", JenisDokumen.SPO, [(ep["TKRS"][0], "R")])
    revisi = sampai(revisi, "disetujui", "TKRS")
    dokumen_services.unggah_versi(
        dokumen=revisi,
        user=user["demo.ketua.tkrs"],
        file=_pdf("SPO TKRS contoh berversi", "Versi 2: revisi."),
        catatan_perubahan="Revisi alur pelaporan.",
    )
    sampai(Dokumen.objects.get(pk=revisi.pk), "disetujui", "TKRS")

    buat(
        "SKP",
        "Formulir terisi SKP contoh (draft)",
        JenisDokumen.FORMULIR,
        [(ep["SKP"][3], "D")],
        pasien=True,
        unit=unit["DEMO-IGD"],
    )
    log(f"{jumlah} dokumen contoh dibuat dengan berbagai status workflow.")


def _penilaian(user, ep, log):
    hari_ini = timezone.localdate()
    periode = PeriodeAkreditasi(
        nama=f"{PREFIX_PERIODE} Akreditasi {hari_ini.year}",
        tanggal_mulai=tambah_bulan(hari_ini, -3),
        tanggal_survei=hari_ini + datetime.timedelta(days=120),
        status=PeriodeAkreditasi.Status.PENILAIAN_MANDIRI,
        aktif=True,
    )
    periode = penilaian_services.simpan_periode(user=user["demo.komite"], periode=periode)
    n = 0
    for kode_bab, daftar in ep.items():
        ketua = user[f"demo.ketua.{kode_bab.lower()}"]
        for e, nilai in zip(daftar, POLA_SKOR[kode_bab], strict=True):
            if nilai is None:
                continue
            penilaian_services.nilai_ep(
                user=ketua,
                periode=periode,
                ep=e,
                nilai=nilai,
                fakta_analisis="[CONTOH] Fakta dan analisis hasil telusur internal.",
            )
            n += 1
    penilaian_services.tambah_catatan(
        user=user["demo.surveior"],
        periode=periode,
        ep=ep["TKRS"][2],
        isi="Bukti wawancara belum ada notulennya.",
    )
    log(f"Periode aktif dibuat, {n} EP dinilai (sisanya sengaja belum dinilai).")
    return periode


def _pps(user, periode, log):
    komite = user["demo.komite"]
    n = pps_services.buat_dari_penilaian(user=komite, periode=periode)
    hari_ini = timezone.localdate()
    for i, p in enumerate(RencanaPerbaikan.objects.filter(periode=periode).order_by("id")):
        bab = p.elemen_penilaian.standar.bab.kode.lower()
        p.rekomendasi = "[CONTOH] Rekomendasi surveior: lengkapi bukti pelaksanaan."
        p.rencana_kegiatan = "Sosialisasi ulang dan audit kepatuhan bulanan."
        p.indikator = "Kepatuhan ≥ 90% selama 3 bulan berturut-turut."
        p.pj = user[f"demo.anggota.{bab}"]
        # satu terlambat, satu berjalan, sisanya rencana
        p.tenggat = hari_ini + datetime.timedelta(days=-10 if i == 0 else 30 * (i + 1))
        p.status = RencanaPerbaikan.Status.BERJALAN if i == 1 else RencanaPerbaikan.Status.RENCANA
        pps_services.simpan_pps(user=komite, pps=p)
    log(f"{n} rencana perbaikan (PPS) dibuat dari EP berskor 0/5.")


# (kode bab pokja, ukuran, target %, mulai H-, tenggat H+) — dipilih supaya keempat status muncul
POLA_TARGET = [
    ("TKRS", TargetPokja.Ukuran.PROGRES_PENILAIAN, 100, -60, 30),  # tercapai
    ("TKRS", TargetPokja.Ukuran.KELENGKAPAN_BUKTI, 100, -90, -5),  # terlambat
    ("PMKP", TargetPokja.Ukuran.KELENGKAPAN_BUKTI, 90, -60, 20),  # berisiko
    ("PMKP", TargetPokja.Ukuran.CAPAIAN_SKOR, 80, -30, 60),  # sesuai jadwal
    ("SKP", TargetPokja.Ukuran.KELENGKAPAN_BUKTI, 100, -10, 90),  # sesuai jadwal
    ("SKP", TargetPokja.Ukuran.CAPAIAN_SKOR, 80, -30, 60),  # tercapai
]


def _target(pokja, user, periode, log):
    hari_ini = timezone.localdate()
    for kode_bab, ukuran, nilai, mulai, tenggat in POLA_TARGET:
        target_svc.buat_target_banyak(
            user=user["demo.komite"],
            periode=periode,
            daftar_pokja=[pokja[kode_bab]],
            ukuran=ukuran,
            nilai_target=nilai,
            tanggal_mulai=hari_ini + datetime.timedelta(days=mulai),
            tenggat=hari_ini + datetime.timedelta(days=tenggat),
            keterangan="[CONTOH] Target bertahap persiapan survei.",
        )
    log(f"{len(POLA_TARGET)} target pokja dibuat (tercapai, sesuai jadwal, berisiko, terlambat).")


def isi(*, log=print, kata_sandi=PASSWORD):
    if ada_data_contoh():
        raise DataContohSudahAda("Data contoh sudah ada. Gunakan `reset` untuk mengulang.")
    # Email notifikasi tidak dikirim/ditampilkan saat mengisi data contoh.
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        with transaction.atomic():
            unit, pokja, user, ep = _master(log, kata_sandi)
            _dokumen(unit, pokja, user, ep, log)
            periode = _penilaian(user, ep, log)
            _pps(user, periode, log)
            _target(pokja, user, periode, log)


# ---------------------------------------------------------------------------
# Hapus
# ---------------------------------------------------------------------------


def _ids(qs):
    return list(qs.values_list("pk", flat=True))


@transaction.atomic
def hapus(*, log=print) -> dict[str, int]:
    """Hapus permanen SEMUA data contoh (berdasarkan penanda). Data asli tidak tersentuh."""
    user = _ids(User.objects.filter(username__startswith=PREFIX_USER))
    pokja = _ids(Pokja.semua.filter(kode__startswith=PREFIX_KODE))
    unit = _ids(Unit.semua.filter(kode__startswith=PREFIX_KODE))
    periode = _ids(PeriodeAkreditasi.semua.filter(nama__startswith=PREFIX_PERIODE))
    standar = _ids(Standar.semua.filter(kode__endswith=SUFIKS_STANDAR))
    ep = _ids(ElemenPenilaian.semua.filter(standar_id__in=standar))
    dok = _ids(Dokumen.semua.filter(Q(pokja_id__in=pokja) | Q(dibuat_oleh_id__in=user)))
    versi = DokumenVersi.objects.filter(dokumen_id__in=dok)

    hasil = {}

    def hapus_qs(nama, qs):
        hasil[nama] = qs.delete()[1].get(qs.model._meta.label, 0)

    hapus_qs("notifikasi", Notifikasi.objects.filter(penerima_id__in=user))
    hapus_qs("pengingat", PengingatTerkirim.objects.filter(dokumen_id__in=dok))
    hapus_qs(
        "log unduhan", LogUnduhan.objects.filter(Q(versi__dokumen_id__in=dok) | Q(user_id__in=user))
    )
    hapus_qs(
        "log verifikasi", LogVerifikasi.objects.filter(Q(dokumen_id__in=dok) | Q(user_id__in=user))
    )
    # Data asli yang kebetulan menunjuk data contoh: lepaskan kaitannya, jangan dihapus.
    RencanaPerbaikan.semua.filter(pj_id__in=user).exclude(dibuat_oleh_id__in=user).update(pj=None)
    Dokumen.semua.exclude(pk__in=dok).filter(penanggung_jawab_id__in=user).update(
        penanggung_jawab=None
    )
    Dokumen.semua.exclude(pk__in=dok).filter(unit_id__in=unit).update(unit=None)
    User.objects.exclude(pk__in=user).filter(unit_id__in=unit).update(unit=None)

    hapus_qs(
        "rencana perbaikan",
        RencanaPerbaikan.semua.filter(
            Q(periode_id__in=periode) | Q(elemen_penilaian_id__in=ep) | Q(dibuat_oleh_id__in=user)
        ),
    )
    hapus_qs(
        "target pokja",
        TargetPokja.semua.filter(
            Q(periode_id__in=periode) | Q(pokja_id__in=pokja) | Q(dibuat_oleh_id__in=user)
        ),
    )
    hapus_qs(
        "catatan penilaian",
        CatatanPenilaian.objects.filter(
            Q(periode_id__in=periode) | Q(elemen_penilaian_id__in=ep) | Q(penulis_id__in=user)
        ),
    )
    hapus_qs(
        "penilaian EP",
        PenilaianEP.objects.filter(
            Q(periode_id__in=periode) | Q(elemen_penilaian_id__in=ep) | Q(dinilai_oleh_id__in=user)
        ),
    )
    hapus_qs(
        "bukti EP",
        BuktiEP.objects.filter(
            Q(dokumen_id__in=dok) | Q(elemen_penilaian_id__in=ep) | Q(dibuat_oleh_id__in=user)
        ),
    )
    file = [v.file for v in versi]
    Dokumen.semua.filter(pk__in=dok).update(versi_aktif=None)
    hapus_qs("versi dokumen", versi)
    hapus_qs("dokumen", Dokumen.semua.filter(pk__in=dok))
    hapus_qs("item wawancara", ItemWawancara.semua.filter(elemen_penilaian_id__in=ep))
    hapus_qs("elemen penilaian", ElemenPenilaian.semua.filter(pk__in=ep))
    hapus_qs("standar", Standar.semua.filter(pk__in=standar))
    hapus_qs("periode", PeriodeAkreditasi.semua.filter(pk__in=periode))
    Bab.semua.filter(pokja_id__in=pokja).update(pokja=None)
    LogImporStandar.objects.filter(diimpor_oleh_id__in=user).delete()
    hapus_qs("pengguna", User.objects.filter(pk__in=user))
    hapus_qs("pokja", Pokja.semua.filter(pk__in=pokja))
    hapus_qs("unit", Unit.semua.filter(pk__in=unit))

    # File fisik dihapus setelah transaksi berhasil (pengecualian aturan "versi tidak pernah
    # dihapus": ini data latihan, bukan bukti akreditasi).
    transaction.on_commit(lambda: [f.delete(save=False) for f in file if f])
    for nama, n in hasil.items():
        if n:
            log(f"  {nama}: {n}")
    return hasil
