from django.urls import path

from . import views

app_name = "standar"

urlpatterns = [
    path("", views.BabListView.as_view(), name="bab_list"),
    path("bab/<int:pk>/", views.BabDetailView.as_view(), name="bab_detail"),
    path("impor/", views.ImporStandarView.as_view(), name="impor"),
    path("impor/template/", views.UnduhTemplateView.as_view(), name="impor_template"),
    path("impor/<int:pk>/", views.ImporPratinjauView.as_view(), name="impor_pratinjau"),
    path(
        "impor/<int:pk>/konfirmasi/", views.ImporKonfirmasiView.as_view(), name="impor_konfirmasi"
    ),
    path("impor/<int:pk>/batal/", views.ImporBatalView.as_view(), name="impor_batal"),
]
