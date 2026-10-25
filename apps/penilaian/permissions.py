from apps.akun.peran import Peran
from apps.akun.permissions import (
    adalah_komite_atau_admin,
    adalah_peran_pokja,
    id_pokja_user,
    ketua_pokja_dari,
    punya_peran,
)
from apps.standar.permissions import bisa_lihat_bab

from .models import TargetPokja


def bisa_kelola_periode(user) -> bool:
    return adalah_komite_atau_admin(user)


def bisa_nilai_bab(user, bab) -> bool:
    """Komite/admin untuk semua bab; ketua pokja untuk bab pokjanya."""
    return adalah_komite_atau_admin(user) or ketua_pokja_dari(user, bab.pokja_id)


def bisa_beri_catatan(user, bab) -> bool:
    return bisa_lihat_bab(user, bab) and (
        adalah_komite_atau_admin(user) or punya_peran(user, Peran.SURVEIOR_INTERNAL)
    )


def bisa_kelola_target(user) -> bool:
    """Target pokja ditetapkan komite mutu/admin."""
    return adalah_komite_atau_admin(user)


def queryset_target_untuk(user):
    """Direktur, komite, admin, dan surveior internal melihat semua target; pokja hanya
    target pokjanya. Tamu surveior tidak melihat target internal."""
    qs = TargetPokja.objects.all()
    if adalah_komite_atau_admin(user) or punya_peran(user, Peran.DIREKTUR, Peran.SURVEIOR_INTERNAL):
        return qs
    if adalah_peran_pokja(user):
        return qs.filter(pokja__in=id_pokja_user(user))
    return qs.none()
