from django.urls import path

from . import views

app_name = "pps"

urlpatterns = [
    path("", views.PPSListView.as_view(), name="list"),
    path("baru/", views.PPSCreateView.as_view(), name="baru"),
    path("<int:pk>/ubah/", views.PPSUpdateView.as_view(), name="ubah"),
    path("<int:pk>/hapus/", views.PPSHapusView.as_view(), name="hapus"),
    path("dari-penilaian/", views.PPSOtomatisView.as_view(), name="otomatis"),
    path("ekspor/", views.PPSEksporView.as_view(), name="ekspor"),
]
