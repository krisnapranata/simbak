from django.urls import path

from . import views

app_name = "dokumen"

urlpatterns = [
    path("", views.DokumenListView.as_view(), name="list"),
    path("baru/", views.DokumenCreateView.as_view(), name="baru"),
    path("<int:pk>/", views.DokumenDetailView.as_view(), name="detail"),
    path("<int:pk>/ubah/", views.DokumenUpdateView.as_view(), name="ubah"),
    path("<int:pk>/hapus/", views.HapusDokumenView.as_view(), name="hapus"),
    path("<int:pk>/versi/baru/", views.UnggahVersiView.as_view(), name="versi_baru"),
    path("<int:pk>/versi/<int:versi_pk>/unduh/", views.UnduhView.as_view(), name="unduh"),
    path("<int:pk>/cari-ep/", views.CariEPView.as_view(), name="cari_ep"),
    path("<int:pk>/tautkan/", views.TautkanEPView.as_view(), name="tautkan"),
    path("<int:pk>/bukti/<int:bukti_pk>/lepas/", views.LepasBuktiView.as_view(), name="lepas"),
]
