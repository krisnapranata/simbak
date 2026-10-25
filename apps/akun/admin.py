from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Pokja, Unit, User


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["kode", "nama"]
    search_fields = ["kode", "nama"]


@admin.register(Pokja)
class PokjaAdmin(admin.ModelAdmin):
    list_display = ["kode", "nama", "ketua"]
    search_fields = ["kode", "nama"]
    autocomplete_fields = ["ketua"]


@admin.register(User)
class PenggunaAdmin(UserAdmin):
    list_display = ["username", "first_name", "last_name", "unit", "is_active", "aktif_sampai"]
    list_filter = ["is_active", "is_staff", "groups", "unit", "pokja"]
    autocomplete_fields = ["unit"]
    filter_horizontal = ["groups", "user_permissions", "pokja"]
    fieldsets = UserAdmin.fieldsets + (
        ("Organisasi & masa aktif", {"fields": ["unit", "pokja", "aktif_sampai"]}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Organisasi & masa aktif", {"fields": ["unit", "pokja", "aktif_sampai"]}),
    )
