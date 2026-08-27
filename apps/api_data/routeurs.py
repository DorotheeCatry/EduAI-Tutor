"""
Routeur de base de données : aiguillage de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API exposant le jeu de données
Compétence visée : C4 (épreuve E1) — séparation des deux bases

Le projet tient deux bases sur une même instance PostgreSQL (décision 006) :

    eduai_app   application Django, schéma géré par les migrations
    eduai_data  jeu de données du pipeline, schéma géré par des scripts SQL

Django ne sait pas nativement qu'un modèle vit ailleurs que dans `default`.
Sans routeur, toute requête de l'application `api_data` interrogerait
`eduai_app`, où les treize tables du jeu de données n'existent pas — l'erreur
serait un « relation does not exist » déroutant, très loin de sa cause.
"""

from __future__ import annotations

#: Application dont les modèles vivent dans la base du jeu de données.
APPLICATION_JEU_DONNEES = "api_data"

#: Nom de la connexion Django vers eduai_data.
CONNEXION_JEU_DONNEES = "eduai_data"


class EcritureInterdite(Exception):
    """
    Levée lorsqu'un code tente d'écrire dans le jeu de données via l'ORM.

    Compétence visée : C5 (épreuve E1)

    Choix : une exception nommée plutôt qu'un retour silencieux. Motivation :
    un routeur qui renvoie `None` sur `db_for_write` laisse Django choisir la
    base par défaut — l'écriture partirait donc vers `eduai_app`, où la table
    n'existe pas, avec un message d'erreur sans rapport avec la faute commise.
    """


class RouteurJeuDonnees:
    """
    Aiguille les modèles du jeu de données vers eduai_data, en lecture seule.

    Compétence visée : C5 (épreuve E1)

    Choix : trois garde-fous superposés plutôt qu'un seul, chacun tenu par un
    acteur différent.

      1. Ce routeur refuse les écritures — garantie tenue par le code Django.
      2. Les vues sont des `ReadOnlyModelViewSet` : aucune route d'écriture
         n'est même exposée — garantie tenue par le routage HTTP.
      3. La connexion utilise un rôle PostgreSQL n'ayant que le SELECT —
         garantie tenue par le moteur.

    Motivation : les trois échouent différemment. Un bogue dans le routeur ne
    contourne pas le rôle PostgreSQL ; un point de terminaison ajouté par
    distraction ne contourne ni l'un ni l'autre. Le principe est celui appliqué
    partout dans ce projet : une règle qui ne vit qu'à un seul endroit finit
    par être oubliée à cet endroit-là.
    """

    def db_for_read(self, model, **indices):
        """
        Dirige les lectures des modèles du jeu de données vers eduai_data.

        Compétence visée : C5 (épreuve E1)
        """
        if model._meta.app_label == APPLICATION_JEU_DONNEES:
            return CONNEXION_JEU_DONNEES
        return None

    def db_for_write(self, model, **indices):
        """
        Refuse toute écriture sur le jeu de données.

        Compétence visée : C5 (épreuve E1)

        L'API expose le corpus, elle ne le modifie pas. Le jeu de données n'est
        écrit que par le pipeline, qui utilise psycopg directement et ne passe
        pas par l'ORM Django.
        """
        if model._meta.app_label == APPLICATION_JEU_DONNEES:
            raise EcritureInterdite(
                f"Écriture refusée sur {model._meta.label} : la base "
                f"eduai_data est exposée en lecture seule par l'API du jeu de "
                "données. Son alimentation relève du pipeline "
                "(data_pipeline/load/chargeur.py)."
            )
        return None

    def allow_relation(self, obj1, obj2, **indices):
        """
        Autorise les relations entre modèles d'une même base.

        Compétence visée : C5 (épreuve E1)

        Choix : autoriser explicitement les relations internes au jeu de
        données. Motivation : sans cela, Django refuse de suivre une clé
        étrangère entre deux modèles qu'il croit sur des bases différentes, et
        `select_related` échoue au moment le moins prévisible.
        """
        etiquettes = {obj1._meta.app_label, obj2._meta.app_label}
        if etiquettes == {APPLICATION_JEU_DONNEES}:
            return True
        if APPLICATION_JEU_DONNEES in etiquettes:
            # Une relation entre le jeu de données et l'application n'a pas de
            # sens : les deux bases sont volontairement étanches (décision 006).
            return False
        return None

    def allow_migrate(self, db, app_label, model_name=None, **indices):
        """
        Interdit toute migration sur le jeu de données.

        Compétence visée : C4 (épreuve E1)

        Le schéma de eduai_data appartient aux scripts de
        `data_pipeline/load/sql/`, pas aux migrations Django (décision 006).
        Deux règles, symétriques :

          - les modèles de `api_data` ne se migrent nulle part ;
          - rien d'autre ne se migre dans la base du jeu de données.

        La seconde compte autant que la première : sans elle, `migrate` créerait
        les tables `django_migrations`, `auth_user` et consorts dans
        `eduai_data`, mêlant le schéma applicatif au jeu de données que la
        décision 006 avait justement séparé.
        """
        if app_label == APPLICATION_JEU_DONNEES:
            return False
        if db == CONNEXION_JEU_DONNEES:
            return False
        return None
