from django.conf import settings
from django.db import models

from apps.dokumen.models import Dokumen, StatusDokumen


class LogVerifikasi(models.Model):
    """Riwayat transisi status dokumen. Hanya dibuat oleh `services.py`, tidak dapat diubah."""

    dokumen = models.ForeignKey(
        Dokumen, verbose_name="dokumen", on_delete=models.PROTECT, related_name="log_verifikasi"
    )
    dari_status = models.CharField("dari status", max_length=30, choices=StatusDokumen)
    ke_status = models.CharField("ke status", max_length=30, choices=StatusDokumen)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="oleh",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Kosong bila dilakukan sistem (mis. penandaan kedaluwarsa otomatis).",
    )
    catatan = models.TextField("catatan", blank=True)
    waktu = models.DateTimeField("waktu", auto_now_add=True)

    class Meta:
        verbose_name = "log verifikasi"
        verbose_name_plural = "log verifikasi"
        ordering = ["-waktu", "-id"]

    def __str__(self):
        return f"{self.dokumen}: {self.dari_status} → {self.ke_status}"


class Notifikasi(models.Model):
    """Notifikasi in-app. Hanya judul dan tautan; tidak pernah memuat isi dokumen."""

    penerima = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="penerima",
        on_delete=models.CASCADE,
        related_name="notifikasi",
    )
    judul = models.CharField("judul", max_length=255)
    url = models.CharField("tautan", max_length=255, blank=True)
    dibaca_pada = models.DateTimeField("dibaca pada", null=True, blank=True)
    dibuat_pada = models.DateTimeField("dibuat pada", auto_now_add=True)

    class Meta:
        verbose_name = "notifikasi"
        verbose_name_plural = "notifikasi"
        ordering = ["-dibuat_pada", "-id"]
        indexes = [models.Index(fields=["penerima", "dibaca_pada"])]

    def __str__(self):
        return self.judul


class PengingatTerkirim(models.Model):
    """Mencegah pengingat jatuh tempo yang sama terkirim berulang."""

    dokumen = models.ForeignKey(
        Dokumen, verbose_name="dokumen", on_delete=models.CASCADE, related_name="+"
    )
    ambang_hari = models.PositiveSmallIntegerField("ambang (hari)")
    tanggal_jatuh_tempo = models.DateField("tanggal jatuh tempo")
    dikirim_pada = models.DateTimeField("dikirim pada", auto_now_add=True)

    class Meta:
        verbose_name = "pengingat terkirim"
        verbose_name_plural = "pengingat terkirim"
        constraints = [
            models.UniqueConstraint(
                fields=["dokumen", "ambang_hari", "tanggal_jatuh_tempo"], name="pengingat_unik"
            )
        ]

    def __str__(self):
        return f"{self.dokumen} H-{self.ambang_hari}"
