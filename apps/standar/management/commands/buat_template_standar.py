from pathlib import Path

from django.core.management.base import BaseCommand

from apps.standar.services import buat_template_workbook


class Command(BaseCommand):
    help = "Buat template Excel kosong untuk impor master standar."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default="data/template_starkes.xlsx")

    def handle(self, *args, path, **options):
        tujuan = Path(path)
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        buat_template_workbook().save(tujuan)
        self.stdout.write(self.style.SUCCESS(f"Template dibuat: {tujuan}"))
