from django.apps import AppConfig


class DokumenConfig(AppConfig):
    name = "apps.dokumen"
    verbose_name = "Dokumen Bukti"

    def ready(self):
        from auditlog.registry import auditlog

        from . import models

        auditlog.register(models.Dokumen)
        auditlog.register(models.DokumenVersi)
        auditlog.register(models.BuktiEP)
