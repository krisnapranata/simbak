from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.inti.models import ModelDasar
from apps.penilaian.models import PeriodeAkreditasi
from apps.standar.models import ElemenPenilaian


class RencanaPerbaikan(ModelDasar):
    """Perencanaan Perbaikan Strategis (PPS) pascasurvei per elemen penilaian."""

    class Status(models.TextChoices):
        RENCANA = "rencana", "Rencana"
        BERJALAN = "berjalan", "Berjalan"
        SELESAI = "selesai", "Selesai"

    periode = models.ForeignKey(
        PeriodeAkreditasi, verbose_name="periode", on_delete=models.PROTECT, related_name="pps"
    )
    elemen_penilaian = models.ForeignKey(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        on_delete=models.PROTECT,
        related_name="pps",
    )
    rekomendasi = models.TextField("rekomendasi surveior")
    rencana_kegiatan = models.TextField("rencana kegiatan", blank=True)
    indikator = models.TextField("indikator / target", blank=True)
    pj = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="penanggung jawab",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pps_dipegang",
    )
    tenggat = models.DateField("tenggat", null=True, blank=True)
    status = models.CharField("status", max_length=20, choices=Status, default=Status.RENCANA)
    catatan_progres = models.TextField("catatan progres", blank=True)
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        verbose_name = "rencana perbaikan"
        verbose_name_plural = "rencana perbaikan"
        ordering = ["tenggat", "id"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"PPS {self.elemen_penilaian}"

    @property
    def terlambat(self) -> bool:
        return (
            self.status != self.Status.SELESAI
            and self.tenggat is not None
            and self.tenggat < timezone.localdate()
        )
