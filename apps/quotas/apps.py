"""
Déclaration de l'application de quotas.

Compétence visée : C17 (épreuve E4) — application web
Compétence visée : C13 (épreuve E3) — mise en production maîtrisée
"""

from django.apps import AppConfig


class QuotasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.quotas"
    verbose_name = "Quotas de génération"
