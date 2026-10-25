from django.db import models


class Peran(models.TextChoices):
    """Nama Django Group yang dipakai sebagai peran. Isi grup ada di fixture `peran_awal`."""

    SUPER_ADMIN = "super-admin", "Super Admin"
    DIREKTUR = "direktur", "Direktur"
    KOMITE_MUTU = "komite-mutu", "Komite Mutu"
    KETUA_POKJA = "ketua-pokja", "Ketua Pokja"
    ANGGOTA_POKJA = "anggota-pokja", "Anggota Pokja"
    SURVEIOR_INTERNAL = "surveior-internal", "Surveior Internal"
    TAMU_SURVEIOR = "tamu-surveior", "Tamu Surveior"
