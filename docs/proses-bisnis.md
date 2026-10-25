# Proses Bisnis SIMBAK (untuk pengembang)

## Gambaran besar
Rumah sakit diakreditasi dengan **STARKES**: ±16 **bab** (TKRS, PMKP, SKP, …). Tiap bab berisi
**standar**, tiap standar berisi **elemen penilaian (EP)**. Surveior menilai setiap EP dengan
memeriksa **bukti**. Setiap EP menyebut jenis bukti yang diminta:

| Kode | Jenis | Contoh |
|---|---|---|
| R | Regulasi | kebijakan, SPO, pedoman, SK |
| D | Dokumen pelaksanaan | notulen, laporan, daftar hadir |
| O | Observasi | foto/checklist lapangan |
| W | Wawancara | daftar narasumber + pertanyaan |
| S | Simulasi | video/skenario latihan |

Tiap bab dipegang satu **pokja** (kelompok kerja). Tugas RS sebelum survei:
**kumpulkan bukti → verifikasi → nilai diri sendiri → perbaiki yang kurang → hadapi survei
→ tindak lanjuti rekomendasi.** SIMBAK mendukung seluruh siklus itu.

```
 Tim mutu impor standar (Excel)
          │
          ▼
 Anggota pokja unggah bukti ──► tautkan ke EP (1 file → banyak EP)
          │
          ▼
 Ketua pokja AJUKAN ──► Komite mutu VERIFIKASI ──► Direktur SETUJUI (regulasi)
          ▲                     │                    Komite SETUJUI (bukti lain)
          └── dikembalikan ◄────┘ (dengan catatan)
          │
          ▼
 Ketua pokja NILAI MANDIRI tiap EP (10 / 5 / 0 / TDD) dalam satu PERIODE
          │
          ▼
 Dashboard: capaian %, kelengkapan bukti, jatuh tempo, predikat
          │
          ▼
 Survei (mode baca, ekspor PDF/ZIP) ──► PPS (rencana perbaikan) per EP
```

## Peran dan kode yang menangani
| Peran (grup) | Pekerjaan sehari-hari | Di kode |
|---|---|---|
| anggota-pokja | unggah/edit draft bukti bab pokjanya | `dokumen/services.py` |
| ketua-pokja | ajukan verifikasi, nilai mandiri, buat PPS bab pokjanya | `verifikasi.ajukan`, `penilaian.nilai_ep` |
| komite-mutu | verifikasi dokumen, kelola periode, impor standar, setujui bukti non-regulasi | `verifikasi.verifikasi/setujui` |
| direktur | persetujuan final dokumen **regulasi** | `verifikasi.setujui` |
| surveior-internal | baca semua, beri catatan pada EP | `penilaian.tambah_catatan` |
| tamu-surveior | baca dokumen disetujui saja, akun berbatas waktu | `dokumen/permissions.py` |
| super-admin | semua + admin Django | — |

Semua keputusan "boleh/tidak" ada di `apps/*/permissions.py`.

## Status dokumen
`draft → diajukan → diverifikasi_komite → disetujui → kedaluwarsa | dicabut`,
dengan cabang `→ dikembalikan → draft`. Hanya dokumen **disetujui** yang dihitung sebagai bukti
lengkap dan tampil di mode survei. Dokumen regulasi punya *tanggal review*; lewat tanggal itu,
`kirim_pengingat` (harian) mengubahnya menjadi **kedaluwarsa** dan pokja harus mengunggah versi
baru (status kembali ke draft dan diverifikasi ulang). Versi lama tidak pernah dihapus.

## Skor
Per EP: **10** tercapai penuh, **5** sebagian, **0** tidak tercapai, **TDD** tidak dapat diterapkan
(dikeluarkan dari pembagi), atau belum dinilai (tidak ada baris).
`capaian = Σ skor / (jumlah EP dinilai non-TDD × 10) × 100` — di `penilaian/capaian.py`.

## Fitur bantu harian
| Fitur | Untuk | Lokasi / kode |
|---|---|---|
| **Tugas saya** | daftar pekerjaan yang menunggu user sesuai peran & pokja | Dashboard · `penilaian/tugas.py` |
| **Target pokja** | target bertahap per pokja + tenggat; status *tercapai / sesuai jadwal / berisiko / terlambat* dibanding kemajuan linier; notifikasi saat status memburuk | menu Target Pokja · `penilaian/target.py` |
| **Langkah persiapan** | checklist penyiapan sistem untuk komite/admin | Dashboard · `tugas.langkah_persiapan` |
| **Detail EP** | satu halaman per EP: bukti per jenis, skor + riwayat, catatan, wawancara, PPS | `/penilaian/ep/<id>/` |
| **Kekurangan bukti** | EP yang belum lengkap; merah = belum ada dokumen, biru = menunggu verifikasi; ekspor Excel | menu Kekurangan · `capaian.kekurangan_bukti` |
| **Laporan Excel** | rekap per bab + detail per EP untuk rapat/manajemen | tombol di Dashboard · `penilaian/laporan.py` |
| **Pratinjau** | lihat PDF/gambar/video di browser (tetap dicatat bila data pasien) | tautan "Lihat" · `?lihat=1` |
| **Cari** | EP dan dokumen, tersaring hak akses | kotak cari di navbar |
| **Panduan** | langkah kerja per peran | `/panduan/` |
| **Profil** | lihat peran/pokja, ganti kata sandi sendiri | klik nama di navbar |

---

## Data contoh
```bash
python manage.py data_contoh isi     # isi data contoh
python manage.py data_contoh reset   # hapus lalu isi ulang (kembali ke keadaan awal contoh)
python manage.py data_contoh hapus   # kosongkan semua data contoh
```
Hanya data berpenanda yang dihapus: akun `demo.*`, unit/pokja `DEMO-*`, standar `… (contoh)`,
periode `[CONTOH] …`. Akun `admin` Anda dan data asli tidak tersentuh. Teks standar/EP adalah
placeholder, **bukan** isi resmi STARKES, dan tidak ada data pasien.

**Semua akun contoh memakai kata sandi `SimbakContoh2026`.**

| Username | Peran |
|---|---|
| demo.admin | super-admin (bisa buka /admin) |
| demo.direktur | direktur |
| demo.komite | komite-mutu |
| demo.ketua.tkrs / demo.ketua.pmkp / demo.ketua.skp | ketua pokja TKRS / PMKP / SKP |
| demo.anggota.tkrs / demo.anggota.pmkp / demo.anggota.skp | anggota pokja |
| demo.surveior | surveior-internal |
| demo.tamu | tamu-surveior (aktif 30 hari) |

Isi data contoh per bab (TKRS, PMKP, SKP), masing-masing 2 standar × 3 EP:

| Dokumen | Status | Gunanya untuk dicoba |
|---|---|---|
| Kebijakan … contoh | disetujui, review ±1 bulan lagi | muncul di "Akan jatuh tempo" |
| Notulen rapat … contoh | disetujui | bukti D lengkap |
| Laporan bulanan … contoh | diajukan | antrian **komite** |
| Pedoman … contoh | diverifikasi komite | antrian **direktur** |
| Panduan … contoh | dikembalikan + catatan | pokja memperbaiki |
| Foto kegiatan … contoh | draft, data pasien | tidak terlihat oleh tamu |
| Notulen lama PMKP | disetujui, terbit 30 bln lalu | "Bukti pelaksanaan usang" |
| SPO SKP (lama) | kedaluwarsa | perlu versi baru |
| SPO TKRS berversi | disetujui, 2 versi | riwayat versi |

Periode `[CONTOH] Akreditasi <tahun>` aktif (survei 120 hari lagi), 15 dari 18 EP sudah dinilai,
6 PPS dibuat dari EP berskor 0/5 (salah satunya sudah lewat tenggat), dan 6 target pokja
yang menghasilkan keempat status (tercapai, sesuai jadwal, berisiko, terlambat).

## Skenario latihan (±15 menit)
Gunakan dua browser/jendela samaran agar bisa login sebagai dua orang sekaligus.

1. **demo.komite** → *Dashboard*: lihat **Tugas saya**, langkah persiapan, capaian per bab,
   dokumen per status, jatuh tempo, EP tanpa bukti. Buka *Verifikasi*: ada "Laporan bulanan … contoh" menunggu.
   Klik → **Verifikasi (komite)** → **Setujui** (bukan regulasi, jadi komite boleh final).
2. **demo.direktur** → *Verifikasi*: "Pedoman … contoh" menunggu → **Setujui**.
   Perhatikan 🔔 notifikasi.
3. **demo.anggota.tkrs** → *Dokumen* → "Panduan TKRS contoh" (dikembalikan): baca catatan
   komite, klik **Ubah** dan simpan → status kembali **draft**.
4. **demo.ketua.tkrs** → buka dokumen yang sama → **Ajukan verifikasi**. Lalu *Penilaian* →
   TKRS → ubah skor sebuah EP, simpan; capaian di atas halaman ikut berubah.
5. **demo.anggota.tkrs** → menu *Kekurangan* → klik label merah (mis. **+ D**) → unggah PDF apa
   saja. Buka EP tersebut (klik kodenya) untuk melihat semua informasinya di satu halaman.
   Coba juga *Penilaian* → TKRS: anggota hanya bisa melihat, tidak bisa menilai.
6. **demo.surveior** → *Penilaian* → TKRS → tambah catatan pada EP. *Survei* → TKRS →
   **Ekspor PDF/ZIP**.
7. **demo.tamu** → *Survei*: hanya dokumen disetujui; foto berisi data pasien tidak tampil.
   Buka URL dokumen draft secara langsung → 404.
8. **demo.direktur** → *Target Pokja*: lihat pokja yang **terlambat** (TKRS, kelengkapan bukti)
   dan **berisiko** (PMKP). Bandingkan kolom *Aktual* dengan *Seharusnya*.
   **demo.komite** → *Tetapkan target* untuk beberapa pokja sekaligus.
9. **demo.komite** → *PPS*: lihat PPS yang terlambat (merah), **Ekspor Excel**.
10. Terminal: `python manage.py kirim_pengingat --dry-run` untuk melihat apa yang akan dikirim.

Selesai berlatih: `python manage.py data_contoh reset` untuk kembali ke awal.
