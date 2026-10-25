"""Logika bisnis periode dan penilaian mandiri."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import CatatanPenilaian, PenilaianEP, PeriodeAkreditasi, SkorEP
from .permissions import bisa_beri_catatan, bisa_kelola_periode, bisa_nilai_bab

TDD = "tdd"


def periode_aktif() -> PeriodeAkreditasi | None:
    return PeriodeAkreditasi.objects.filter(aktif=True).first()


@transaction.atomic
def simpan_periode(*, user, periode: PeriodeAkreditasi) -> PeriodeAkreditasi:
    if not bisa_kelola_periode(user):
        raise PermissionDenied
    periode.save()
    if periode.aktif:
        PeriodeAkreditasi.objects.exclude(pk=periode.pk).update(aktif=False)
    return periode


@transaction.atomic
def aktifkan_periode(*, user, periode: PeriodeAkreditasi) -> PeriodeAkreditasi:
    """Hanya satu periode aktif pada satu waktu."""
    if not bisa_kelola_periode(user):
        raise PermissionDenied
    PeriodeAkreditasi.objects.exclude(pk=periode.pk).update(aktif=False)
    periode.aktif = True
    periode.save(update_fields=["aktif", "diubah_pada"])
    return periode


def _cek_boleh_nilai(user, periode, ep):
    if not bisa_nilai_bab(user, ep.standar.bab):
        raise PermissionDenied
    if periode.terkunci:
        raise ValidationError("Periode sudah selesai; penilaian tidak dapat diubah.")


@transaction.atomic
def nilai_ep(*, user, periode, ep, nilai, catatan="", fakta_analisis="") -> PenilaianEP | None:
    """`nilai`: 10/5/0, "tdd", atau None/"" untuk menghapus penilaian (kembali belum dinilai)."""
    _cek_boleh_nilai(user, periode, ep)
    if nilai in (None, ""):
        PenilaianEP.objects.filter(periode=periode, elemen_penilaian=ep).delete()
        return None
    if nilai == TDD:
        skor, tdd = None, True
    else:
        try:
            skor = int(nilai)
        except (TypeError, ValueError) as e:
            raise ValidationError("Skor tidak valid.") from e
        if skor not in SkorEP.values:
            raise ValidationError("Skor hanya boleh 10, 5, atau 0.")
        tdd = False
    penilaian, _ = PenilaianEP.objects.update_or_create(
        periode=periode,
        elemen_penilaian=ep,
        defaults={
            "skor": skor,
            "tdd": tdd,
            "catatan": catatan,
            "fakta_analisis": fakta_analisis,
            "dinilai_oleh": user,
        },
    )
    return penilaian


def tambah_catatan(*, user, periode, ep, isi) -> CatatanPenilaian:
    if not bisa_beri_catatan(user, ep.standar.bab):
        raise PermissionDenied
    if not isi.strip():
        raise ValidationError("Catatan tidak boleh kosong.")
    return CatatanPenilaian.objects.create(
        periode=periode, elemen_penilaian=ep, penulis=user, isi=isi.strip()
    )
