from django.apps import AppConfig


class AgentsConfig(AppConfig):
    """
    Application des agents du service IA.

    Compétence visée : C10 (épreuve E3) — intégration du modèle
    Compétence visée : C20 (épreuve E5) — monitorage du service
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agents'

    def ready(self):
        """
        Branche la sonde de monitorage au démarrage de l'application.

        Compétence visée : C20 (épreuve E5)

        Choix : le branchement a lieu dans `ready()` et non à l'import d'un
        module. Motivation : Django appelle `ready()` une seule fois, après le
        chargement complet des réglages. Un branchement à l'import serait rejoué
        à chaque importation du module et parfois avant que les réglages soient
        lus, donc avant que le répertoire de journal soit connu.

        Choix : un échec du branchement n'empêche pas le démarrage. Motivation :
        le monitorage observe le service, il n'en est pas une dépendance. Mais
        l'échec est journalisé en niveau ERROR — un monitorage absent qui se
        tait serait la pire des deux situations.
        """
        try:
            from apps.monitoring.sondes import installer

            installer()
        except Exception as exception:  # noqa: BLE001 — jamais bloquant
            import logging

            logging.getLogger(__name__).error(
                "[monitorage] branchement impossible au démarrage (%s : %s). "
                "Le service fonctionne, les appels ne sont PAS tracés.",
                type(exception).__name__, exception,
            )
