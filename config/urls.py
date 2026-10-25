from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.akun.views import PanduanView
from apps.inti.views import sehat
from apps.penilaian.views import CariView, DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="beranda"),
    path("cari/", CariView.as_view(), name="cari"),
    path("panduan/", PanduanView.as_view(), name="panduan"),
    path("sehat/", sehat, name="sehat"),
    path("akun/", include("apps.akun.urls")),
    path("standar/", include("apps.standar.urls")),
    path("dokumen/", include("apps.dokumen.urls")),
    path("penilaian/", include("apps.penilaian.urls")),
    path("verifikasi/", include("apps.verifikasi.urls")),
    path("survei/", include("apps.survei.urls")),
    path("pps/", include("apps.pps.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]

admin.site.site_header = "Administrasi SIMBAK"
admin.site.site_title = "SIMBAK"
admin.site.index_title = "Administrasi"
