# Operasional SIMBAK

## Tugas terjadwal (pengingat & kedaluwarsa)
Jalankan sekali sehari. Command ini menandai dokumen yang lewat tanggal review sebagai
`kedaluwarsa` dan mengirim pengingat H-90/H-60/H-30 (atur di Admin → Pengaturan sistem).

Linux (cron, pukul 06.00):
```cron
0 6 * * * cd /srv/simbak && .venv/bin/python manage.py kirim_pengingat >> /var/log/simbak/pengingat.log 2>&1
```
Windows Task Scheduler: Program `C:\simbak\.venv\Scripts\python.exe`,
argumen `manage.py kirim_pengingat`, *Start in* `C:\simbak`.

Uji dulu tanpa menyimpan: `python manage.py kirim_pengingat --dry-run`.

## Produksi di belakang Nginx
`.env` produksi:
```
DJANGO_SETTINGS_MODULE=config.settings.prod
DEBUG=False
ALLOWED_HOSTS=simbak.rs.local
CSRF_TRUSTED_ORIGINS=https://simbak.rs.local
UNDUH_X_ACCEL=True
URL_DASAR=https://simbak.rs.local
```
Potongan konfigurasi Nginx:
```nginx
client_max_body_size 30m;            # sedikit di atas UPLOAD_MAKS_MB

location /static/ { alias /srv/simbak/staticfiles/; }

# File bukti hanya dapat diakses lewat header X-Accel-Redirect dari Django.
location /_privat/ {
    internal;
    alias /srv/simbak/media_private/;
    add_header X-Content-Type-Options nosniff;
}

location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Jangan pernah membuat `location` publik ke folder `media_private/`.

Aplikasi dijalankan dengan Gunicorn (Linux) atau Waitress (Windows Server):
`gunicorn config.wsgi --bind 127.0.0.1:8000 --workers 3`. Sebelum go-live jalankan
`python manage.py check --deploy` dan `python manage.py collectstatic`.

Semua aset (Bootstrap, ikon, HTMX, font) sudah lokal di `static/vendor/`, jadi aplikasi
berjalan tanpa internet. `collectstatic` dengan `ManifestStaticFilesStorage` sudah diuji:
`@import` di `blue-glass.css` otomatis diubah ke nama ber-hash.

## Backup (wajib)
Harian, terenkripsi, disimpan di lokasi terpisah dari server aplikasi:
```bash
TGL=$(date +%F)
mysqldump --single-transaction -u simbak -p simbak | gzip > /backup/simbak-db-$TGL.sql.gz
tar czf /backup/simbak-file-$TGL.tar.gz -C /srv/simbak media_private
gpg --encrypt -r tim-it@rs.local /backup/simbak-*-$TGL.*   # lalu salin ke lokasi lain
```
Database dan folder `media_private/` harus dibackup **bersamaan**; keduanya saling bergantung.

Uji pemulihan minimal tiap 3 bulan di server uji:
1. `gunzip < simbak-db-TGL.sql.gz | mysql -u simbak -p simbak_uji`
2. Ekstrak `media_private` ke folder uji, arahkan `MEDIA_PRIVATE_ROOT` ke sana.
3. Login, buka beberapa dokumen, pastikan unduhan berhasil.

## Data awal setelah instalasi
```bash
python manage.py migrate
python manage.py loaddata peran_awal bab_starkes_awal
python manage.py createsuperuser
```
Lalu di Admin: isi **Pengaturan sistem**, **Kriteria predikat** (sesuai aturan lembaga
akreditasi), pokja per bab, dan buat **Periode akreditasi** yang aktif.
