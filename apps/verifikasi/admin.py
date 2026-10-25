from django.contrib import admin

from .models import LogVerifikasi, Notifikasi


class HanyaBacaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogVerifikasi)
class LogVerifikasiAdmin(HanyaBacaAdmin):
    list_display = ["waktu", "dokumen", "dari_status", "ke_status", "user"]
    list_filter = ["ke_status"]
    search_fields = ["dokumen__judul"]
    list_select_related = ["dokumen", "user"]


@admin.register(Notifikasi)
class NotifikasiAdmin(HanyaBacaAdmin):
    list_display = ["dibuat_pada", "penerima", "judul", "dibaca_pada"]
    list_select_related = ["penerima"]
