from .base import *  # noqa: F403
from .base import STORAGES, env

DEBUG = False
SECRET_KEY = env("SECRET_KEY")
# 127.0.0.1/localhost untuk healthcheck Docker dari dalam container.
ALLOWED_HOSTS = [*env.list("ALLOWED_HOSTS"), "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# File statis ber-hash (cache aman di browser); dilayani nginx dari STATIC_ROOT.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
}

# HTTPS diterminasi di reverse proxy (Nginx Proxy Manager) yang mengirim X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^sehat/$"]
SESSION_COOKIE_SECURE = env.bool("COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("COOKIE_SECURE", default=True)
# includeSubDomains/preload default mati: dapat memaksa HTTPS pada subdomain RS lain.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Log ke stdout supaya terlihat di `docker logs simbak_web`. Jangan mencatat data pasien.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"ringkas": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"konsol": {"class": "logging.StreamHandler", "formatter": "ringkas"}},
    "root": {"handlers": ["konsol"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["konsol"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
