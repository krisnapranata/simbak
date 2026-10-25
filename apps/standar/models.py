import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.akun.models import Pokja
from apps.inti.models import ManagerAktifKode, ModelDasar
from apps.inti.storage import storage_privat


class JenisBukti(models.TextChoices):
    REGULASI = "R", "Regulasi"
    DOKUMEN = "D", "Dokumen"
    OBSERVASI = "O", "Observasi"
    WAWANCARA = "W", "Wawancara"
    SIMULASI = "S", "Simulasi"


class KelompokStandar(ModelDasar):
    kode = models.CharField("kode", max_length=20, unique=True)
    nama = models.CharField("nama", max_length=255)
    urutan = models.PositiveIntegerField("urutan", default=0)

    objects = ManagerAktifKode()

    class Meta:
        verbose_name = "kelompok standar"
        verbose_name_plural = "kelompok standar"
        ordering = ["urutan", "kode"]

    def __str__(self):
        return self.nama

    def natural_key(self):
        return (self.kode,)


class Bab(ModelDasar):
    kelompok = models.ForeignKey(
        KelompokStandar, verbose_name="kelompok", on_delete=models.PROTECT, related_name="bab"
    )
    kode = models.CharField("kode", max_length=20, unique=True)
    nama = models.CharField("nama", max_length=255)
    pokja = models.ForeignKey(
        Pokja,
        verbose_name="pokja",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bab",
    )
    urutan = models.PositiveIntegerField("urutan", default=0)

    objects = ManagerAktifKode()

    class Meta:
        verbose_name = "bab"
        verbose_name_plural = "bab"
        ordering = ["kelompok__urutan", "urutan", "kode"]

    def __str__(self):
        return f"{self.kode} – {self.nama}"

    def natural_key(self):
        return (self.kode,)


class Standar(ModelDasar):
    bab = models.ForeignKey(
        Bab, verbose_name="bab", on_delete=models.PROTECT, related_name="standar"
    )
    kode = models.CharField("kode", max_length=50)
    uraian = models.TextField("uraian")
    maksud_tujuan = models.TextField("maksud dan tujuan", blank=True)
    urutan = models.PositiveIntegerField("urutan", default=0)

    class Meta:
        verbose_name = "standar"
        verbose_name_plural = "standar"
        ordering = ["bab", "urutan", "kode"]
        constraints = [
            models.UniqueConstraint(fields=["bab", "kode"], name="standar_unik_per_bab"),
        ]

    def __str__(self):
        return self.kode


def validasi_jenis_bukti(nilai):
    if not isinstance(nilai, list) or not nilai:
        raise ValidationError("Jenis bukti harus berupa daftar berisi minimal satu kode.")
    salah = [k for k in nilai if k not in JenisBukti.values]
    if salah:
        raise ValidationError(f"Jenis bukti tidak dikenal: {', '.join(map(str, salah))}.")


class ElemenPenilaian(ModelDasar):
    standar = models.ForeignKey(
        Standar,
        verbose_name="standar",
        on_delete=models.PROTECT,
        related_name="elemen_penilaian",
    )
    kode = models.CharField("kode", max_length=50)
    uraian = models.TextField("uraian")
    jenis_bukti = models.JSONField(
        "jenis bukti",
        default=list,
        validators=[validasi_jenis_bukti],
        help_text="Daftar kode: R, D, O, W, S.",
    )
    urutan = models.PositiveIntegerField("urutan", default=0)

    class Meta:
        verbose_name = "elemen penilaian"
        verbose_name_plural = "elemen penilaian"
        ordering = ["standar", "urutan", "kode"]
        constraints = [
            models.UniqueConstraint(fields=["standar", "kode"], name="ep_unik_per_standar"),
        ]

    def __str__(self):
        return f"{self.standar.kode} EP {self.kode}"

    @property
    def label_jenis_bukti(self) -> list[str]:
        return [JenisBukti(k).label for k in self.jenis_bukti if k in JenisBukti.values]


class ItemWawancara(ModelDasar):
    elemen_penilaian = models.ForeignKey(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        on_delete=models.CASCADE,
        related_name="item_wawancara",
    )
    narasumber = models.CharField("narasumber", max_length=255, help_text="Jabatan narasumber.")
    daftar_pertanyaan = models.TextField("daftar pertanyaan", blank=True)

    class Meta:
        verbose_name = "item wawancara"
        verbose_name_plural = "item wawancara"
        ordering = ["elemen_penilaian", "id"]

    def __str__(self):
        return f"{self.elemen_penilaian} – {self.narasumber}"


def path_file_impor(instance, filename):
    return f"impor_standar/{uuid.uuid4().hex}.xlsx"


class LogImporStandar(models.Model):
    class Status(models.TextChoices):
        PRATINJAU = "pratinjau", "Menunggu konfirmasi"
        GAGAL_VALIDASI = "gagal_validasi", "Gagal validasi"
        BERHASIL = "berhasil", "Berhasil"
        DIBATALKAN = "dibatalkan", "Dibatalkan"

    class Sumber(models.TextChoices):
        WEB = "web", "Antarmuka web"
        CLI = "cli", "Perintah manage.py"

    diimpor_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="diimpor oleh",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="log_impor_standar",
    )
    sumber = models.CharField("sumber", max_length=10, choices=Sumber, default=Sumber.WEB)
    nama_file = models.CharField("nama file", max_length=255)
    file = models.FileField(
        "file sementara",
        storage=storage_privat,
        upload_to=path_file_impor,
        blank=True,
    )
    nonaktifkan_yang_hilang = models.BooleanField("nonaktifkan yang hilang", default=False)
    status = models.CharField("status", max_length=20, choices=Status, default=Status.PRATINJAU)
    ringkasan = models.JSONField("ringkasan", default=dict, blank=True)
    galat = models.JSONField("daftar error", default=list, blank=True)
    dinonaktifkan = models.JSONField("dinonaktifkan", default=list, blank=True)
    dibuat_pada = models.DateTimeField("dibuat pada", auto_now_add=True)
    selesai_pada = models.DateTimeField("selesai pada", null=True, blank=True)

    class Meta:
        verbose_name = "log impor standar"
        verbose_name_plural = "log impor standar"
        ordering = ["-dibuat_pada"]

    def __str__(self):
        return f"{self.nama_file} ({self.get_status_display()})"
