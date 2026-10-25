from django.core.management.base import BaseCommand, CommandError

from apps.standar.services import ENTITAS, impor_standar_cli


class Command(BaseCommand):
    help = "Impor master standar (Kelompok, Bab, Standar, EP) dari file Excel."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path file .xlsx")
        parser.add_argument(
            "--dry-run", action="store_true", help="Validasi saja, tidak menyimpan."
        )
        parser.add_argument(
            "--nonaktifkan-yang-hilang",
            action="store_true",
            help="Nonaktifkan standar/EP (pada bab yang ada di file) yang tidak ada di file.",
        )

    def handle(self, *args, path, dry_run, nonaktifkan_yang_hilang, **options):
        hasil = impor_standar_cli(
            path=path, dry_run=dry_run, nonaktifkan_yang_hilang=nonaktifkan_yang_hilang
        )
        if hasil.galat:
            for g in hasil.galat:
                self.stderr.write(self.style.ERROR(g))
            raise CommandError(f"{len(hasil.galat)} error. Tidak ada data yang disimpan.")

        self.stdout.write(f"{'Entitas':<10} {'dibuat':>8} {'diperbarui':>11} {'tetap':>7}")
        for e in ENTITAS:
            r = hasil.ringkasan[e]
            self.stdout.write(f"{e:<10} {r['dibuat']:>8} {r['diperbarui']:>11} {r['tetap']:>7}")
        if hasil.dinonaktifkan:
            self.stdout.write(f"Dinonaktifkan ({len(hasil.dinonaktifkan)}):")
            for item in hasil.dinonaktifkan:
                self.stdout.write(f"  - {item}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: tidak ada data yang disimpan."))
        else:
            self.stdout.write(self.style.SUCCESS("Impor selesai."))
