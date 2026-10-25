#!/bin/sh
# Menjalankan `manage.py kirim_pengingat` setiap hari pada JAM_PENGINGAT (default 06:00,
# zona waktu TZ). Pengganti cron di dalam Docker. Kegagalan satu hari tidak menghentikan loop.
set -u
JAM="${JAM_PENGINGAT:-06:00}"
echo "Penjadwal SIMBAK aktif: kirim_pengingat setiap hari pukul $JAM ($TZ)"
while true; do
  sekarang=$(date +%s)
  berikut=$(date -d "today $JAM" +%s)
  if [ "$berikut" -le "$sekarang" ]; then
    berikut=$(date -d "tomorrow $JAM" +%s)
  fi
  echo "Berikutnya: $(date -d "@$berikut" '+%Y-%m-%d %H:%M')"
  sleep $((berikut - sekarang))
  python /app/manage.py kirim_pengingat || echo "kirim_pengingat gagal, dicoba lagi besok"
done
