from django.apps import AppConfig


class PpsConfig(AppConfig):
    name = "apps.pps"
    verbose_name = "Rencana Perbaikan"

    def ready(self):
        from auditlog.registry import auditlog

        from . import models

        auditlog.register(models.RencanaPerbaikan)
