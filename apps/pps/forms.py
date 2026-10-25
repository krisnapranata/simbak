from django import forms

from apps.akun.models import User
from apps.dokumen.forms import InputTanggal

from .models import RencanaPerbaikan
from .permissions import queryset_ep_pps


class FormPPS(forms.ModelForm):
    class Meta:
        model = RencanaPerbaikan
        fields = [
            "periode",
            "elemen_penilaian",
            "rekomendasi",
            "rencana_kegiatan",
            "indikator",
            "pj",
            "tenggat",
            "status",
            "catatan_progres",
        ]
        widgets = {
            "tenggat": InputTanggal(),
            "rekomendasi": forms.Textarea(attrs={"rows": 3}),
            "rencana_kegiatan": forms.Textarea(attrs={"rows": 3}),
            "indikator": forms.Textarea(attrs={"rows": 2}),
            "catatan_progres": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["elemen_penilaian"].queryset = queryset_ep_pps(user).select_related("standar")
        self.fields["pj"].queryset = User.objects.filter(is_active=True)


class FormProgresPPS(forms.ModelForm):
    class Meta:
        model = RencanaPerbaikan
        fields = ["status", "catatan_progres"]
        widgets = {"catatan_progres": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)


class FormFilterPPS(forms.Form):
    status = forms.ChoiceField(
        choices=[("", "Semua status")] + RencanaPerbaikan.Status.choices, required=False
    )
