---
name: modul-django
description: Langkah standar membuat app atau fitur baru di proyek SIMBAK (Django + venv) — model, migrasi, service, permission, view/template HTMX, admin, dan test. Gunakan setiap kali menambah model, halaman CRUD, atau alur bisnis baru.
---

# Membuat Modul / Fitur Baru (Django)

## 0. Persiapan
- Pastikan venv aktif (`which python` / `where python` menunjuk ke `.venv`). Jika belum, aktifkan dulu.
- Baca `CLAUDE.md` dan, bila menyangkut akreditasi, skill `akreditasi-domain`.
- Tulis rencana singkat (model, URL, peran yang boleh akses) dan konfirmasi ke pengguna bila fitur besar.

## 1. App baru (jika perlu)
```bash
mkdir apps/namaapp
python manage.py startapp namaapp apps/namaapp
```
- Ubah `apps/namaapp/apps.py`: `name = "apps.namaapp"`, `verbose_name = "Nama App"`.
- Daftarkan di `INSTALLED_APPS` (`config/settings/base.py`).
- Buat file: `services.py`, `permissions.py`, `forms.py`, `urls.py`, `tests/__init__.py`.

## 2. Model
```python
class Dokumen(ModelDasar):  # ModelDasar: dibuat_pada, diubah_pada, dihapus_pada
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        DIAJUKAN = "diajukan", "Diajukan"
        ...

    judul = models.CharField("judul", max_length=255)
    status = models.CharField("status", max_length=30, choices=Status, default=Status.DRAFT)

    class Meta:
        verbose_name = "dokumen"
        verbose_name_plural = "dokumen"
        ordering = ["-dibuat_pada"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.judul
```
Aturan:
- Warisi `ModelDasar` (abstract, di `apps/akun/models.py` atau `apps/inti/`) untuk timestamp dan soft delete.
- `verbose_name` Bahasa Indonesia di semua field.
- Gunakan `on_delete=models.PROTECT` untuk relasi ke master standar dan dokumen. Hindari `CASCADE` kecuali benar-benar anak (mis. `DokumenVersi`).
- Constraint unik pakai `UniqueConstraint` di `Meta.constraints`.
- Daftarkan model penting ke `auditlog.register(...)`.

## 3. Migrasi
```bash
python manage.py makemigrations namaapp
python manage.py migrate
python manage.py makemigrations --check   # pastikan tidak ada yang tertinggal
```
Data awal (grup, kelompok standar) lewat **data migration** atau fixture, bukan diisi manual.

## 4. Service (logika bisnis)
```python
# apps/namaapp/services.py
from django.db import transaction


@transaction.atomic
def ajukan_dokumen(*, dokumen, user, catatan=""):
    if not bisa_ajukan(user, dokumen):
        raise PermissionDenied
    if dokumen.status != Dokumen.Status.DRAFT:
        raise TransisiTidakValid(...)
    ...
    return dokumen
```
- Argumen keyword-only (`*`).
- View hanya memanggil service, tidak berisi logika bisnis.

## 5. Permission
```python
# apps/namaapp/permissions.py
def bisa_edit_dokumen(user, dokumen) -> bool:
    if user.is_superuser or user.groups.filter(name="komite-mutu").exists():
        return True
    return dokumen.status == Dokumen.Status.DRAFT and user.pokja.filter(babs__in=...).exists()


def queryset_dokumen_untuk(user):
    """Selalu dipakai di list view agar data tersaring sesuai hak akses."""
```
- Satu fungsi per keputusan akses. Pakai di view, dan lewat template tag/filter di template.

## 6. View, URL, Template
- CBV: `ListView`, `DetailView`, `CreateView`, `UpdateView` + `LoginRequiredMixin` + mixin izin proyek (`IzinMixin` yang memanggil fungsi di `permissions.py`).
- `get_queryset()` wajib memakai `queryset_..._untuk(user)` + `select_related/prefetch_related`.
- URL berbahasa Indonesia dengan `app_name`: `path("dokumen/<int:pk>/ubah/", ..., name="ubah")`.
- Template di `templates/namaapp/`, extend `base.html`. Partial HTMX di `templates/namaapp/partials/` dan dicek `request.htmx`.
- Template pakai kelas Bootstrap 5 (tema Blue Glass, tanpa CDN); form pakai crispy-bootstrap5. Pesan sukses lewat `django.contrib.messages`.

## 7. Admin
Daftarkan model dengan `list_display`, `list_filter`, `search_fields`, `autocomplete_fields`. Admin untuk super-admin saja, bukan UI utama pengguna.

## 8. Test (wajib)
```
apps/namaapp/tests/
  factories.py      # factory-boy
  test_models.py
  test_services.py  # transisi valid & tidak valid
  test_views.py     # akses per peran: boleh (200/302) dan tidak boleh (403/404)
```
- Minimal: setiap peran yang relevan diuji aksesnya, dan alur utama service diuji.
- Jangan pakai data pasien asli. Pakai nama fiktif dari factory.

## 9. Checklist sebelum selesai
- [ ] `ruff check .` dan `ruff format .` bersih
- [ ] `pytest` lulus
- [ ] `python manage.py makemigrations --check` tidak ada perubahan
- [ ] Paket baru tercatat di `requirements.txt`
- [ ] Hak akses dicek di view **dan** queryset tersaring
- [ ] Tidak ada query N+1 di halaman list (cek dengan `django-debug-toolbar` saat dev)
- [ ] Ringkas perubahan untuk pengguna: file yang diubah, cara mencoba, dan yang belum dikerjakan
