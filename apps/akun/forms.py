from django.contrib.auth.forms import AuthenticationForm


class FormMasuk(AuthenticationForm):
    error_messages = {
        "invalid_login": "Nama pengguna atau kata sandi salah, atau akun sudah tidak aktif.",
        "inactive": "Akun ini tidak aktif.",
    }
