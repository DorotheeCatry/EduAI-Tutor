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
        Enregistre les modèles de l'application, puis branche la sonde.

        Compétence visée : C20 (épreuve E5), C4 (E1) — droit à l'effacement

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
        # L'IMPORT DES MODÈLES, avant tout le reste.
        #
        # Compétence visée : C4 (épreuve E1) — droit à l'effacement
        #
        # Cette application n'a **pas de `models.py`** : `LearningSession` et
        # `UserMistake` vivent dans `agent_watcher.py`. Or Django n'importe
        # automatiquement que `<application>/models.py` au démarrage. Sans cet
        # import, les deux modèles n'étaient donc pas enregistrés au moment où
        # Django calcule — et met en cache — `User._meta.related_objects`.
        #
        # **Conséquence mesurée, et elle n'était pas théorique.** La suppression
        # d'un compte ne cascadait pas vers ces deux tables, PostgreSQL refusait
        # l'opération sur sa contrainte de clé étrangère, et la route qui porte
        # le droit à l'effacement échouait pour **tout compte ayant utilisé
        # l'application** — c'est-à-dire tous. Relevé :
        #
        #     avant cet import : User._meta.related_objects → aucune relation agents
        #     après            : LearningSession, UserMistake
        #
        # L'échec était au moins atomique : rien n'était supprimé à moitié.
        # Voir l'incident 024.
        #
        # Choix : ici plutôt qu'un `models.py` qui réexporterait les classes.
        # Motivation : deux domiciles pour un même modèle est précisément ce qui
        # produit ce genre d'écart. `ready()` est le point que Django prévoit
        # pour cela, et il est appelé une fois, après le chargement des réglages.
        from apps.agents import agent_watcher  # noqa: F401

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
