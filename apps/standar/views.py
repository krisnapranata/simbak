import io

from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.dokumen.permissions import bisa_buat_dokumen
from apps.inti.views import IzinMixin

from . import services
from .forms import FormFilterBab, FormImporStandar
from .models import ElemenPenilaian, LogImporStandar, Standar
from .permissions import bisa_impor_standar, bisa_proses_log_impor, queryset_bab_untuk


def _annotasi_jumlah(qs):
    return qs.annotate(
        jumlah_standar=Count(
            "standar", filter=Q(standar__dihapus_pada__isnull=True), distinct=True
        ),
        jumlah_ep=Count(
            "standar__elemen_penilaian",
            filter=Q(
                standar__dihapus_pada__isnull=True,
                standar__elemen_penilaian__dihapus_pada__isnull=True,
            ),
            distinct=True,
        ),
    )


class BabListView(ListView):
    template_name = "standar/bab_list.html"
    context_object_name = "daftar_bab"

    def get_queryset(self):
        qs = queryset_bab_untuk(self.request.user).select_related("kelompok", "pokja")
        self.form = FormFilterBab(self.request.GET or None)
        if self.form.is_valid():
            if q := self.form.cleaned_data["q"]:
                qs = qs.filter(Q(kode__icontains=q) | Q(nama__icontains=q))
            if kelompok := self.form.cleaned_data["kelompok"]:
                qs = qs.filter(kelompok=kelompok)
        return _annotasi_jumlah(qs)

    def get_template_names(self):
        if self.request.htmx:
            return ["standar/partials/bab_tabel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = self.form
        return ctx


class BabDetailView(DetailView):
    template_name = "standar/bab_detail.html"
    context_object_name = "bab"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bisa_unggah_bukti"] = bisa_buat_dokumen(self.request.user)
        return ctx

    def get_queryset(self):
        # Bab di luar hak akses user menghasilkan 404.
        ep = ElemenPenilaian.objects.order_by("urutan", "kode")
        standar = Standar.objects.order_by("urutan", "kode").prefetch_related(
            Prefetch("elemen_penilaian", queryset=ep)
        )
        return (
            queryset_bab_untuk(self.request.user)
            .select_related("kelompok", "pokja")
            .prefetch_related(Prefetch("standar", queryset=standar))
        )


class ImporStandarView(IzinMixin, FormView):
    template_name = "standar/impor_form.html"
    form_class = FormImporStandar

    def cek_izin(self):
        return bisa_impor_standar(self.request.user)

    def form_valid(self, form):
        log = services.buat_pratinjau_impor(
            file=form.cleaned_data["file"],
            user=self.request.user,
            nonaktifkan_yang_hilang=form.cleaned_data["nonaktifkan_yang_hilang"],
        )
        return redirect("standar:impor_pratinjau", pk=log.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["riwayat"] = LogImporStandar.objects.select_related("diimpor_oleh")[:10]
        return ctx


class ImporPratinjauView(IzinMixin, DetailView):
    template_name = "standar/impor_pratinjau.html"
    context_object_name = "log"
    queryset = LogImporStandar.objects.select_related("diimpor_oleh")

    def cek_izin(self):
        return bisa_impor_standar(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        log = self.object
        ctx["bisa_proses"] = (
            log.status == LogImporStandar.Status.PRATINJAU
            and bisa_proses_log_impor(self.request.user, log)
        )
        label = {
            "kelompok": "Kelompok",
            "pokja": "Pokja",
            "bab": "Bab",
            "standar": "Standar",
            "ep": "Elemen penilaian",
        }
        ctx["baris_ringkasan"] = [
            (label[k], log.ringkasan[k]) for k in services.ENTITAS if k in log.ringkasan
        ]
        return ctx


class _AksiImporView(IzinMixin, View):
    http_method_names = ["post"]
    aksi = None

    def cek_izin(self):
        return bisa_impor_standar(self.request.user)

    def post(self, request, pk):
        log = get_object_or_404(LogImporStandar, pk=pk)
        try:
            log = self.aksi(log=log, user=request.user)
        except services.GalatImpor as e:
            messages.error(request, str(e))
        else:
            self.beri_pesan(log)
        return redirect("standar:impor_pratinjau", pk=log.pk)


class ImporKonfirmasiView(_AksiImporView):
    aksi = staticmethod(services.konfirmasi_impor)

    def beri_pesan(self, log):
        if log.status == LogImporStandar.Status.BERHASIL:
            messages.success(self.request, "Master standar berhasil diimpor.")
        else:
            messages.error(self.request, "Impor gagal. Tidak ada data yang disimpan.")


class ImporBatalView(_AksiImporView):
    aksi = staticmethod(services.batalkan_impor)

    def beri_pesan(self, log):
        messages.info(self.request, "Impor dibatalkan.")


class UnduhTemplateView(IzinMixin, View):
    def cek_izin(self):
        return bisa_impor_standar(self.request.user)

    def get(self, request):
        buffer = io.BytesIO()
        services.buat_template_workbook().save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="template_starkes.xlsx"'
        return response
