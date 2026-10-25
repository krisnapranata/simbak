from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import FormMasuk

app_name = "akun"

urlpatterns = [
    path(
        "masuk/",
        auth_views.LoginView.as_view(
            template_name="akun/masuk.html",
            authentication_form=FormMasuk,
            redirect_authenticated_user=True,
        ),
        name="masuk",
    ),
    path("keluar/", auth_views.LogoutView.as_view(), name="keluar"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path("kata-sandi/", views.GantiKataSandiView.as_view(), name="kata_sandi"),
]
