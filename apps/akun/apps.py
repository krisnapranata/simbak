from django.apps import AppConfig


class AkunConfig(AppConfig):
    name = "apps.akun"
    verbose_name = "Akun & Organisasi"

    def ready(self):
        from auditlog.registry import auditlog
        from django.contrib.auth.models import Group

        from . import models

        auditlog.register(models.User, exclude_fields=["password", "last_login"])
        auditlog.register(models.Unit)
        auditlog.register(models.Pokja)
        auditlog.register(Group, m2m_fields={"permissions"})
