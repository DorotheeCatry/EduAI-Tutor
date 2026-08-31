from django.apps import AppConfig


class AccueilConfig(AppConfig):
    """
    Page d'accueil : où j'en suis, et que faire maintenant.

    Compétence visée : C17 (épreuve E4) — application web
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accueil"
    verbose_name = "Accueil"
