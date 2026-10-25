from django.contrib import admin

from .models import (
    CatatanPenilaian,
    KriteriaPredikat,
    PenilaianEP,
    PeriodeAkreditasi,
    SyaratPredikat,
    TargetPokja,
)


@admin.register(PeriodeAkreditasi)
class PeriodeAkreditasiAdmin(admin.ModelAdmin):
    list_display = ["nama", "tanggal_mulai", "tanggal_survei", "status", "aktif"]
    filter_horizontal = ["tamu_boleh_data_pasien"]


class SyaratInline(admin.TabularInline):
    model = SyaratPredikat
    extra = 1
    filter_horizontal = ["bab_wajib"]


@admin.register(KriteriaPredikat)
class KriteriaPredikatAdmin(admin.ModelAdmin):
    list_display = ["nama", "urutan"]
    inlines = [SyaratInline]


@admin.register(PenilaianEP)
class PenilaianEPAdmin(admin.ModelAdmin):
    list_display = ["elemen_penilaian", "periode", "skor", "tdd", "dinilai_oleh", "dinilai_pada"]
    list_filter = ["periode", "tdd", "skor"]
    list_select_related = ["elemen_penilaian__standar", "periode", "dinilai_oleh"]
    autocomplete_fields = ["elemen_penilaian"]


@admin.register(CatatanPenilaian)
class CatatanPenilaianAdmin(admin.ModelAdmin):
    list_display = ["elemen_penilaian", "periode", "penulis", "dibuat_pada"]
    list_select_related = ["elemen_penilaian__standar", "periode", "penulis"]


@admin.register(TargetPokja)
class TargetPokjaAdmin(admin.ModelAdmin):
    list_display = ["pokja", "ukuran", "nilai_target", "tenggat", "periode"]
    list_filter = ["periode", "ukuran", "pokja"]
    list_select_related = ["pokja", "periode"]
