---
name: akreditasi-domain
description: Pengetahuan domain akreditasi rumah sakit Indonesia (STARKES), meliputi struktur bab, standar, elemen penilaian, jenis bukti R/D/O/W/S, skor, dan istilah. Gunakan saat merancang model data, logika penilaian, dashboard, atau label UI terkait akreditasi.
---

# Domain Akreditasi Rumah Sakit (STARKES)

## Sumber Acuan
- Keputusan Menteri Kesehatan No. HK.01.07/MENKES/1128/2022 tentang Standar Akreditasi Rumah Sakit.
- Instrumen survei dari lembaga independen penyelenggara akreditasi yang dipakai RS.

**Penting:** Regulasi dapat diperbarui. Jangan meng-hardcode isi standar, jumlah EP, atau kriteria kelulusan di kode.
Simpan semuanya di database (diimpor dari Excel, lihat skill `impor-standar`) atau di pengaturan.
Jika ragu tentang isi standar, tanyakan kepada pengguna. Jangan mengarang uraian standar.

## Hierarki
```
Kelompok Standar
 └─ Bab (kode singkat, mis. TKRS, PMKP, SKP)
     └─ Standar (mis. "TKRS 1")
         └─ Elemen Penilaian / EP (mis. "a", "b", atau "TKRS 1 EP a")
             └─ Bukti (dokumen, observasi, wawancara, simulasi)
```

## Kelompok dan Bab (STARKES 2022, verifikasi dengan dokumen resmi)
**Kelompok Manajemen Rumah Sakit**
- TKRS – Tata Kelola Rumah Sakit
- KPS – Kompetensi dan Kewenangan Staf
- MFK – Manajemen Fasilitas dan Keselamatan
- PPI – Pencegahan dan Pengendalian Infeksi
- PPK – Pendidikan dalam Pelayanan Kesehatan
- PMKP – Peningkatan Mutu dan Keselamatan Pasien
- MRMIK – Manajemen Rekam Medis dan Informasi Kesehatan

**Kelompok Pelayanan Berfokus pada Pasien**
- AKP – Akses dan Kontinuitas Pelayanan
- HPK – Hak Pasien dan Keluarga
- PP – Pengkajian Pasien
- PAP – Pelayanan dan Asuhan Pasien
- PAB – Pelayanan Anestesi dan Bedah
- PKPO – Pelayanan Kefarmasian dan Penggunaan Obat
- KE – Komunikasi dan Edukasi

**Kelompok Sasaran Keselamatan Pasien**
- SKP – Sasaran Keselamatan Pasien

**Kelompok Program Nasional**
- PROGNAS – Program Nasional (sesuaikan isinya dengan standar terbaru)

Daftar ini adalah **data awal (fixture/seed)**, bukan konstanta kode.

## Jenis Bukti (Telusur)
| Kode | Nama | Contoh bukti di sistem |
|---|---|---|
| R | Regulasi | Kebijakan, pedoman, panduan, SPO, program, SK |
| D | Dokumen | Bukti pelaksanaan: notulen, laporan, daftar hadir, formulir terisi, foto kegiatan |
| O | Observasi | Catatan atau foto hasil observasi lapangan, checklist observasi |
| W | Wawancara | Daftar narasumber (jabatan) dan pertanyaan, catatan hasil wawancara |
| S | Simulasi | Skenario simulasi, video atau foto, daftar peserta, evaluasi |

Satu EP dapat membutuhkan lebih dari satu jenis bukti. Simpan sebagai list (JSONField/ArrayField), bukan satu nilai.

```python
class JenisBukti(models.TextChoices):
    REGULASI = "R", "Regulasi"
    DOKUMEN = "D", "Dokumen"
    OBSERVASI = "O", "Observasi"
    WAWANCARA = "W", "Wawancara"
    SIMULASI = "S", "Simulasi"
```

## Jenis Dokumen
- Regulasi: Kebijakan, Pedoman, Panduan, SPO, Program, SK Penetapan, Lainnya.
- Bukti pelaksanaan: Notulen, Laporan, Daftar Hadir, Formulir, Foto, Video, Lainnya.

## Skor EP
| Nilai | Arti |
|---|---|
| 10 | Tercapai penuh |
| 5 | Tercapai sebagian |
| 0 | Tidak tercapai |
| `None` + flag `tdd=True` | Tidak dapat diterapkan — **dikeluarkan dari pembagi** |

Bedakan tiga keadaan: belum dinilai (tidak ada `PenilaianEP`), TDD, dan skor 0.

Rumus capaian (per standar, bab, pokja, atau total):
```
capaian (%) = jumlah skor EP yang dinilai / (jumlah EP yang dinilai dan bukan TDD × 10) × 100
```
Hitung dengan agregasi ORM (`Sum`, `Count` dengan `filter=Q(...)`), bukan loop Python.

Kriteria kelulusan dan predikat (mis. Paripurna, Utama, Madya, Dasar, Tidak Lulus) **disimpan di pengaturan/database**,
bukan di kode. Konfirmasikan angkanya ke pengguna atau tim mutu sebelum diisi.

## Istilah UI
- Pokja = Kelompok Kerja penanggung jawab bab
- Komite Mutu = verifikator internal
- Surveior = penilai dari lembaga akreditasi
- Telusur = proses penelusuran bukti oleh surveior
- PPS = Perencanaan Perbaikan Strategis (tindak lanjut rekomendasi survei)
- Penilaian mandiri / self-assessment = penilaian internal sebelum survei
- TDD = Tidak Dapat Diterapkan

## Aturan Bisnis Penting
1. Dokumen regulasi (R) ditinjau berkala. Simpan `tanggal_review_berikutnya`. Periode default dapat dikonfigurasi (mis. 3 tahun), tanyakan ke pengguna.
2. Bukti pelaksanaan (D) relevan untuk rentang waktu tertentu sebelum survei. Tampilkan peringatan jika bukti lebih tua dari batas yang dikonfigurasi terhadap `tanggal_survei` periode aktif.
3. EP dianggap **lengkap bukti** jika setiap jenis bukti yang diwajibkan EP punya minimal satu bukti berstatus `disetujui`.
4. Dashboard menampilkan: % kelengkapan bukti, % skor penilaian mandiri, jumlah dokumen per status, dokumen akan kedaluwarsa (30/60/90 hari), EP tanpa bukti.
