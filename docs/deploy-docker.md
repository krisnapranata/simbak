# Deploy SIMBAK dengan Docker (server bersama + Nginx Proxy Manager)

```
Internet ──HTTPS──► Nginx Proxy Manager (proxy-npm-1, :80/:443, sertifikat)
                       │  http://<IP server>:8030
                       ▼
                    simbak_nginx (:8030 → 80)   file statis + unduhan aman (X-Accel)
                       │
                    simbak_web (Gunicorn :8000)  ── simbak_db (MariaDB 10.11)
                    simbak_jadwal                 kirim_pengingat setiap hari 06:00
```

Semua container, network, dan volume berawalan `simbak`, terpisah dari casemix, nentis, dll.
Hanya port **8030** yang dibuka ke host. Database tidak terbuka ke luar.

| Container | Isi |
|---|---|
| `simbak_db` | MariaDB 10.11, volume `simbak_db_data` |
| `simbak_web` | Django + Gunicorn; saat start otomatis `migrate` + `collectstatic` |
| `simbak_jadwal` | Penjadwal harian `kirim_pengingat` (pengganti cron) |
| `simbak_nginx` | Nginx internal, port host **8030** |

Volume: `simbak_db_data` (database), `simbak_media_private` (file bukti), `simbak_static`.

## 1. Pasang pertama kali

```bash
# di server
sudo mkdir -p /srv/simbak && sudo chown $USER: /srv/simbak
cd /srv/simbak
git clone <repo-simbak> .          # atau salin folder proyek (tanpa .venv, .env, media_private)

cp .env.db.example .env.db
cp .env.production.example .env.production
nano .env.db                        # isi password DB & root (huruf/angka saja)
nano .env.production                # isi SECRET_KEY, domain, DATABASE_URL (password sama!)
chmod 600 .env.db .env.production
```

Buat `SECRET_KEY` acak:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Bangun dan jalankan:
```bash
docker compose up -d --build
docker compose ps                   # tunggu simbak_web "healthy"
```
Bila muncul `failed to resolve reference "docker.io/library/simbak-web:latest"` (compose versi
lama yang mencoba menarik image sebelum membangunnya), jalankan
`docker compose build web && docker compose up -d`.

Data awal dan akun admin (**sekali saja**, jangan diulang setiap deploy karena fixture
menimpa grup/izin dan nama bab):
```bash
docker compose exec web python manage.py loaddata peran_awal bab_starkes_awal
docker compose exec web python manage.py createsuperuser
```

Uji dari server: `curl http://localhost:8030/sehat/` → `ok`.

## 2. Nginx Proxy Manager (http://<IP server>:81)

**Hosts → Proxy Hosts → Add Proxy Host**
- Domain Names: `simbak.<domain-rs>` (harus sama dengan `ALLOWED_HOSTS`)
- Scheme: `http` · Forward Hostname/IP: **IP LAN server** (bukan `localhost`, karena NPM
  berjalan di container lain) · Forward Port: **8030**
- Centang *Block Common Exploits*
- Tab **SSL**: Request a new SSL Certificate, *Force SSL*, *HTTP/2 Support*.
  Jangan centang *HSTS Subdomains* kecuali semua subdomain RS sudah HTTPS.
- Tab **Advanced** (custom Nginx configuration):
  ```nginx
  client_max_body_size 30m;
  proxy_read_timeout 180s;
  ```

NPM mengirim `X-Forwarded-Proto: https` dan `X-Real-IP`; SIMBAK memakainya untuk redirect
HTTPS, cookie aman, log unduhan, dan penguncian login (per username + IP).

> Uji coba sebelum domain siap: set `SECURE_SSL_REDIRECT=False` dan `COOKIE_SECURE=False`
> di `.env.production`, tambahkan IP server ke `ALLOWED_HOSTS` dan `http://<IP>:8030` ke
> `CSRF_TRUSTED_ORIGINS`, lalu `docker compose up -d`. Kembalikan ke `True` setelah domain HTTPS aktif.

Port 8030 (HTTP biasa) bisa dibuka siapa pun di LAN. Catatan: port yang dipublikasikan Docker
**tidak** tunduk pada aturan `ufw` biasa. Bila ingin pengguna wajib lewat HTTPS, hapus bagian
`ports:` di `simbak_nginx` dan sambungkan NPM ke network SIMBAK:
`docker network connect simbak_default proxy-npm-1`, lalu di NPM isi Forward Hostname
`simbak_nginx`, port `80`.

## 3. Pembaruan aplikasi

```bash
cd /srv/simbak
git pull
docker compose up -d --build        # migrasi otomatis saat simbak_web start
docker image prune -f
```

## 4. Perintah harian/berguna

```bash
docker compose logs -f web                      # log aplikasi
docker compose logs jadwal                      # jadwal pengingat berikutnya
docker compose exec web python manage.py kirim_pengingat --dry-run
docker compose exec web python manage.py impor_standar data/starkes.xlsx --dry-run
docker compose exec web python manage.py axes_reset   # buka kunci login
docker compose restart web
```

File Excel untuk impor via command harus ada di dalam container; lebih mudah lewat menu
**Kelola → Impor Standar** di aplikasi.

## 5. Backup (wajib, harian)

Database dan file bukti saling bergantung: backup **bersamaan**.

```bash
#!/bin/sh
# /srv/simbak/backup.sh — jalankan via cron host, mis. 0 1 * * * /srv/simbak/backup.sh
set -e
TGL=$(date +%F); TUJUAN=/srv/backup/simbak; mkdir -p $TUJUAN
cd /srv/simbak
. ./.env.db
docker compose exec -T db mariadb-dump --single-transaction -u root -p"$MARIADB_ROOT_PASSWORD" \
  "$MARIADB_DATABASE" | gzip > $TUJUAN/db-$TGL.sql.gz
docker run --rm -v simbak_media_private:/data:ro -v $TUJUAN:/backup alpine \
  tar czf /backup/file-$TGL.tar.gz -C /data .
find $TUJUAN -mtime +30 -delete      # simpan 30 hari
```
Salin `/srv/backup/simbak` ke lokasi lain (NAS/Nextcloud) dan enkripsi bila keluar server.

Pemulihan (uji berkala di server uji):
```bash
gunzip < db-TGL.sql.gz | docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" simbak
docker run --rm -v simbak_media_private:/data -v /srv/backup/simbak:/backup alpine \
  sh -c "cd /data && tar xzf /backup/file-TGL.tar.gz"
```

## 6. Catatan

- `data_contoh` ditolak di produksi (`DEBUG=False`); jangan dipakai di server produksi.
- `check --deploy` menyisakan peringatan HSTS `includeSubDomains`/`preload`: sengaja dimatikan
  (bisa memaksa HTTPS di subdomain RS lain). Aktifkan via `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
  bila semua subdomain sudah HTTPS.
- Gunicorn: `GUNICORN_WORKERS` (default 3) di `.env.production`; naikkan bila pengguna banyak.
