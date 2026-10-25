#!/bin/sh
# Titik masuk container SIMBAK.
#   web    : migrasi + collectstatic, lalu Gunicorn (hanya container ini yang migrasi)
#   jadwal : menjalankan `kirim_pengingat` setiap hari
#   lainnya: diteruskan apa adanya, mis. `docker compose run --rm web python manage.py ...`
set -e
cd /app

case "${1:-web}" in
  web)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput --verbosity 0
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --access-logfile - \
      --error-logfile -
    ;;
  jadwal)
    exec sh /app/deploy/jadwal.sh
    ;;
  *)
    exec "$@"
    ;;
esac
