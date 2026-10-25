from django.apps import AppConfig


class PenilaianConfig(AppConfig):
    name = "apps.penilaian"
    verbose_name = "Penilaian"

    def ready(self):
        from auditlog.registry import auditlog

        from . import models

        auditlog.register(models.PeriodeAkreditasi)
        auditlog.register(models.PenilaianEP)
        auditlog.register(models.KriteriaPredikat)
        auditlog.register(models.SyaratPredikat)
        auditlog.register(models.TargetPokja)
