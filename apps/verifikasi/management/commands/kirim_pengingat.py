from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.penilaian.target import kirim_notifikasi_target
from apps.verifikasi.services import kirim_pengingat_jatuh_tempo, proses_kedaluwarsa


class Command(BaseCommand):
    help = (
        "Tandai dokumen yang melewati tanggal review sebagai kedaluwarsa, kirim pengingat "
        "jatuh tempo, dan beri tahu pokja yang targetnya tertinggal. Jalankan harian lewat "
        "cron / Windows Task Scheduler."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Tampilkan saja, tidak menyimpan/mengirim."
        )

    def handle(self, *args, dry_run, **options):
        hari_ini = timezone.localdate()
        with transaction.atomic():
            kedaluwarsa = proses_kedaluwarsa(hari_ini=hari_ini)
            pengingat = kirim_pengingat_jatuh_tempo(hari_ini=hari_ini)
            target = kirim_notifikasi_target(hari_ini=hari_ini)
            if dry_run:
                transaction.set_rollback(True)

        for d in kedaluwarsa:
            self.stdout.write(f"Kedaluwarsa: {d}")
        for d, ambang in pengingat:
            self.stdout.write(f"Pengingat H-{ambang}: {d}")
        for h in target:
            self.stdout.write(f"Target {h.label_status.lower()}: {h.target}")
        ringkas = (
            f"{len(kedaluwarsa)} dokumen kedaluwarsa, {len(pengingat)} pengingat, "
            f"{len(target)} target tertinggal dinotifikasi."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: {ringkas} Tidak ada yang disimpan."))
        else:
            self.stdout.write(self.style.SUCCESS(ringkas))
