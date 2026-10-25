from django.urls import path

from . import views

app_name = "penilaian"

urlpatterns = [
    path("", views.PenilaianBabListView.as_view(), name="bab_list"),
    path("bab/<int:pk>/", views.PenilaianBabView.as_view(), name="bab"),
    path("ep/<int:pk>/", views.EPDetailView.as_view(), name="ep"),
    path("kekurangan/", views.KekuranganView.as_view(), name="kekurangan"),
    path("laporan/", views.LaporanPenilaianView.as_view(), name="laporan"),
    path("target/", views.TargetListView.as_view(), name="target_list"),
    path("target/baru/", views.TargetCreateView.as_view(), name="target_baru"),
    path("target/<int:pk>/ubah/", views.TargetUpdateView.as_view(), name="target_ubah"),
    path("target/<int:pk>/hapus/", views.TargetHapusView.as_view(), name="target_hapus"),
    path(
        "periode/<int:periode_pk>/ep/<int:ep_pk>/nilai/", views.NilaiEPView.as_view(), name="nilai"
    ),
    path(
        "periode/<int:periode_pk>/ep/<int:ep_pk>/catatan/",
        views.CatatanEPView.as_view(),
        name="catatan",
    ),
    path("periode/", views.PeriodeListView.as_view(), name="periode_list"),
    path("periode/baru/", views.PeriodeCreateView.as_view(), name="periode_baru"),
    path("periode/<int:pk>/ubah/", views.PeriodeUpdateView.as_view(), name="periode_ubah"),
    path(
        "periode/<int:pk>/aktifkan/", views.AktifkanPeriodeView.as_view(), name="periode_aktifkan"
    ),
]
