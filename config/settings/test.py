import tempfile

from .base import *  # noqa: F403
from .base import STORAGES

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MEDIA_PRIVATE_ROOT = tempfile.mkdtemp(prefix="simbak-test-")
STORAGES["privat"]["OPTIONS"]["location"] = MEDIA_PRIVATE_ROOT

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
