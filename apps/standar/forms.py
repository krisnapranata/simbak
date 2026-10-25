from django import forms

from apps.inti.validators import validasi_upload

from .models import KelompokStandar

MIME_XLSX = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}


class FormImporStandar(forms.Form):
    file = forms.FileField(
        label="File Excel (.xlsx)",
        help_text="Gunakan template SIMBAK. Sheet EP wajib, sheet Bab opsional.",
    )
    nonaktifkan_yang_hilang = forms.BooleanField(
        label="Nonaktifkan standar/EP yang tidak ada di file",
        required=False,
        help_text="Hanya untuk bab yang ada di file. Data tidak dihapus; bukti dan penilaian "
        "terkait tetap tersimpan.",
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        validasi_upload(file, ekstensi={"xlsx": MIME_XLSX}, maks_mb=10)
        return file


class FormFilterBab(forms.Form):
    q = forms.CharField(label="Cari", required=False)
    kelompok = forms.ModelChoiceField(
        label="Kelompok",
        queryset=KelompokStandar.objects.all(),
        required=False,
        empty_label="Semua kelompok",
    )
