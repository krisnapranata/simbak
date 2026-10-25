---
name: impor-standar
description: Cara mengimpor dan memperbarui master standar akreditasi (Kelompok, Bab, Standar, Elemen Penilaian, jenis bukti) dari file Excel ke SIMBAK dengan openpyxl, lewat management command dan halaman admin. Gunakan saat membuat, mengubah, atau men-debug fitur impor standar.
---

# Impor Master Standar dari Excel

Isi standar STARKES **tidak diketik di kode**. Tim mutu mengisi template Excel, lalu diimpor.

## Format Template Excel
File: `data/template_starkes.xlsx`. Satu sheet `EP` (wajib), opsional sheet `Bab`.

**Sheet `Bab`**
| kode_kelompok | nama_kelompok | kode_bab | nama_bab | kode_pokja | urutan |
|---|---|---|---|---|---|
| KMRS | Kelompok Manajemen Rumah Sakit | TKRS | Tata Kelola Rumah Sakit | POKJA-TKRS | 1 |

**Sheet `EP`** (satu baris = satu elemen penilaian)
| kode_bab | kode_standar | uraian_standar | maksud_tujuan | kode_ep | uraian_ep | jenis_bukti | urutan |
|---|---|---|---|---|---|---|---|
| TKRS | TKRS 1 | (uraian standar) | (opsional) | a | (uraian EP) | R,D,W | 1 |

Aturan kolom:
- Baris pertama adalah header; nama header dicocokkan **tanpa peduli huruf besar/kecil dan spasi**.
- `jenis_bukti` dipisah koma, hanya boleh `R, D, O, W, S`.
- `uraian_standar` cukup diisi sekali per standar; baris berikutnya boleh kosong (diambil dari baris sebelumnya dengan kode standar sama).
- Kode disimpan apa adanya (hanya `strip()` spasi di ujung).

Sediakan juga perintah untuk membuat template kosong:
```bash
python manage.py buat_template_standar data/template_starkes.xlsx
```

## Management Command
`apps/standar/management/commands/impor_standar.py`
```bash
python manage.py impor_standar data/starkes.xlsx --dry-run      # validasi saja, tidak menyimpan
python manage.py impor_standar data/starkes.xlsx                 # simpan
python manage.py impor_standar data/starkes.xlsx --nonaktifkan-yang-hilang
```

Logika (taruh di `apps/standar/services.py`, command hanya memanggil):
1. Buka dengan `openpyxl.load_workbook(path, read_only=True, data_only=True)`.
2. **Validasi semua baris dulu**, kumpulkan error dengan nomor baris (mis. `Baris 15: jenis_bukti 'X' tidak dikenal`). Jika ada error, berhenti tanpa menyimpan apa pun.
3. Simpan dalam satu `transaction.atomic()` memakai `update_or_create` berdasarkan kunci alami:
   - Bab: `kode`
   - Standar: (`bab`, `kode`)
   - EP: (`standar`, `kode`)
4. **Jangan menghapus** standar/EP yang tidak ada di file, karena mungkin sudah punya bukti dan penilaian. Dengan `--nonaktifkan-yang-hilang`, tandai `aktif=False` (soft delete) dan laporkan daftarnya.
5. Cetak ringkasan: jumlah dibuat, diperbarui, tidak berubah, dinonaktifkan, dan error.

## Impor dari Antarmuka Web
- Halaman khusus `super-admin` dan `komite-mutu`: unggah file → tampilkan **pratinjau** (ringkasan + daftar error) → tombol konfirmasi untuk menyimpan.
- File unggahan impor disimpan sementara di storage privat dan dihapus setelah selesai.
- Catat siapa yang mengimpor, kapan, nama file, dan ringkasan hasil (model `LogImporStandar`).

## Test Wajib
`apps/standar/tests/test_impor.py`, buat file Excel kecil di `tmp_path` dengan openpyxl:
- Impor baru membuat Bab, Standar, EP dengan benar
- Impor ulang file sama → tidak ada duplikat (idempoten)
- Uraian EP diubah → terperbarui, ID tetap
- `jenis_bukti` tidak valid → error dengan nomor baris, tidak ada data tersimpan
- EP hilang dari file + `--nonaktifkan-yang-hilang` → dinonaktifkan, bukti terkait tetap ada
- `--dry-run` tidak menyimpan apa pun

## Catatan
- Isi standar resmi berasal dari dokumen Kemenkes / lembaga akreditasi. Jangan mengarang uraian standar atau EP untuk mengisi data contoh; gunakan teks placeholder seperti "Uraian EP contoh" di test dan fixture.
