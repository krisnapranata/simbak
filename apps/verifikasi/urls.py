from django.urls import path

from . import views

app_name = "verifikasi"

urlpatterns = [
    path("", views.AntrianView.as_view(), name="antrian"),
    path("dokumen/<int:pk>/<str:aksi>/", views.AksiView.as_view(), name="aksi"),
    path("notifikasi/", views.NotifikasiListView.as_view(), name="notifikasi"),
    path("notifikasi/<int:pk>/baca/", views.BacaNotifikasiView.as_view(), name="baca"),
    path("notifikasi/baca-semua/", views.BacaSemuaView.as_view(), name="baca_semua"),
]
