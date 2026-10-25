from django.contrib import admin

from .models import RencanaPerbaikan


@admin.register(RencanaPerbaikan)
class RencanaPerbaikanAdmin(admin.ModelAdmin):
    list_display = ["elemen_penilaian", "periode", "pj", "tenggat", "status"]
    list_filter = ["periode", "status"]
    list_select_related = ["elemen_penilaian__standar", "periode", "pj"]
    autocomplete_fields = ["elemen_penilaian", "pj"]
