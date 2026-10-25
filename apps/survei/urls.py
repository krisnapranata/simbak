from django.urls import path

from . import views

app_name = "survei"

urlpatterns = [
    path("", views.SurveiBabListView.as_view(), name="bab_list"),
    path("bab/<int:pk>/", views.SurveiBabView.as_view(), name="bab"),
    path("bab/<int:pk>/pdf/", views.EksporPDFView.as_view(), name="pdf"),
    path("bab/<int:pk>/zip/", views.EksporZIPView.as_view(), name="zip"),
]
