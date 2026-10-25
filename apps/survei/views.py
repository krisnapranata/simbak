from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from django.views import View
from django.views.generic import TemplateView

from apps.inti.utils import ip_klien
from apps.penilaian.capaian import capaian_per_bab
from apps.penilaian.views import PeriodeMixin

from . import services
from .permissions import queryset_bab_survei


class SurveiBabListView(PeriodeMixin, TemplateView):
    template_name = "survei/bab_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["baris_bab"] = capaian_per_bab(
            periode=self.periode, bab_qs=queryset_bab_survei(self.request.user)
        )
        return ctx


class SurveiBabMixin(PeriodeMixin):
    def get_bab(self):
        return get_object_or_404(
            queryset_bab_survei(self.request.user).select_related("kelompok", "pokja"),
            pk=self.kwargs["pk"],
        )


class SurveiBabView(SurveiBabMixin, TemplateView):
    template_name = "survei/bab_telusur.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            services.konteks_bab(bab=self.get_bab(), periode=self.periode, user=self.request.user)
        )
        return ctx


class EksporPDFView(SurveiBabMixin, View):
    def get(self, request, pk):
        bab = self.get_bab()
        pdf = services.buat_pdf(bab=bab, periode=self.periode, user=request.user)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = content_disposition_header(
            True, f"telusur_{bab.kode}.pdf"
        )
        response["Cache-Control"] = "private, no-store"
        return response


class EksporZIPView(SurveiBabMixin, View):
    def get(self, request, pk):
        bab = self.get_bab()
        tmp = services.buat_zip(
            bab=bab, periode=self.periode, user=request.user, ip=ip_klien(request)
        )
        response = FileResponse(
            tmp,
            as_attachment=True,
            filename=f"bukti_{bab.kode}.zip",
            content_type="application/zip",
        )
        response["Cache-Control"] = "private, no-store"
        return response
