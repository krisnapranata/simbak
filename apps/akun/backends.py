from django.contrib.auth.backends import ModelBackend


class BackendAkun(ModelBackend):
    """Menolak login (dan sesi berjalan) untuk akun yang masa aktifnya habis."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not user.masa_aktif_habis
