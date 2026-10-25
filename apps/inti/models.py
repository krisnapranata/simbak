from django.db import models


class ManagerAktif(models.Manager):
    """Manager default: menyaring baris yang sudah dihapus lunak."""

    def get_queryset(self):
        return super().get_queryset().filter(dihapus_pada__isnull=True)


class ManagerAktifKode(ManagerAktif):
    """Manager untuk master data dengan kunci alami `kode` (dipakai fixture)."""

    def get_by_natural_key(self, kode):
        return self.model.semua.get(kode=kode)


class ModelDasar(models.Model):
    """Model abstrak: timestamp + soft delete (`dihapus_pada`)."""

    dibuat_pada = models.DateTimeField("dibuat pada", auto_now_add=True)
    diubah_pada = models.DateTimeField("diubah pada", auto_now=True)
    dihapus_pada = models.DateTimeField("dihapus pada", null=True, blank=True, editable=False)

    objects = ManagerAktif()
    semua = models.Manager()  # noqa: DJ012 (manager kedua, bukan field)

    class Meta:
        abstract = True

    @property
    def aktif(self) -> bool:
        return self.dihapus_pada is None


class PengaturanSistem(models.Model):
    """Pengaturan yang dapat diubah tim mutu lewat admin (satu baris, pk=1)."""

    periode_review_regulasi_bulan = models.PositiveSmallIntegerField(
        "periode review regulasi (bulan)",
        default=36,
        help_text="Dipakai mengisi tanggal review berikutnya dokumen regulasi bila dikosongkan.",
    )
    batas_usia_bukti_bulan = models.PositiveSmallIntegerField(
        "batas usia bukti pelaksanaan (bulan)",
        default=12,
        help_text="Bukti pelaksanaan (D) yang terbit lebih lama dari ini sebelum tanggal survei "
        "diberi peringatan.",
    )
    hari_pengingat = models.CharField(
        "hari pengingat sebelum jatuh tempo",
        max_length=50,
        default="90,60,30",
        help_text="Daftar hari dipisah koma, mis. 90,60,30.",
    )

    class Meta:
        verbose_name = "pengaturan sistem"
        verbose_name_plural = "pengaturan sistem"

    def __str__(self):
        return "Pengaturan sistem"

    @classmethod
    def ambil(cls) -> "PengaturanSistem":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def daftar_hari_pengingat(self) -> list[int]:
        hasil = {int(x) for x in self.hari_pengingat.split(",") if x.strip().isdigit()}
        return sorted(hasil, reverse=True)
