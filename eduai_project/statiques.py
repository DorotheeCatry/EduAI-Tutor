"""
Stockage des fichiers statiques collectés.

Compétence visée : C13 (épreuve E3) — mise en production
Compétence visée : C17 (épreuve E4) — application web
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class StockageStatiquesTolerant(CompressedManifestStaticFilesStorage):
    """
    Stockage empreinté et compressé, tolérant aux références manquantes.

    Compétence visée : C13 (épreuve E3)

    Choix : une sous-classe plutôt qu'une option de configuration.
    Motivation : `manifest_strict` est un attribut de classe et non un
    paramètre d'initialisation — le déclarer dans `OPTIONS` lève une
    `TypeError` au premier `collectstatic`. La sous-classe est le seul point
    d'accroche prévu, et elle porte ici sa justification.

    Choix : `manifest_strict = False`. Motivation : par défaut, un gabarit qui
    référence un fichier absent du manifeste — une image supprimée, un script
    renommé — provoque une erreur 500 à l'affichage de la page. L'application
    en comporte, hérités de son développement initial. Une page dégradée, à
    laquelle une illustration manque, vaut mieux qu'une page morte pendant une
    démonstration.

    Ce que cette tolérance ne fait pas : elle ne masque rien au moment de la
    construction. `collectstatic` signale les fichiers manquants ; c'est
    seulement l'exécution qui cesse d'en faire une panne.
    """

    manifest_strict = False
