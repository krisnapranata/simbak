"""Mode survei: telusur bukti per bab dan ekspor PDF/ZIP (hanya dokumen disetujui)."""

import re
import tempfile
import zipfile

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.template.loader import render_to_string
from django.utils import timezone

from apps.dokumen.models import BuktiEP, StatusDokumen
from apps.dokumen.permissions import queryset_dokumen_untuk
from apps.dokumen.services import catat_unduhan
from apps.penilaian.capaian import capaian_per_bab
from apps.penilaian.models import PenilaianEP
from apps.standar.models import ElemenPenilaian, ItemWawancara, Standar
from apps.standar.permissions import queryset_bab_untuk

from .permissions import bisa_ekspor_bab


def data_telusur_bab(*, bab, periode, user) -> list[Standar]:
    """Standar → EP beserta bukti disetujui yang boleh dilihat user, skor mandiri, dan wawancara."""
    bukti = (
        BuktiEP.objects.filter(
            dokumen__in=queryset_dokumen_untuk(user), dokumen__status=StatusDokumen.DISETUJUI
        )
        .select_related("dokumen__versi_aktif")
        .order_by("jenis_bukti", "dokumen__judul")
    )
    ep_qs = ElemenPenilaian.objects.order_by("urutan", "kode").prefetch_related(
        Prefetch("bukti", queryset=bukti, to_attr="bukti_survei"),
        Prefetch(
            "penilaian",
            queryset=PenilaianEP.objects.filter(periode=periode),
            to_attr="penilaian_periode",
        ),
        Prefetch("item_wawancara", queryset=ItemWawancara.objects.all(), to_attr="wawancara"),
    )
    daftar = list(
        Standar.objects.filter(bab=bab)
        .order_by("urutan", "kode")
        .prefetch_related(Prefetch("elemen_penilaian", queryset=ep_qs, to_attr="daftar_ep"))
    )
    for std in daftar:
        for ep in std.daftar_ep:
            ep.nilai = ep.penilaian_periode[0] if ep.penilaian_periode else None
            ada = {b.jenis_bukti for b in ep.bukti_survei}
            ep.jenis_kurang = [j for j in ep.jenis_bukti if j not in ada]
    return daftar


def konteks_bab(*, bab, periode, user) -> dict:
    cap = capaian_per_bab(periode=periode, bab_qs=queryset_bab_untuk(user).filter(pk=bab.pk))
    return {
        "bab": bab,
        "periode": periode,
        "daftar_standar": data_telusur_bab(bab=bab, periode=periode, user=user),
        "capaian_bab": cap[0][1] if cap else None,
        "dicetak_pada": timezone.localtime(),
        "dicetak_oleh": user,
    }


def buat_pdf(*, bab, periode, user) -> bytes:
    """Ringkasan telusur per bab. Hanya metadata bukti, tidak menyertakan isi file."""
    from weasyprint import HTML

    if not bisa_ekspor_bab(user, bab):
        raise PermissionDenied
    html = render_to_string("survei/pdf_bab.html", konteks_bab(bab=bab, periode=periode, user=user))
    return HTML(string=html).write_pdf()


def _aman(teks: str) -> str:
    """Komponen path ZIP yang aman (tanpa pemisah folder / traversal)."""
    teks = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", teks).strip(" .")
    return teks[:120] or "_"


def buat_zip(*, bab, periode, user, ip=None):
    """ZIP berisi PDF ringkasan + file versi aktif setiap bukti disetujui, per standar/EP/jenis.

    Mengembalikan file sementara (sudah di-seek ke awal). Unduhan dokumen berisi data pasien
    dicatat satu kali per versi.
    """
    if not bisa_ekspor_bab(user, bab):
        raise PermissionDenied
    daftar = data_telusur_bab(bab=bab, periode=periode, user=user)
    tmp = tempfile.TemporaryFile()
    tercatat = set()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as arsip:
        arsip.writestr(
            f"{_aman(bab.kode)}_ringkasan.pdf", buat_pdf(bab=bab, periode=periode, user=user)
        )
        for std in daftar:
            for ep in std.daftar_ep:
                for b in ep.bukti_survei:
                    versi = b.dokumen.versi_aktif
                    if versi is None:
                        continue
                    path = "/".join(
                        [
                            _aman(std.kode),
                            _aman(f"EP {ep.kode}"),
                            b.jenis_bukti,
                            _aman(f"{b.dokumen.pk}_v{versi.nomor_versi}_{versi.nama_file_asli}"),
                        ]
                    )
                    with versi.file.open("rb") as f:
                        with arsip.open(path, "w") as tujuan:
                            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                                tujuan.write(chunk)
                    if b.dokumen.mengandung_data_pasien and versi.pk not in tercatat:
                        versi.dokumen = b.dokumen
                        catat_unduhan(versi=versi, user=user, ip=ip, keterangan="ekspor ZIP")
                        tercatat.add(versi.pk)
    tmp.seek(0)
    return tmp
