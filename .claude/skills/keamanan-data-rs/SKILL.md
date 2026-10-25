---
name: keamanan-data-rs
description: Aturan keamanan untuk SIMBAK (Django) — upload dan unduh file bukti, dokumen berisi data pasien, hak akses, audit, setting produksi, dan kepatuhan UU PDP. Gunakan saat menyentuh upload/download file, autentikasi, izin, logging, atau konfigurasi deployment.
---

# Keamanan Data Rumah Sakit

Bukti akreditasi sering memuat data pasien (contoh rekam medis, laporan insiden, foto pelayanan) dan data staf.
Perlakukan sebagai data pribadi yang dilindungi (UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi)
serta aturan kerahasiaan rekam medis.

## 1. Penyimpanan File
- File bukti disimpan di storage privat, **di luar** `MEDIA_ROOT`/`STATIC_ROOT` yang dilayani publik:
  ```python
  # config/settings/base.py
  MEDIA_PRIVATE_ROOT = env.path("MEDIA_PRIVATE_ROOT", default=BASE_DIR / "media_private")
  STORAGES = {
      "default": {...},
      "privat": {
          "BACKEND": "django.core.files.storage.FileSystemStorage",
          "OPTIONS": {"location": MEDIA_PRIVATE_ROOT, "base_url": None},
      },
  }
  ```
  Field: `file = models.FileField(storage=storages["privat"], upload_to=path_bukti)`.
- `upload_to` menghasilkan nama acak (UUID) per tahun/bulan, **bukan** nama file asli. Nama asli disimpan di field `nama_file_asli`.
- Hitung dan simpan `sha256` setiap versi untuk integritas dan deteksi duplikat.
- Jangan pernah menghapus file versi lama secara otomatis.

## 2. Validasi Upload
- Ekstensi yang diizinkan (dapat dikonfigurasi): `pdf, docx, xlsx, pptx, jpg, jpeg, png, mp4`.
- Cek MIME asli dengan `python-magic` (bukan hanya `content_type` dari browser), harus cocok dengan ekstensi.
- Batas ukuran per file dari setting (mis. `UPLOAD_MAKS_MB = 25`); set juga `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE` dan `client_max_body_size` di Nginx.
- Tolak file makro (`.docm`, `.xlsm`), executable, dan arsip berisi executable.
- Opsional: pindai antivirus (ClamAV) sebelum file berstatus aktif.

## 3. Unduh File
- Hanya lewat view, contoh `dokumen/<pk>/versi/<versi_pk>/unduh/`:
  1. `login_required`
  2. cek `bisa_lihat_dokumen(user, dokumen)` → 404 jika tidak boleh (jangan bocorkan keberadaan)
  3. catat unduhan (siapa, kapan, IP) bila dokumen `mengandung_data_pasien`
  4. kirim `FileResponse(..., as_attachment=True, filename=nama_file_asli)`; di produksi gunakan header `X-Accel-Redirect` ke lokasi `internal` Nginx
- Header `Content-Disposition` aman, `X-Content-Type-Options: nosniff`.
- Jangan membuat URL publik/permanen ke file. Tautan berbagi untuk tamu surveior harus berbatas waktu (`django.core.signing.TimestampSigner`).

## 4. Data Pasien
- Field `mengandung_data_pasien` wajib diisi saat upload (default `True` untuk jenis bukti D/O bila ragu, dikonfirmasi pengguna).
- Tampilkan pengingat di form upload: sebisa mungkin samarkan identitas pasien (nama, No. RM, NIK, alamat) sebelum diunggah.
- Grup `tamu-surveior` tidak dapat melihat dokumen ini kecuali diberi izin eksplisit per periode survei.
- **Jangan pernah** memasukkan data pasien asli ke fixture, factory, test, seed, log, pesan error, atau commit git.
- Jangan menampilkan isi dokumen di notifikasi email; cukup judul dan tautan ke aplikasi.

## 5. Autentikasi & Akses
- Semua halaman wajib login, kecuali halaman login dan reset kata sandi.
- Password validator bawaan Django aktif; panjang minimal 10.
- Batasi percobaan login (`django-axes`).
- Sesi kedaluwarsa setelah tidak aktif (mis. `SESSION_COOKIE_AGE = 8 jam`, `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`).
- Akun `tamu-surveior` punya `aktif_sampai`; middleware/backend menolak login setelah tanggal tersebut.
- Pengecekan izin lewat `permissions.py`; queryset list selalu disaring per user (cegah IDOR — jangan andalkan menyembunyikan tombol).

## 6. Audit
- `django-auditlog` untuk perubahan model: Dokumen, DokumenVersi, BuktiEP, PenilaianEP, RencanaPerbaikan, User, Group.
- Log verifikasi status dan log unduhan dokumen sensitif disimpan terpisah dan tidak bisa diubah dari UI.
- Log aplikasi tidak boleh memuat isi file, password, token, atau data pasien.

## 7. Setting Produksi (`config/settings/prod.py`)
```python
DEBUG = False
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```
- Jalankan `python manage.py check --deploy` dan selesaikan semua peringatan.
- Gunakan Gunicorn/uWSGI (Linux) atau Waitress (Windows Server) di belakang Nginx/IIS dengan HTTPS.
- `.env` tidak masuk git; sediakan `.env.example` tanpa nilai rahasia.

## 8. Backup
- Backup harian database (`pg_dump`) dan folder `media_private`, terenkripsi, disimpan di lokasi terpisah.
- Uji pemulihan (restore) berkala. Dokumentasikan prosedurnya di `docs/backup.md`.

## Checklist Review Keamanan
- [ ] File baru tersimpan di storage privat dengan nama acak
- [ ] Validasi ekstensi + MIME + ukuran berjalan dan ada test-nya
- [ ] View unduh mengecek izin dan mengembalikan 404 untuk yang tidak berhak
- [ ] Queryset tersaring per user
- [ ] Tidak ada data pasien di test/fixture/log
- [ ] `check --deploy` bersih untuk setting produksi
