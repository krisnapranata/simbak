import io

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.inti.views import IzinMixin
from apps.penilaian.views import PeriodeMixin

from . import services
from .forms import FormFilterPPS, FormPPS, FormProgresPPS
from .permissions import (
    bisa_buat_pps,
    bisa_buat_pps_otomatis,
    bisa_edit_pps,
    bisa_update_progres,
    queryset_pps_untuk,
)


def _filter(request, periode):
    qs = queryset_pps_untuk(request.user).select_related(
        "elemen_penilaian__standar__bab", "pj", "periode"
    )
    if periode is not None:
        qs = qs.filter(periode=periode)
    form = FormFilterPPS(request.GET or None)
    if form.is_valid() and form.cleaned_data["status"]:
        qs = qs.filter(status=form.cleaned_data["status"])
    if request.GET.get("pj") == "saya":
        qs = qs.filter(pj=request.user)
    return qs.order_by("elemen_penilaian__standar__bab__kode", "tenggat"), form


class PPSListView(PeriodeMixin, ListView):
    template_name = "pps/pps_list.html"
    context_object_name = "daftar_pps"
    paginate_by = 50

    def get_queryset(self):
        qs, self.form = _filter(self.request, self.periode)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            form=self.form,
            bisa_buat=bisa_buat_pps(self.request.user),
            bisa_otomatis=bisa_buat_pps_otomatis(self.request.user),
            query=self.request.GET.urlencode(),
        )
        return ctx


class PPSCreateView(IzinMixin, CreateView):
    template_name = "pps/pps_form.html"
    form_class = FormPPS

    def cek_izin(self):
        return bisa_buat_pps(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        from apps.penilaian.services import periode_aktif

        return {"periode": periode_aktif()}

    def form_valid(self, form):
        services.simpan_pps(user=self.request.user, pps=form.save(commit=False))
        messages.success(self.request, "Rencana perbaikan disimpan.")
        return redirect("pps:list")


class PPSUpdateView(IzinMixin, UpdateView):
    template_name = "pps/pps_form.html"

    def get_object(self, queryset=None):
        if not hasattr(self, "_obj"):
            self._obj = get_object_or_404(
                queryset_pps_untuk(self.request.user).select_related(
                    "elemen_penilaian__standar__bab"
                ),
                pk=self.kwargs["pk"],
            )
        return self._obj

    def cek_izin(self):
        return bisa_update_progres(self.request.user, self.get_object())

    def get_form_class(self):
        return FormPPS if bisa_edit_pps(self.request.user, self.get_object()) else FormProgresPPS

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        services.simpan_pps(
            user=self.request.user, pps=form.save(commit=False), field_diubah=form.changed_data
        )
        messages.success(self.request, "Rencana perbaikan diperbarui.")
        return redirect("pps:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bisa_hapus"] = bisa_edit_pps(self.request.user, self.object)
        return ctx


class PPSHapusView(View):
    http_method_names = ["post"]

    def post(self, request, pk):
        pps = get_object_or_404(queryset_pps_untuk(request.user), pk=pk)
        services.hapus_pps(user=request.user, pps=pps)
        messages.success(request, "Rencana perbaikan dihapus.")
        return redirect("pps:list")


class PPSOtomatisView(PeriodeMixin, IzinMixin, View):
    http_method_names = ["post"]

    def cek_izin(self):
        return bisa_buat_pps_otomatis(self.request.user)

    def post(self, request):
        if self.periode is None:
            messages.error(request, "Belum ada periode aktif.")
        else:
            n = services.buat_dari_penilaian(user=request.user, periode=self.periode)
            messages.success(request, f"{n} draft rencana perbaikan dibuat dari EP berskor 0/5.")
        return redirect("pps:list")


class PPSEksporView(PeriodeMixin, View):
    def get(self, request):
        qs, _ = _filter(request, self.periode)
        buffer = io.BytesIO()
        services.ekspor_xlsx(qs).save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="rencana_perbaikan.xlsx"'
        return response
