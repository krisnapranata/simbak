from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from apps.dokumen.permissions import queryset_dokumen_untuk

from . import services
from .models import Notifikasi
from .permissions import queryset_antrian_untuk


class AntrianView(ListView):
    template_name = "verifikasi/antrian.html"
    context_object_name = "daftar_dokumen"
    paginate_by = 50

    def get_queryset(self):
        return (
            queryset_antrian_untuk(self.request.user)
            .select_related("pokja", "dibuat_oleh")
            .order_by("status", "diubah_pada")
        )


class AksiView(View):
    """POST aksi verifikasi (ajukan/verifikasi/setujui/kembalikan/cabut)."""

    http_method_names = ["post"]

    def post(self, request, pk, aksi):
        if aksi not in services.JALANKAN:
            raise Http404
        dokumen = get_object_or_404(queryset_dokumen_untuk(request.user), pk=pk)
        try:
            services.JALANKAN[aksi](
                dokumen=dokumen, user=request.user, catatan=request.POST.get("catatan", "")
            )
        except services.TransisiTidakValid as e:
            messages.error(request, str(e))
        except PermissionDenied:
            messages.error(request, "Anda tidak berhak melakukan aksi ini.")
        else:
            messages.success(request, f"{services.AKSI_UI[aksi]}: berhasil.")
        return redirect("dokumen:detail", pk=pk)


class NotifikasiListView(ListView):
    template_name = "verifikasi/notifikasi.html"
    context_object_name = "daftar_notifikasi"
    paginate_by = 50

    def get_queryset(self):
        return Notifikasi.objects.filter(penerima=self.request.user)


class BacaNotifikasiView(View):
    http_method_names = ["post"]

    def post(self, request, pk):
        notif = get_object_or_404(Notifikasi, pk=pk, penerima=request.user)
        services.tandai_dibaca(notifikasi=notif, user=request.user)
        if notif.url and url_has_allowed_host_and_scheme(notif.url, allowed_hosts=None):
            return redirect(notif.url)
        return redirect("verifikasi:notifikasi")


class BacaSemuaView(View):
    http_method_names = ["post"]

    def post(self, request):
        services.tandai_semua_dibaca(user=request.user)
        return redirect("verifikasi:notifikasi")
