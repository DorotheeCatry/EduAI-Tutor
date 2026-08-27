from django.apps import AppConfig


class ApiDataConfig(AppConfig):
    """
    Application exposant le jeu de données de eduai_data en lecture seule.

    Compétence visée : C5 (épreuve E1)
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api_data"
    label = "api_data"
    verbose_name = "API du jeu de données"
