from apps.akun.peran import Peran
from apps.akun.permissions import adalah_super_admin, bisa_lihat_semua_bab, punya_peran

from .models import Bab


def queryset_bab_untuk(user):
    """Bab yang boleh dilihat user. Selalu dipakai di view list/detail bab."""
    if not user.is_authenticated:
        return Bab.objects.none()
    if bisa_lihat_semua_bab(user):
        return Bab.objects.all()
    return Bab.objects.filter(pokja__in=user.pokja.all())


def bisa_lihat_bab(user, bab) -> bool:
    return queryset_bab_untuk(user).filter(pk=bab.pk).exists()


def bisa_impor_standar(user) -> bool:
    return user.is_authenticated and (
        adalah_super_admin(user) or punya_peran(user, Peran.KOMITE_MUTU)
    )


def bisa_proses_log_impor(user, log) -> bool:
    """Konfirmasi/batal pratinjau impor hanya oleh pengunggahnya."""
    return bisa_impor_standar(user) and log.diimpor_oleh_id == user.pk
