from apps.standar.permissions import bisa_lihat_bab, queryset_bab_untuk


def queryset_bab_survei(user):
    """Mode survei bersifat baca saja; cakupan bab mengikuti hak lihat bab."""
    return queryset_bab_untuk(user)


def bisa_ekspor_bab(user, bab) -> bool:
    return bisa_lihat_bab(user, bab)
