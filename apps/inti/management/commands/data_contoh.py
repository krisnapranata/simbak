import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.inti import data_contoh


class Command(BaseCommand):
    help = (
        "Kelola data contoh untuk latihan: `isi`, `hapus`, atau `reset` (hapus lalu isi ulang). "
        "Hanya data contoh (demo.*, DEMO-*, '(contoh)', '[CONTOH]') yang dihapus."
    )

    def add_arguments(self, parser):
        parser.add_argument("aksi", choices=["isi", "hapus", "reset"])
        parser.add_argument(
            "--paksa", action="store_true", help="Izinkan dijalankan saat DEBUG=False."
        )
        parser.add_argument(
            "--kata-sandi",
            dest="kata_sandi",
            help="Kata sandi semua akun demo.*. Bawaan: SimbakContoh2026 di development, "
            "acak di produksi (ditampilkan sekali di akhir).",
        )

    def handle(self, *args, aksi, paksa, kata_sandi=None, **options):
        if not settings.DEBUG and not paksa:
            raise CommandError(
                "DEBUG=False (kemungkinan produksi). Tambahkan --paksa bila benar-benar yakin."
            )
        if aksi in ("hapus", "reset"):
            self.stdout.write("Menghapus data contoh…")
            hasil = data_contoh.hapus(log=self.stdout.write)
            if not any(hasil.values()):
                self.stdout.write("  (tidak ada data contoh)")
        if aksi in ("isi", "reset"):
            if not kata_sandi:
                # Sandi tetap yang tertulis di dokumentasi publik tidak boleh dipakai di server
                # yang dapat diakses dari luar.
                kata_sandi = data_contoh.PASSWORD if settings.DEBUG else secrets.token_urlsafe(12)
            if len(kata_sandi) < 10:
                raise CommandError("Kata sandi akun demo minimal 10 karakter.")
            self.stdout.write("Mengisi data contoh…")
            try:
                data_contoh.isi(log=lambda m: self.stdout.write(f"  {m}"), kata_sandi=kata_sandi)
            except data_contoh.DataContohSudahAda as e:
                raise CommandError(str(e)) from e
            self.stdout.write(
                self.style.SUCCESS(
                    f"Selesai. Login dengan akun demo.* (lihat docs/proses-bisnis.md), "
                    f"kata sandi: {kata_sandi}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Data contoh dihapus."))
