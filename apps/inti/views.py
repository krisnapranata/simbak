from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.http import Http404, HttpResponse


class IzinMixin:
    """Mixin view: panggil fungsi dari `permissions.py` lewat `cek_izin()`.

    Set `sembunyikan=True` agar yang tidak berhak mendapat 404 (tidak membocorkan keberadaan).
    """

    sembunyikan = False

    def cek_izin(self) -> bool:
        raise NotImplementedError

    def dispatch(self, request, *args, **kwargs):
        if not self.cek_izin():
            if self.sembunyikan:
                raise Http404
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


@login_not_required
def sehat(request):
    """Healthcheck untuk Docker/reverse proxy: aplikasi hidup dan database dapat dihubungi."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("database tidak dapat dihubungi", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
