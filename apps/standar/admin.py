from django.contrib import admin

from apps.inti.services import hapus_lunak, pulihkan

from .models import Bab, ElemenPenilaian, ItemWawancara, KelompokStandar, LogImporStandar, Standar


class MasterAdmin(admin.ModelAdmin):
    """Admin master standar: tampilkan juga baris nonaktif, tanpa hapus permanen."""

    actions = ["nonaktifkan", "aktifkan"]

    def get_queryset(self, request):
        return self.model.semua.get_queryset()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, description="aktif")
    def status_aktif(self, obj):
        return obj.aktif

    @admin.action(description="Nonaktifkan (soft delete)")
    def nonaktifkan(self, request, queryset):
        for obj in queryset:
            hapus_lunak(obj=obj)

    @admin.action(description="Aktifkan kembali")
    def aktifkan(self, request, queryset):
        for obj in queryset:
            pulihkan(obj=obj)


@admin.register(KelompokStandar)
class KelompokStandarAdmin(MasterAdmin):
    list_display = ["kode", "nama", "urutan", "status_aktif"]
    search_fields = ["kode", "nama"]


@admin.register(Bab)
class BabAdmin(MasterAdmin):
    list_display = ["kode", "nama", "kelompok", "pokja", "urutan", "status_aktif"]
    list_filter = ["kelompok", "pokja"]
    search_fields = ["kode", "nama"]
    autocomplete_fields = ["kelompok", "pokja"]


@admin.register(Standar)
class StandarAdmin(MasterAdmin):
    list_display = ["kode", "bab", "urutan", "status_aktif"]
    list_filter = ["bab__kelompok", "bab"]
    search_fields = ["kode", "uraian"]
    autocomplete_fields = ["bab"]
    list_select_related = ["bab"]


class ItemWawancaraInline(admin.TabularInline):
    model = ItemWawancara
    extra = 0


@admin.register(ElemenPenilaian)
class ElemenPenilaianAdmin(MasterAdmin):
    list_display = ["__str__", "jenis_bukti", "urutan", "status_aktif"]
    list_filter = ["standar__bab"]
    search_fields = ["kode", "uraian", "standar__kode"]
    autocomplete_fields = ["standar"]
    list_select_related = ["standar"]
    inlines = [ItemWawancaraInline]


@admin.register(LogImporStandar)
class LogImporStandarAdmin(admin.ModelAdmin):
    list_display = ["dibuat_pada", "nama_file", "diimpor_oleh", "sumber", "status"]
    list_filter = ["status", "sumber"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
