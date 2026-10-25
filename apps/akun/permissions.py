from .peran import Peran


def nama_peran(user) -> frozenset[str]:
    """Nama grup user, di-cache pada objek user selama satu request."""
    if not user.is_authenticated:
        return frozenset()
    if not hasattr(user, "_cache_peran"):
        user._cache_peran = frozenset(user.groups.values_list("name", flat=True))
    return user._cache_peran


def punya_peran(user, *peran: Peran) -> bool:
    return bool(nama_peran(user) & set(peran))


def adalah_super_admin(user) -> bool:
    return user.is_superuser or punya_peran(user, Peran.SUPER_ADMIN)


def bisa_lihat_semua_bab(user) -> bool:
    """Peran yang boleh melihat seluruh bab, bukan hanya bab pokjanya."""
    return adalah_super_admin(user) or punya_peran(
        user,
        Peran.DIREKTUR,
        Peran.KOMITE_MUTU,
        Peran.SURVEIOR_INTERNAL,
        Peran.TAMU_SURVEIOR,
    )


def adalah_komite_atau_admin(user) -> bool:
    return adalah_super_admin(user) or punya_peran(user, Peran.KOMITE_MUTU)


def adalah_peran_pokja(user) -> bool:
    return punya_peran(user, Peran.KETUA_POKJA, Peran.ANGGOTA_POKJA)


def id_pokja_user(user) -> frozenset[int]:
    """ID pokja tempat user bergabung, di-cache pada objek user selama satu request."""
    if not user.is_authenticated:
        return frozenset()
    if not hasattr(user, "_cache_pokja"):
        user._cache_pokja = frozenset(user.pokja.values_list("id", flat=True))
    return user._cache_pokja


def anggota_pokja_dari(user, pokja_id) -> bool:
    """Ketua/anggota pokja yang tergabung di pokja tersebut."""
    return pokja_id is not None and adalah_peran_pokja(user) and pokja_id in id_pokja_user(user)


def ketua_pokja_dari(user, pokja_id) -> bool:
    return (
        pokja_id is not None
        and punya_peran(user, Peran.KETUA_POKJA)
        and pokja_id in id_pokja_user(user)
    )
