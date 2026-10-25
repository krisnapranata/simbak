from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.inti.models import ManagerAktifKode, ModelDasar


class Unit(ModelDasar):
    kode = models.CharField("kode", max_length=30, unique=True)
    nama = models.CharField("nama", max_length=150)

    objects = ManagerAktifKode()

    class Meta:
        verbose_name = "unit"
        verbose_name_plural = "unit"
        ordering = ["nama"]

    def __str__(self):
        return self.nama

    def natural_key(self):
        return (self.kode,)


class Pokja(ModelDasar):
    kode = models.CharField("kode", max_length=30, unique=True)
    nama = models.CharField("nama", max_length=150)
    ketua = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ketua",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pokja_diketuai",
    )

    objects = ManagerAktifKode()

    class Meta:
        verbose_name = "pokja"
        verbose_name_plural = "pokja"
        ordering = ["kode"]

    def __str__(self):
        return f"{self.kode} – {self.nama}"

    def natural_key(self):
        return (self.kode,)


class User(AbstractUser):
    unit = models.ForeignKey(
        Unit,
        verbose_name="unit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pengguna",
    )
    pokja = models.ManyToManyField(Pokja, verbose_name="pokja", blank=True, related_name="anggota")
    aktif_sampai = models.DateTimeField(
        "aktif sampai",
        null=True,
        blank=True,
        help_text="Kosongkan untuk akun tanpa batas waktu. Wajib diisi untuk tamu surveior.",
    )

    class Meta:
        verbose_name = "pengguna"
        verbose_name_plural = "pengguna"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def masa_aktif_habis(self) -> bool:
        return self.aktif_sampai is not None and self.aktif_sampai <= timezone.now()
