from django.contrib import admin

from .models import BuktiEP, Dokumen, DokumenVersi, LogUnduhan


class VersiInline(admin.TabularInline):
    model = DokumenVersi
    extra = 0
    can_delete = False
    fields = ["nomor_versi", "nama_file_asli", "mime", "ukuran", "sha256", "diunggah_oleh"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class BuktiInline(admin.TabularInline):
    model = BuktiEP
    extra = 0
    autocomplete_fields = ["elemen_penilaian"]
    readonly_fields = ["dibuat_oleh"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Dokumen)
class DokumenAdmin(admin.ModelAdmin):
    """Hanya untuk koreksi data oleh super-admin. Status diubah lewat alur verifikasi."""

    list_display = ["judul", "nomor", "jenis_dokumen", "pokja", "status", "mengandung_data_pasien"]
    list_filter = ["status", "jenis_dokumen", "pokja", "mengandung_data_pasien"]
    search_fields = ["judul", "nomor"]
    readonly_fields = ["status", "versi_aktif", "dibuat_oleh"]
    autocomplete_fields = ["pokja", "unit", "penanggung_jawab"]
    inlines = [VersiInline, BuktiInline]

    def get_queryset(self, request):
        return Dokumen.semua.select_related("pokja")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogUnduhan)
class LogUnduhanAdmin(admin.ModelAdmin):
    list_display = ["waktu", "user", "versi", "ip", "keterangan"]
    list_select_related = ["user", "versi__dokumen"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
