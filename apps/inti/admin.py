from django.contrib import admin

from .models import PengaturanSistem


@admin.register(PengaturanSistem)
class PengaturanSistemAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not PengaturanSistem.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
