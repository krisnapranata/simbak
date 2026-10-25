from django import forms

from apps.akun.models import User
from apps.standar.models import ElemenPenilaian, JenisBukti

from .models import Dokumen, JenisDokumen, StatusDokumen
from .permissions import queryset_ep_tautan, queryset_pokja_kelola
from .services import validasi_file_bukti

PILIHAN_DATA_PASIEN = [
    ("True", "Ya, mengandung data pasien"),
    ("False", "Tidak mengandung data pasien"),
]


class InputTanggal(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class FormDokumen(forms.ModelForm):
    mengandung_data_pasien = forms.TypedChoiceField(
        label="Apakah dokumen mengandung data pasien?",
        choices=PILIHAN_DATA_PASIEN,
        coerce=lambda v: v == "True",
        widget=forms.RadioSelect,
        help_text="Sebisa mungkin samarkan identitas pasien (nama, No. RM, NIK, alamat) "
        "sebelum mengunggah.",
    )

    class Meta:
        model = Dokumen
        fields = [
            "judul",
            "nomor",
            "jenis_dokumen",
            "pokja",
            "unit",
            "penanggung_jawab",
            "tanggal_terbit",
            "tanggal_review_berikutnya",
            "mengandung_data_pasien",
            "keterangan",
        ]
        widgets = {
            "tanggal_terbit": InputTanggal(),
            "tanggal_review_berikutnya": InputTanggal(),
            "keterangan": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "tanggal_review_berikutnya": "Untuk regulasi, bila dikosongkan diisi otomatis dari "
            "tanggal terbit + periode review pada pengaturan sistem.",
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pokja"].queryset = queryset_pokja_kelola(user)
        self.fields["penanggung_jawab"].queryset = User.objects.filter(is_active=True)


class FormDokumenBaru(FormDokumen):
    file = forms.FileField(label="File")
    catatan_perubahan = forms.CharField(label="Catatan", required=False)
    ep = forms.ModelChoiceField(
        queryset=ElemenPenilaian.objects.none(), required=False, widget=forms.HiddenInput
    )
    jenis_bukti = forms.ChoiceField(
        choices=[("", "")] + JenisBukti.choices, required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["ep"].queryset = queryset_ep_tautan(user)

    def clean_file(self):
        file = self.cleaned_data["file"]
        validasi_file_bukti(file)
        return file

    def clean(self):
        data = super().clean()
        ep, jenis = data.get("ep"), data.get("jenis_bukti")
        if ep and jenis not in ep.jenis_bukti:
            self.add_error(None, f"EP {ep} tidak memerlukan bukti jenis {jenis}.")
        return data


class FormVersi(forms.Form):
    file = forms.FileField(label="File versi baru")
    catatan_perubahan = forms.CharField(
        label="Catatan perubahan", widget=forms.Textarea(attrs={"rows": 3})
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        validasi_file_bukti(file)
        return file


class FormTautkanEP(forms.Form):
    elemen_penilaian = forms.ModelChoiceField(queryset=ElemenPenilaian.objects.none())
    jenis_bukti = forms.ChoiceField(choices=JenisBukti.choices)
    keterangan = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["elemen_penilaian"].queryset = queryset_ep_tautan(user)


class FormFilterDokumen(forms.Form):
    q = forms.CharField(label="Cari", required=False)
    status = forms.ChoiceField(
        label="Status", choices=[("", "Semua status")] + StatusDokumen.choices, required=False
    )
    jenis = forms.ChoiceField(
        label="Jenis", choices=[("", "Semua jenis")] + JenisDokumen.choices, required=False
    )
