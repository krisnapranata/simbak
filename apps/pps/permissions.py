from apps.akun.peran import Peran
from apps.akun.permissions import (
    adalah_komite_atau_admin,
    id_pokja_user,
    ketua_pokja_dari,
    punya_peran,
)
from apps.standar.models import ElemenPenilaian
from apps.standar.permissions import queryset_bab_untuk

from .models import RencanaPerbaikan


def queryset_pps_untuk(user):
    return RencanaPerbaikan.objects.filter(
        elemen_penilaian__standar__bab__in=queryset_bab_untuk(user)
    )


def bisa_kelola_pps_bab(user, bab) -> bool:
    return adalah_komite_atau_admin(user) or ketua_pokja_dari(user, bab.pokja_id)


def queryset_ep_pps(user):
    """EP yang boleh dibuatkan PPS oleh user."""
    if adalah_komite_atau_admin(user):
        return ElemenPenilaian.objects.all()
    if punya_peran(user, Peran.KETUA_POKJA):
        return ElemenPenilaian.objects.filter(standar__bab__pokja__in=id_pokja_user(user))
    return ElemenPenilaian.objects.none()


def bisa_buat_pps(user) -> bool:
    return adalah_komite_atau_admin(user) or punya_peran(user, Peran.KETUA_POKJA)


def bisa_edit_pps(user, pps) -> bool:
    return bisa_kelola_pps_bab(user, pps.elemen_penilaian.standar.bab)


def bisa_update_progres(user, pps) -> bool:
    """Penanggung jawab boleh memperbarui status dan progres PPS-nya."""
    return bisa_edit_pps(user, pps) or pps.pj_id == user.pk


def bisa_buat_pps_otomatis(user) -> bool:
    return adalah_komite_atau_admin(user)
