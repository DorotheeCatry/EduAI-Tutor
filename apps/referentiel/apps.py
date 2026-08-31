from django.apps import AppConfig


class ReferentielConfig(AppConfig):
    """
    Référentiel de compétences, importé depuis un fichier.

    Compétence visée : C17 (épreuve E4) — application web
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.referentiel"
    verbose_name = "Référentiel de compétences"
