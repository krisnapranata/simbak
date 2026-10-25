from django.db.models import Q

from apps.akun.models import Pokja
from apps.akun.peran import Peran
from apps.akun.permissions import (
    adalah_komite_atau_admin,
    adalah_peran_pokja,
    adalah_super_admin,
    anggota_pokja_dari,
    id_pokja_user,
    ketua_pokja_dari,
    punya_peran,
)
from apps.standar.models import ElemenPenilaian

from .models import BuktiEP, Dokumen, StatusDokumen

STATUS_BISA_DIEDIT = frozenset({StatusDokumen.DRAFT, StatusDokumen.DIKEMBALIKAN})
STATUS_BISA_DIREVISI = frozenset({StatusDokumen.DISETUJUI, StatusDokumen.KEDALUWARSA})


def adalah_tamu(user) -> bool:
    return punya_peran(user, Peran.TAMU_SURVEIOR) and not (
        adalah_super_admin(user)
        or punya_peran(user, Peran.DIREKTUR, Peran.KOMITE_MUTU, Peran.SURVEIOR_INTERNAL)
    )


def tamu_boleh_data_pasien(user) -> bool:
    """Izin eksplisit untuk tamu surveior melihat dokumen berisi data pasien pada periode aktif."""
    from apps.penilaian.models import PeriodeAkreditasi

    return PeriodeAkreditasi.objects.filter(aktif=True, tamu_boleh_data_pasien=user).exists()


def queryset_dokumen_untuk(user):
    """Dokumen yang boleh dilihat user. Wajib dipakai di semua list/detail/unduh."""
    qs = Dokumen.objects.all()
    if not user.is_authenticated:
        return qs.none()
    if adalah_super_admin(user) or punya_peran(
        user, Peran.DIREKTUR, Peran.KOMITE_MUTU, Peran.SURVEIOR_INTERNAL
    ):
        return qs
    if punya_peran(user, Peran.TAMU_SURVEIOR):
        qs = qs.filter(status=StatusDokumen.DISETUJUI)
        if not tamu_boleh_data_pasien(user):
            qs = qs.filter(mengandung_data_pasien=False)
        return qs
    if adalah_peran_pokja(user):
        pokja = id_pokja_user(user)
        ditautkan = BuktiEP.objects.filter(elemen_penilaian__standar__bab__pokja__in=pokja).values(
            "dokumen_id"
        )
        return qs.filter(Q(pokja__in=pokja) | Q(pk__in=ditautkan))
    return qs.none()


def bisa_lihat_dokumen(user, dokumen) -> bool:
    return queryset_dokumen_untuk(user).filter(pk=dokumen.pk).exists()


def bisa_kelola_pokja(user, pokja_id) -> bool:
    """Boleh membuat/mengubah dokumen dan tautan bukti milik pokja ini."""
    return adalah_komite_atau_admin(user) or anggota_pokja_dari(user, pokja_id)


def queryset_pokja_kelola(user):
    if adalah_komite_atau_admin(user):
        return Pokja.objects.all()
    if adalah_peran_pokja(user):
        return Pokja.objects.filter(pk__in=id_pokja_user(user))
    return Pokja.objects.none()


def bisa_buat_dokumen(user) -> bool:
    return queryset_pokja_kelola(user).exists()


def bisa_edit_dokumen(user, dokumen) -> bool:
    return dokumen.status in STATUS_BISA_DIEDIT and bisa_kelola_pokja(user, dokumen.pokja_id)


def bisa_unggah_versi(user, dokumen) -> bool:
    """Versi baru pada draft, atau revisi dokumen yang sudah disetujui/kedaluwarsa
    (oleh komite/admin atau ketua pokja; status kembali ke draft)."""
    if bisa_edit_dokumen(user, dokumen):
        return True
    return dokumen.status in STATUS_BISA_DIREVISI and (
        adalah_komite_atau_admin(user) or ketua_pokja_dari(user, dokumen.pokja_id)
    )


def bisa_hapus_dokumen(user, dokumen) -> bool:
    if dokumen.status != StatusDokumen.DRAFT:
        return False
    return (
        adalah_komite_atau_admin(user)
        or ketua_pokja_dari(user, dokumen.pokja_id)
        or (dokumen.dibuat_oleh_id == user.pk and anggota_pokja_dari(user, dokumen.pokja_id))
    )


def queryset_ep_tautan(user):
    """EP yang boleh ditautkan ke bukti oleh user."""
    if adalah_komite_atau_admin(user):
        return ElemenPenilaian.objects.all()
    if adalah_peran_pokja(user):
        return ElemenPenilaian.objects.filter(standar__bab__pokja__in=id_pokja_user(user))
    return ElemenPenilaian.objects.none()


def bisa_tautkan_ep(user, dokumen, ep) -> bool:
    return (
        bisa_lihat_dokumen(user, dokumen)
        and dokumen.status != StatusDokumen.DICABUT
        and bisa_kelola_pokja(user, ep.standar.bab.pokja_id)
    )


def bisa_lepas_bukti(user, bukti) -> bool:
    return bisa_kelola_pokja(user, bukti.elemen_penilaian.standar.bab.pokja_id)


def bisa_unduh_versi(user, dokumen, versi) -> bool:
    """Tamu surveior hanya boleh mengunduh versi aktif."""
    if versi.dokumen_id != dokumen.pk or not bisa_lihat_dokumen(user, dokumen):
        return False
    return versi.pk == dokumen.versi_aktif_id or not adalah_tamu(user)
