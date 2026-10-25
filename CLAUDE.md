# SIMBAK — Sistem Informasi Manajemen Bukti Akreditasi Rumah Sakit

> File ini dibaca otomatis oleh Claude Code. Isinya konteks proyek, aturan, dan arah pengembangan.

## Tujuan Proyek
Aplikasi web untuk mengelola bukti akreditasi rumah sakit berdasarkan **Standar Akreditasi Rumah Sakit (STARKES)**
Kemenkes RI, dengan fitur:
- Master standar: Kelompok → Bab → Standar → Elemen Penilaian (EP)
- Unggah dan versioning dokumen bukti (Regulasi, Dokumen, Observasi, Wawancara, Simulasi)
- Relasi satu dokumen ke banyak EP
- Alur verifikasi: Pokja → Komite Mutu → Direktur
- Penilaian mandiri (self-assessment) per periode akreditasi
- Dashboard capaian per bab dan per pokja
- Pengingat dokumen kedaluwarsa / jatuh tempo review
- Mode survei (akses baca untuk surveior)
- Rencana Perbaikan Strategis (PPS) pascasurvei

Detail domain akreditasi ada di skill `akreditasi-domain`. **Baca skill itu sebelum mengubah model data atau logika skor.**

## Stack Teknologi
- **Bahasa**: Python 3.12, dijalankan di **virtual environment (`venv`)** di folder `.venv/`
- **Framework**: Django 5.2 LTS
- **Database**: MySQL/MariaDB (dev: MariaDB 10.11 lokal, driver `mysqlclient`); PostgreSQL 16 tetap didukung lewat `DATABASE_URL`. Pakai `JSONField`, bukan `ArrayField`, agar portabel.
- **Konfigurasi**: `django-environ` (file `.env`, tidak di-commit)
- **Frontend**: Django Templates + HTMX (`django-htmx`) + **Bootstrap 5.3** + Bootstrap Icons. **Tanpa CDN**: semua aset lokal di `static/vendor/` (bootstrap, bootstrap-icons, htmx, font Inter).
- **Tema**: "Blue Glass" (terang) — `static/css/tema/blue-glass.css` meng-`@import` `mint-forest.css` sebagai basis struktur (sidebar navy hover-expand, topbar kaca, kartu, tabel). Kerangka di `templates/base.html` + `templates/partials/`. Komponen kecil SIMBAK di `static/css/simbak.css`. Jangan tulis literal `url` + kurung di komentar CSS (collectstatic gagal).
- **Form**: `django-crispy-forms` + `crispy-bootstrap5`
- **Peran & izin**: Django `Group` + `Permission` bawaan, ditambah aturan per-objek di `permissions.py` tiap app
- **Audit trail**: `django-auditlog`
- **Impor/Ekspor Excel**: `openpyxl`
- **PDF**: `weasyprint`
- **Tugas terjadwal (pengingat)**: management command dijalankan cron / Windows Task Scheduler (opsi lanjut: `django-q2`)
- **Testing**: `pytest` + `pytest-django` + `factory-boy`
- **Format & lint**: `ruff`

## Setup & Perintah Umum
Selalu aktifkan venv sebelum menjalankan perintah Python.

```bash
# sekali saja
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt   # produksi/Docker: requirements.txt
cp .env.example .env          # isi SECRET_KEY, DATABASE_URL, dll.
python manage.py migrate
python manage.py createsuperuser
python manage.py loaddata peran_awal          # grup & izin awal
python manage.py loaddata bab_starkes_awal    # kelompok & bab STARKES (data awal)

# harian
python manage.py runserver
pytest                          # jalankan test
ruff check . && ruff format .   # lint & format
python manage.py makemigrations && python manage.py migrate
python manage.py kirim_pengingat [--dry-run]  # kedaluwarsa + pengingat jatuh tempo (harian)
python manage.py buat_template_standar         # → data/template_starkes.xlsx
python manage.py impor_standar data/starkes.xlsx --dry-run
```

Aturan venv:
- Jangan pernah `pip install` di luar venv.
- Setiap menambah paket: `pip install <paket>` lalu perbarui `requirements.txt` (produksi) atau `requirements-dev.txt` (test/lint saja), versi dipin, mis. `Django==5.2.*`.
- Deploy produksi: Docker (`Dockerfile`, `docker-compose.yml`, `deploy/`), panduan di `docs/deploy-docker.md`.
- `.venv/`, `.env`, `media/`, dan `db.sqlite3` wajib ada di `.gitignore`.

## Struktur Proyek
```
simbak/                 # repo root
  manage.py
  requirements.txt
  .env.example
  config/               # settings, urls, wsgi/asgi
    settings/ base.py dev.py prod.py
  apps/
    inti/               # ModelDasar (soft delete), StoragePrivat, validasi upload, IzinMixin
    akun/               # User kustom, profil, unit, pokja
    standar/            # KelompokStandar, Bab, Standar, ElemenPenilaian, impor Excel
    dokumen/            # Dokumen, DokumenVersi, relasi ke EP, unduh aman
    penilaian/          # PeriodeAkreditasi, PenilaianEP, dashboard
    verifikasi/         # alur status, log verifikasi, notifikasi
    survei/             # mode survei, ekspor PDF/ZIP
    pps/                # Rencana Perbaikan Strategis
  templates/  static/
  media_private/        # file bukti (DI LUAR static/media publik)
  data/                 # Excel master standar (diisi tim mutu)
```

Tiap app punya pola file yang sama: `models.py`, `services.py`, `permissions.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `tests/`.

## Model Data Inti
| Model (app) | Field penting |
|---|---|
| `Unit` (akun) | nama, kode |
| `Pokja` (akun) | kode, nama, ketua (FK User) |
| `User` (akun) | AbstractUser + unit, pokja (M2M) |
| `KelompokStandar` (standar) | kode, nama, urutan |
| `Bab` (standar) | kelompok, kode (mis. TKRS), nama, pokja, urutan |
| `Standar` (standar) | bab, kode (mis. TKRS 1), uraian, maksud_tujuan |
| `ElemenPenilaian` (standar) | standar, kode, uraian, jenis_bukti (ArrayField/JSONField: R/D/O/W/S), urutan |
| `Dokumen` (dokumen) | nomor, judul, jenis_dokumen, unit, penanggung_jawab, tanggal_terbit, tanggal_review_berikutnya, status, mengandung_data_pasien, versi_aktif |
| `DokumenVersi` (dokumen) | dokumen, nomor_versi, file, nama_file_asli, mime, ukuran, sha256, catatan_perubahan, diunggah_oleh, diunggah_pada |
| `BuktiEP` (dokumen) | dokumen, elemen_penilaian, jenis_bukti, keterangan — model `through` untuk M2M |
| `PeriodeAkreditasi` (penilaian) | nama, tanggal_mulai, tanggal_survei, status, aktif |
| `PenilaianEP` (penilaian) | periode, elemen_penilaian, skor (10/5/0/None=TDD), catatan, fakta_analisis, dinilai_oleh, dinilai_pada |
| `LogVerifikasi` (verifikasi) | dokumen, dari_status, ke_status, user, catatan, waktu |
| `RencanaPerbaikan` (pps) | periode, elemen_penilaian, rekomendasi, rencana_kegiatan, indikator, pj, tenggat, status |
| `ItemWawancara` (standar) | elemen_penilaian, narasumber, daftar_pertanyaan |

Aturan:
- Gunakan **custom User model sejak migrasi pertama** (`AUTH_USER_MODEL = "akun.User"`).
- Relasi dokumen ↔ EP **many-to-many lewat `BuktiEP`**. Jangan menyalin file untuk EP berbeda.
- Versi lama dokumen **tidak pernah dihapus**. Upload baru membuat `DokumenVersi` baru dan memperbarui `versi_aktif`.
- Soft delete (field `dihapus_pada` + manager default yang menyaring) untuk dokumen dan master standar.
- Nilai tetap memakai `models.TextChoices` / `IntegerChoices` (`JenisBukti`, `StatusDokumen`, `SkorEP`, `JenisDokumen`).
- Kode standar dan EP disimpan apa adanya dari sumber resmi.
- `unique_together`/`UniqueConstraint`: (periode, elemen_penilaian) pada `PenilaianEP`; (dokumen, elemen_penilaian, jenis_bukti) pada `BuktiEP`.

## Peran & Hak Akses (Django Group)
| Grup | Hak |
|---|---|
| `super-admin` | semua, termasuk master standar dan pengguna |
| `direktur` | lihat semua, menyetujui final dokumen regulasi |
| `komite-mutu` | lihat semua, verifikasi dokumen, kelola periode dan penilaian |
| `ketua-pokja` | kelola dokumen dan penilaian pada bab pokjanya, ajukan verifikasi |
| `anggota-pokja` | unggah dan edit draft dokumen pada bab pokjanya |
| `surveior-internal` | baca saja (mode survei), beri catatan penilaian |
| `tamu-surveior` | baca saja mode survei, akun berbatas waktu, tanpa dokumen `mengandung_data_pasien` kecuali diizinkan |

- Semua pengecekan akses lewat fungsi di `apps/<app>/permissions.py` (mis. `bisa_edit_dokumen(user, dokumen)`), dipanggil dari view dan template tag. Jangan menulis `if user.groups...` tersebar di view.
- Semua view wajib login (`LoginRequiredMixin` / middleware login wajib).
- Queryset list selalu difilter sesuai hak akses user (pokja-nya), bukan hanya disembunyikan di template.

## Alur Status Dokumen
```
draft → diajukan → diverifikasi_komite → disetujui → (kedaluwarsa | dicabut)
           ↘ dikembalikan (dengan catatan) → draft
```
- Transisi hanya lewat `apps/verifikasi/services.py` (`ajukan()`, `verifikasi()`, `setujui()`, `kembalikan()`), di dalam `transaction.atomic()`.
- Setiap transisi membuat `LogVerifikasi`. Transisi tidak valid melempar `TransisiTidakValid`.

## Konvensi Kode
- **Nama model, field, label UI, dan URL dalam Bahasa Indonesia**; nama teknis (helper, variabel lokal) boleh Inggris, tapi konsisten per file.
- `verbose_name` diisi Bahasa Indonesia agar admin dan form rapi. `LANGUAGE_CODE = "id"`, `TIME_ZONE` sesuai lokasi RS (mis. `"Asia/Makassar"`).
- Logika bisnis di `services.py`, bukan di view, form, atau `save()` model.
- Class-based view untuk CRUD; HTMX untuk interaksi parsial (filter, tautkan EP, ubah skor).
- Hindari N+1: gunakan `select_related` / `prefetch_related`, terutama di dashboard dan mode survei.
- Setiap fitur baru wajib punya test pytest: akses sesuai peran + alur utama.
- Sebelum menyatakan pekerjaan selesai: `ruff check .`, `ruff format .`, `pytest`, `python manage.py makemigrations --check`.
- Jangan mengubah migrasi yang sudah diterapkan di produksi. Buat migrasi baru.

## Keamanan (WAJIB)
Ikuti skill `keamanan-data-rs`. Ringkasnya:
- File bukti disimpan di `MEDIA_PRIVATE_ROOT` (bukan `MEDIA_ROOT` publik), diunduh hanya lewat view yang mengecek izin (`FileResponse`, atau `X-Accel-Redirect` di Nginx untuk produksi).
- Validasi ekstensi, MIME (dengan `python-magic`), dan ukuran upload.
- Dokumen `mengandung_data_pasien` dibatasi aksesnya dan setiap unduhan dicatat.
- `DEBUG=False` di produksi, `SECRET_KEY` dari `.env`, cookie aman, HTTPS.
- Jangan pernah menaruh data pasien di fixture, test, log, atau pesan error.

## Roadmap
1. **Fase 1 – Fondasi**: setup proyek + venv, User kustom, grup/peran, Unit, Pokja, master standar + impor Excel
2. **Fase 2 – Bukti**: Dokumen, versioning, relasi ke EP, unduh aman
3. **Fase 3 – Penilaian & Dashboard**: periode, self-assessment, dashboard capaian
4. **Fase 4 – Workflow**: verifikasi berjenjang, notifikasi email/in-app, pengingat kedaluwarsa
5. **Fase 5 – Survei & PPS**: mode survei, ekspor per bab (PDF/ZIP), rencana perbaikan

Status: Fase 1–5 selesai (versi awal). Operasional (cron, Nginx, backup) di `docs/operasional.md`.

Kerjakan per fase. Sebelum mulai fase baru, buat rencana singkat dan minta konfirmasi pengguna.

## Skill yang Tersedia
- `akreditasi-domain` — istilah, struktur STARKES, aturan skor, dan jenis bukti
- `modul-django` — langkah standar membuat app/fitur baru (model → migrasi → service → permission → view/template → test)
- `keamanan-data-rs` — aturan upload, akses file, data pasien, UU PDP, dan setting produksi
- `impor-standar` — cara mengimpor master standar dan EP dari Excel
