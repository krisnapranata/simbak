from django.db.models import Q

from apps.akun.peran import Peran
from apps.akun.permissions import (
    adalah_komite_atau_admin,
    adalah_super_admin,
    id_pokja_user,
    ketua_pokja_dari,
    punya_peran,
)
from apps.dokumen.models import JENIS_REGULASI, StatusDokumen
from apps.dokumen.permissions import bisa_kelola_pokja, queryset_dokumen_untuk


def bisa_ajukan(user, dokumen) -> bool:
    return adalah_komite_atau_admin(user) or ketua_pokja_dari(user, dokumen.pokja_id)


def bisa_verifikasi(user, dokumen) -> bool:
    return adalah_komite_atau_admin(user)


def bisa_setujui(user, dokumen) -> bool:
    """Regulasi disetujui final oleh direktur; bukti pelaksanaan cukup oleh komite mutu."""
    if adalah_super_admin(user) or punya_peran(user, Peran.DIREKTUR):
        return True
    return not dokumen.adalah_regulasi and punya_peran(user, Peran.KOMITE_MUTU)


def bisa_kembalikan(user, dokumen) -> bool:
    if dokumen.status == StatusDokumen.DIAJUKAN:
        return bisa_verifikasi(user, dokumen)
    return bisa_setujui(user, dokumen)


def bisa_kembali_ke_draft(user, dokumen) -> bool:
    return bisa_kelola_pokja(user, dokumen.pokja_id)


def bisa_mulai_revisi(user, dokumen) -> bool:
    return adalah_komite_atau_admin(user) or ketua_pokja_dari(user, dokumen.pokja_id)


def bisa_cabut(user, dokumen) -> bool:
    return adalah_komite_atau_admin(user) or punya_peran(user, Peran.DIREKTUR)


def queryset_antrian_untuk(user):
    """Dokumen yang menunggu tindakan user."""
    kondisi = Q(pk__in=[])
    if adalah_komite_atau_admin(user):
        kondisi |= Q(status=StatusDokumen.DIAJUKAN)
        kondisi |= Q(status=StatusDokumen.DIVERIFIKASI_KOMITE) & ~Q(
            jenis_dokumen__in=JENIS_REGULASI
        )
    if adalah_super_admin(user) or punya_peran(user, Peran.DIREKTUR):
        kondisi |= Q(status=StatusDokumen.DIVERIFIKASI_KOMITE)
    if punya_peran(user, Peran.KETUA_POKJA):
        kondisi |= Q(
            status__in=[StatusDokumen.DRAFT, StatusDokumen.DIKEMBALIKAN],
            pokja__in=id_pokja_user(user),
        )
    return queryset_dokumen_untuk(user).filter(kondisi)
