# Login/logout memakai view bawaan Django (lihat urls.py).
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .peran import Peran
from .permissions import nama_peran


class ProfilView(TemplateView):
    template_name = "akun/profil.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["daftar_peran"] = [p.label for p in Peran if p.value in nama_peran(user)]
        ctx["daftar_pokja"] = user.pokja.prefetch_related("bab")
        return ctx


class GantiKataSandiView(PasswordChangeView):
    template_name = "akun/kata_sandi.html"
    success_url = reverse_lazy("akun:profil")

    def form_valid(self, form):
        messages.success(self.request, "Kata sandi berhasil diganti.")
        return super().form_valid(form)


class PanduanView(TemplateView):
    """Panduan penggunaan per peran; peran user sendiri ditampilkan lebih dulu."""

    template_name = "panduan.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        milik = nama_peran(self.request.user)
        if self.request.user.is_superuser:
            milik = milik | {Peran.SUPER_ADMIN}
        ctx["peran_saya"] = [p for p in Peran if p.value in milik]
        ctx["peran_lain"] = [p for p in Peran if p.value not in milik]
        return ctx
