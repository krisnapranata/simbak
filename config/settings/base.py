"""Setting dasar SIMBAK. Nilai rahasia dan lingkungan dibaca dari file `.env`."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # pihak ketiga
    "django_htmx",
    "crispy_forms",
    "crispy_bootstrap5",
    "auditlog",
    "axes",
    # app proyek
    "apps.inti",
    "apps.akun",
    "apps.standar",
    "apps.dokumen",
    "apps.penilaian",
    "apps.verifikasi",
    "apps.survei",
    "apps.pps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Semua view wajib login, kecuali yang ditandai @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    # AxesMiddleware harus paling akhir.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.verifikasi.context_processors.notifikasi",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASES = {"default": env.db("DATABASE_URL")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"}
    )
    DATABASES["default"]["TEST"] = {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Autentikasi
AUTH_USER_MODEL = "akun.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.akun.backends.BackendAkun",
]
LOGIN_URL = "akun:masuk"
LOGIN_REDIRECT_URL = "beranda"
LOGOUT_REDIRECT_URL = "akun:masuk"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# django-axes: batasi percobaan login
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # jam
AXES_RESET_ON_SUCCESS = True
# Kunci kombinasi username + IP (bukan IP saja): di belakang proxy semua pengguna bisa
# tampak ber-IP sama, sehingga kunci per-IP akan memblokir seluruh rumah sakit.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_CLIENT_IP_CALLABLE = "apps.inti.utils.ip_klien"

# Bahasa & waktu
LANGUAGE_CODE = "id"
TIME_ZONE = env("TIME_ZONE", default="Asia/Makassar")
USE_I18N = True
USE_TZ = True

# File statis & media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# File bukti disimpan di luar MEDIA_ROOT publik dan hanya diunduh lewat view berizin.
MEDIA_PRIVATE_ROOT = BASE_DIR / env("MEDIA_PRIVATE_ROOT", default="media_private")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "privat": {
        "BACKEND": "apps.inti.storage.StoragePrivat",
        "OPTIONS": {"location": str(MEDIA_PRIVATE_ROOT)},
    },
}

UPLOAD_MAKS_MB = env.int("UPLOAD_MAKS_MB", default=25)
_MIME_ZIP = "application/zip"
# Ekstensi bukti yang diizinkan → MIME asli yang diterima (dicek dengan python-magic).
UPLOAD_EKSTENSI_BUKTI = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _MIME_ZIP,
    },
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _MIME_ZIP},
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        _MIME_ZIP,
    },
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "mp4": {"video/mp4"},
}
# Produksi di belakang Nginx: set True dan buat lokasi `internal` /_privat/ → MEDIA_PRIVATE_ROOT.
UNDUH_X_ACCEL = env.bool("UNDUH_X_ACCEL", default=False)
UNDUH_X_ACCEL_PREFIX = "/_privat/"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Email (notifikasi hanya berisi judul dan tautan, tidak pernah isi dokumen)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="SIMBAK <simbak@localhost>")
# Alamat dasar untuk tautan di email/pengingat dari management command.
URL_DASAR = env("URL_DASAR", default="http://localhost:8000")

# Form
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Audit
AUDITLOG_INCLUDE_ALL_MODELS = False
