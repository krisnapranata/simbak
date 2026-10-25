from django.apps import AppConfig


class StandarConfig(AppConfig):
    name = "apps.standar"
    verbose_name = "Master Standar"

    def ready(self):
        from auditlog.registry import auditlog

        from . import models

        for model in (
            models.KelompokStandar,
            models.Bab,
            models.Standar,
            models.ElemenPenilaian,
            models.ItemWawancara,
        ):
            auditlog.register(model)
