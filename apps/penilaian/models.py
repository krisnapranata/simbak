from django.conf import settings
from django.db import models

from apps.akun.models import Pokja
from apps.inti.models import ModelDasar
from apps.standar.models import Bab, ElemenPenilaian


class SkorEP(models.IntegerChoices):
    TERCAPAI_PENUH = 10, "10 – Tercapai penuh"
    TERCAPAI_SEBAGIAN = 5, "5 – Tercapai sebagian"
    TIDAK_TERCAPAI = 0, "0 – Tidak tercapai"


class PeriodeAkreditasi(ModelDasar):
    class Status(models.TextChoices):
        PERSIAPAN = "persiapan", "Persiapan"
        PENILAIAN_MANDIRI = "penilaian_mandiri", "Penilaian mandiri"
        SURVEI = "survei", "Survei"
        SELESAI = "selesai", "Selesai"

    nama = models.CharField("nama", max_length=150)
    tanggal_mulai = models.DateField("tanggal mulai")
    tanggal_survei = models.DateField("tanggal survei", null=True, blank=True)
    status = models.CharField("status", max_length=30, choices=Status, default=Status.PERSIAPAN)
    aktif = models.BooleanField(
        "periode aktif", default=False, help_text="Hanya satu periode yang aktif."
    )
    tamu_boleh_data_pasien = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="tamu surveior yang boleh melihat dokumen berisi data pasien",
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "periode akreditasi"
        verbose_name_plural = "periode akreditasi"
        ordering = ["-tanggal_mulai"]

    def __str__(self):
        return self.nama

    @property
    def terkunci(self) -> bool:
        """Periode selesai tidak dapat dinilai ulang."""
        return self.status == self.Status.SELESAI


class PenilaianEP(models.Model):
    """Skor penilaian mandiri. Tanpa baris = belum dinilai; tdd=True = tidak dapat diterapkan."""

    periode = models.ForeignKey(
        PeriodeAkreditasi,
        verbose_name="periode",
        on_delete=models.PROTECT,
        related_name="penilaian",
    )
    elemen_penilaian = models.ForeignKey(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        on_delete=models.PROTECT,
        related_name="penilaian",
    )
    skor = models.PositiveSmallIntegerField("skor", choices=SkorEP, null=True, blank=True)
    tdd = models.BooleanField("tidak dapat diterapkan (TDD)", default=False)
    catatan = models.TextField("catatan", blank=True)
    fakta_analisis = models.TextField("fakta dan analisis", blank=True)
    dinilai_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="dinilai oleh", on_delete=models.PROTECT
    )
    dinilai_pada = models.DateTimeField("dinilai pada", auto_now=True)

    class Meta:
        verbose_name = "penilaian EP"
        verbose_name_plural = "penilaian EP"
        constraints = [
            models.UniqueConstraint(
                fields=["periode", "elemen_penilaian"], name="penilaian_unik_per_periode"
            ),
            models.CheckConstraint(
                condition=(models.Q(tdd=True, skor__isnull=True))
                | (models.Q(tdd=False, skor__isnull=False)),
                name="penilaian_skor_atau_tdd",
            ),
        ]

    def __str__(self):
        return f"{self.elemen_penilaian} = {'TDD' if self.tdd else self.skor}"


class CatatanPenilaian(models.Model):
    """Catatan surveior internal / komite pada EP dalam satu periode."""

    periode = models.ForeignKey(
        PeriodeAkreditasi, verbose_name="periode", on_delete=models.PROTECT, related_name="+"
    )
    elemen_penilaian = models.ForeignKey(
        ElemenPenilaian,
        verbose_name="elemen penilaian",
        on_delete=models.PROTECT,
        related_name="catatan_penilaian",
    )
    penulis = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="penulis", on_delete=models.PROTECT
    )
    isi = models.TextField("catatan")
    dibuat_pada = models.DateTimeField("dibuat pada", auto_now_add=True)

    class Meta:
        verbose_name = "catatan penilaian"
        verbose_name_plural = "catatan penilaian"
        ordering = ["dibuat_pada"]

    def __str__(self):
        return f"{self.elemen_penilaian} – {self.penulis}"


class KriteriaPredikat(models.Model):
    """Predikat kelulusan (mis. Paripurna/Utama/Madya). Angka diisi tim mutu sesuai aturan resmi.

    Predikat tercapai bila SEMUA syaratnya terpenuhi. Dievaluasi dari urutan terkecil (tertinggi).
    """

    nama = models.CharField("nama predikat", max_length=100)
    urutan = models.PositiveSmallIntegerField(
        "urutan", default=0, help_text="Predikat tertinggi diberi urutan terkecil."
    )
    keterangan = models.TextField("keterangan / dasar aturan", blank=True)

    class Meta:
        verbose_name = "kriteria predikat"
        verbose_name_plural = "kriteria predikat"
        ordering = ["urutan", "id"]

    def __str__(self):
        return self.nama


class SyaratPredikat(models.Model):
    """Contoh: minimal 12 bab dengan capaian ≥ 80%, atau bab tertentu wajib ≥ 80%."""

    kriteria = models.ForeignKey(
        KriteriaPredikat, verbose_name="kriteria", on_delete=models.CASCADE, related_name="syarat"
    )
    min_capaian = models.DecimalField("capaian minimal (%)", max_digits=5, decimal_places=2)
    min_jumlah_bab = models.PositiveSmallIntegerField(
        "jumlah bab minimal",
        null=True,
        blank=True,
        help_text="Jumlah bab yang harus mencapai capaian minimal. Kosong = semua bab.",
    )
    bab_wajib = models.ManyToManyField(
        Bab,
        verbose_name="bab wajib",
        blank=True,
        help_text="Bab yang wajib mencapai capaian minimal (opsional).",
    )

    class Meta:
        verbose_name = "syarat predikat"
        verbose_name_plural = "syarat predikat"

    def __str__(self):
        jumlah = self.min_jumlah_bab or "semua"
        return f"{jumlah} bab ≥ {self.min_capaian}%"


class TargetPokja(ModelDasar):
    """Target bertahap per pokja dalam satu periode, mis. "bukti lengkap 100% sebelum 30 Nov".

    Status (tercapai/sesuai jadwal/berisiko/terlambat) dihitung di `target.py` dari capaian
    terkini dibanding kemajuan linier yang diharapkan antara tanggal mulai dan tenggat.
    """

    class Ukuran(models.TextChoices):
        KELENGKAPAN_BUKTI = "kelengkapan_bukti", "Kelengkapan bukti (% EP lengkap)"
        PROGRES_PENILAIAN = "progres_penilaian", "Progres penilaian (% EP dinilai)"
        CAPAIAN_SKOR = "capaian_skor", "Capaian skor penilaian mandiri (%)"

    class Status(models.TextChoices):
        TERCAPAI = "tercapai", "Tercapai"
        SESUAI = "sesuai", "Sesuai jadwal"
        BERISIKO = "berisiko", "Berisiko"
        TERLAMBAT = "terlambat", "Terlambat"

    periode = models.ForeignKey(
        PeriodeAkreditasi, verbose_name="periode", on_delete=models.PROTECT, related_name="target"
    )
    pokja = models.ForeignKey(
        Pokja, verbose_name="pokja", on_delete=models.PROTECT, related_name="target"
    )
    ukuran = models.CharField("ukuran", max_length=30, choices=Ukuran)
    nilai_target = models.DecimalField(
        "target (%)", max_digits=5, decimal_places=2, help_text="0–100."
    )
    tanggal_mulai = models.DateField(
        "tanggal mulai", null=True, blank=True, help_text="Kosong = tanggal mulai periode."
    )
    tenggat = models.DateField("tenggat")
    keterangan = models.TextField("keterangan", blank=True)
    status_dinotifikasi = models.CharField(
        "status terakhir yang dinotifikasi",
        max_length=20,
        choices=Status,
        blank=True,
        editable=False,
    )
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        verbose_name = "target pokja"
        verbose_name_plural = "target pokja"
        ordering = ["tenggat", "pokja__kode"]
        constraints = [
            models.UniqueConstraint(
                fields=["periode", "pokja", "ukuran", "tenggat"], name="target_pokja_unik"
            ),
            models.CheckConstraint(
                condition=models.Q(nilai_target__gte=0, nilai_target__lte=100),
                name="target_pokja_0_100",
            ),
        ]

    def __str__(self):
        ukuran = self.get_ukuran_display()
        return f"{self.pokja.kode}: {ukuran} ≥ {self.nilai_target}% ({self.tenggat})"

    @property
    def mulai(self):
        return self.tanggal_mulai or self.periode.tanggal_mulai
