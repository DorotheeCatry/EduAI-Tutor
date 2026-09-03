"""
Stockage des fichiers statiques collectés.

Compétence visée : C13 (épreuve E3) — mise en production
Compétence visée : C17 (épreuve E4) — application web
"""

from pathlib import Path

from django.conf import settings
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


def version_de_la_feuille(request):
    """
    Rend un suffixe de version pour la feuille de style, en développement.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5) — incidents

    En production, le stockage empreinte le nom du fichier
    (`tailwind.60e3e678.css`) : un changement de feuille change l'URL, et le
    navigateur va la rechercher. En développement, l'URL est fixe — le
    navigateur garde donc l'ancienne feuille en cache, et une modification de
    style n'apparaît pas. Le 03/09/2026, une couleur pourtant servie par le
    serveur est restée invisible à l'écran pour cette seule raison.

    Choix : la date de modification du fichier, et non un identifiant aléatoire.
    Motivation : elle ne change QUE lorsque la feuille change. Un identifiant
    tiré à chaque requête ferait retélécharger la feuille en permanence, ce qui
    masquerait le problème inverse — une feuille qui ne se reconstruit plus.

    Choix : vide hors développement. Motivation : l'empreinte y fait déjà ce
    travail, mieux ; ajouter un paramètre par-dessus n'ajouterait qu'un cache
    de plus à comprendre.
    """
    if not settings.DEBUG:
        return {"version_feuille": ""}

    feuille = Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css"
    try:
        return {"version_feuille": f"?v={int(feuille.stat().st_mtime)}"}
    except OSError:
        # Feuille absente : le gabarit s'en passe plutôt que d'échouer.
        return {"version_feuille": ""}
