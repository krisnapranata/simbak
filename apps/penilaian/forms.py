from django import forms

from apps.akun.models import Pokja, User
from apps.akun.peran import Peran
from apps.dokumen.forms import InputTanggal

from .models import PeriodeAkreditasi, TargetPokja


class FormPeriode(forms.ModelForm):
    class Meta:
        model = PeriodeAkreditasi
        fields = [
            "nama",
            "tanggal_mulai",
            "tanggal_survei",
            "status",
            "aktif",
            "tamu_boleh_data_pasien",
        ]
        widgets = {
            "tanggal_mulai": InputTanggal(),
            "tanggal_survei": InputTanggal(),
            "tamu_boleh_data_pasien": forms.CheckboxSelectMultiple,
        }
        help_texts = {
            "tamu_boleh_data_pasien": "Izin eksplisit bagi akun tamu surveior untuk melihat "
            "dokumen yang ditandai mengandung data pasien selama periode ini aktif.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tamu_boleh_data_pasien"].queryset = User.objects.filter(
            groups__name=Peran.TAMU_SURVEIOR
        )


class _ValidasiTanggalMixin:
    def clean(self):
        data = super().clean()
        mulai, tenggat, periode = (
            data.get("tanggal_mulai"),
            data.get("tenggat"),
            data.get("periode"),
        )
        awal = mulai or (periode.tanggal_mulai if periode else None)
        if awal and tenggat and tenggat <= awal:
            self.add_error("tenggat", "Tenggat harus setelah tanggal mulai.")
        nilai = data.get("nilai_target")
        if nilai is not None and not (0 <= nilai <= 100):
            self.add_error("nilai_target", "Target harus antara 0 dan 100.")
        return data


class FormTarget(_ValidasiTanggalMixin, forms.ModelForm):
    class Meta:
        model = TargetPokja
        fields = [
            "periode",
            "pokja",
            "ukuran",
            "nilai_target",
            "tanggal_mulai",
            "tenggat",
            "keterangan",
        ]
        widgets = {
            "tanggal_mulai": InputTanggal(),
            "tenggat": InputTanggal(),
            "keterangan": forms.Textarea(attrs={"rows": 2}),
        }


class FormTargetBanyak(_ValidasiTanggalMixin, forms.Form):
    """Satu target untuk beberapa pokja sekaligus."""

    periode = forms.ModelChoiceField(label="Periode", queryset=PeriodeAkreditasi.objects.all())
    daftar_pokja = forms.ModelMultipleChoiceField(
        label="Pokja",
        queryset=Pokja.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Centang semua pokja yang mendapat target ini.",
    )
    ukuran = forms.ChoiceField(label="Ukuran", choices=TargetPokja.Ukuran.choices)
    nilai_target = forms.DecimalField(
        label="Target (%)", min_value=0, max_value=100, decimal_places=2
    )
    tanggal_mulai = forms.DateField(
        label="Tanggal mulai",
        required=False,
        widget=InputTanggal(),
        help_text="Kosong = tanggal mulai periode. Dipakai menghitung kemajuan yang diharapkan.",
    )
    tenggat = forms.DateField(label="Tenggat", widget=InputTanggal())
    keterangan = forms.CharField(
        label="Keterangan", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
