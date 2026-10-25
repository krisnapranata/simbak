import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.akun.models import Pokja, Unit
from apps.inti.models import ModelDasar
from apps.inti.storage import storage_privat
from apps.standar.models import ElemenPenilaian, JenisBukti


class JenisDokumen(models.TextChoices):
    # Regulasi
    KEBIJAKAN = "kebijakan", "Kebijakan"
    PEDOMAN = "pedoman", "Pedoman"
    PANDUAN = "panduan", "Panduan"
    SPO = "spo", "SPO"
    PROGRAM = "program", "Program"
    SK = "sk", "SK Penetapan"
    REGULASI_LAINNYA = "regulasi_lainnya", "Regulasi lainnya"
    # Bukti pelaksanaan
    NOTULEN = "notulen", "Notulen"
    LAPORAN = "laporan", "Laporan"
    DAFTAR_HADIR = "daftar_hadir", "Daftar hadir"
    FORMULIR = "formulir", "Formulir terisi"
    FOTO = "foto", "Foto"
    VIDEO = "video", "Video"
    LAINNYA = "lainnya", "Bukti lainnya"


JENIS_REGULASI = frozenset(
    {
        JenisDokumen.KEBIJAKAN,
        JenisDokumen.PEDOMAN,
        JenisDokumen.PANDUAN,
        JenisDokumen.SPO,
        JenisDokumen.PROGRAM,
        JenisDokumen.SK,
        JenisDokumen.REGULASI_LAINNYA,
    }
)


# Jenis file yang aman ditampilkan langsung di browser (?lihat=1). File Office tetap diunduh.
MIME_PRATINJAU = frozenset({"application/pdf", "image/png", "image/jpeg", "video/mp4"})


class StatusDokumen(models.TextChoices):
    DRAFT = "draft", "Draft"
    DIAJUKAN = "diajukan", "Diajukan"
    DIVERIFIKASI_KOMITE = "diverifikasi_komite", "Diverifikasi komite"
    DISETUJUI = "disetujui", "Disetujui"
    DIKEMBALIKAN = "dikembalikan", "Dikembalikan"
    KEDALUWARSA = "kedaluwarsa", "Kedaluwarsa"
    DICABUT = "dicabut", "Dicabut"


def path_bukti(instance, filename):
    """Nama file acak per tahun/bulan; nama asli disimpan di `nama_file_asli`."""
    ext = Path(filename).suffix.lower()
    return f"bukti/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Dokumen(ModelDasar):
    nomor = models.CharField("nomor", max_length=100, blank=True)
    judul = models.CharField("judul", max_length=255)
    jenis_dokumen = models.CharField("jenis dokumen", max_length=30, choices=JenisDokumen)
    pokja = models.ForeignKey(
        Pokja, verbose_name="pokja", on_delete=models.PROTECT, related_name="dokumen"
    )
    unit = models.ForeignKey(
        Unit, verbose_name="unit", on_delete=models.PROTECT, null=True, blank=True
    )
    penanggung_jawab = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="penanggung jawab",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dokumen_dipegang",
    )
    tanggal_terbit = models.DateField("tanggal terbit", null=True, blank=True)
    tanggal_review_berikutnya = models.DateField("tanggal review berikutnya", null=True, blank=True)
    status = models.CharField(
        "status", max_length=30, choices=StatusDokumen, default=StatusDokumen.DRAFT
    )
    mengandung_data_pasien = models.BooleanField("mengandung data pasien", default=False)
    keterangan = models.TextField("keterangan", blank=True)
    versi_aktif = models.ForeignKey(
        "DokumenVersi",
        verbose_name="versi aktif",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        on_delete=models.PROTECT,
        related_name="dokumen_dibuat",
    )
    elemen_penilaian = models.ManyToManyField(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        through="BuktiEP",
        related_name="dokumen",
        blank=True,
    )

    class Meta:
        verbose_name = "dokumen"
        verbose_name_plural = "dokumen"
        ordering = ["-dibuat_pada"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["tanggal_review_berikutnya"]),
        ]

    def __str__(self):
        return f"{self.nomor} – {self.judul}" if self.nomor else self.judul

    @property
    def adalah_regulasi(self) -> bool:
        return self.jenis_dokumen in JENIS_REGULASI


class DokumenVersi(models.Model):
    dokumen = models.ForeignKey(
        Dokumen, verbose_name="dokumen", on_delete=models.CASCADE, related_name="versi"
    )
    nomor_versi = models.PositiveIntegerField("nomor versi")
    file = models.FileField("file", storage=storage_privat, upload_to=path_bukti, max_length=255)
    nama_file_asli = models.CharField("nama file asli", max_length=255)
    mime = models.CharField("MIME", max_length=150)
    ukuran = models.PositiveBigIntegerField("ukuran (byte)")
    sha256 = models.CharField("SHA-256", max_length=64, db_index=True)
    catatan_perubahan = models.TextField("catatan perubahan", blank=True)
    diunggah_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="diunggah oleh",
        on_delete=models.PROTECT,
        related_name="versi_diunggah",
    )
    diunggah_pada = models.DateTimeField("diunggah pada", auto_now_add=True)

    class Meta:
        verbose_name = "versi dokumen"
        verbose_name_plural = "versi dokumen"
        ordering = ["dokumen", "-nomor_versi"]
        constraints = [
            models.UniqueConstraint(fields=["dokumen", "nomor_versi"], name="versi_unik"),
        ]

    def __str__(self):
        return f"{self.dokumen} v{self.nomor_versi}"


class BuktiEP(models.Model):
    """Tautan dokumen ↔ elemen penilaian. Satu file dapat menjadi bukti banyak EP."""

    dokumen = models.ForeignKey(
        Dokumen, verbose_name="dokumen", on_delete=models.CASCADE, related_name="bukti"
    )
    elemen_penilaian = models.ForeignKey(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        on_delete=models.PROTECT,
        related_name="bukti",
    )
    jenis_bukti = models.CharField("jenis bukti", max_length=1, choices=JenisBukti)
    keterangan = models.CharField("keterangan", max_length=255, blank=True)
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ditautkan oleh",
        on_delete=models.PROTECT,
        related_name="+",
    )
    dibuat_pada = models.DateTimeField("ditautkan pada", auto_now_add=True)

    class Meta:
        verbose_name = "bukti EP"
        verbose_name_plural = "bukti EP"
        ordering = ["elemen_penilaian", "jenis_bukti"]
        constraints = [
            models.UniqueConstraint(
                fields=["dokumen", "elemen_penilaian", "jenis_bukti"], name="bukti_ep_unik"
            ),
        ]

    def __str__(self):
        return f"{self.elemen_penilaian} [{self.jenis_bukti}] ← {self.dokumen}"


class LogUnduhan(models.Model):
    """Catatan unduhan dokumen yang mengandung data pasien. Tidak dapat diubah dari UI."""

    versi = models.ForeignKey(
        DokumenVersi, verbose_name="versi", on_delete=models.PROTECT, related_name="unduhan"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="pengguna", on_delete=models.PROTECT
    )
    ip = models.GenericIPAddressField("alamat IP", null=True, blank=True)
    keterangan = models.CharField("keterangan", max_length=100, blank=True)
    waktu = models.DateTimeField("waktu", auto_now_add=True)

    class Meta:
        verbose_name = "log unduhan"
        verbose_name_plural = "log unduhan"
        ordering = ["-waktu"]

    def __str__(self):
        return f"{self.user} – {self.versi} ({self.waktu:%Y-%m-%d %H:%M})"
