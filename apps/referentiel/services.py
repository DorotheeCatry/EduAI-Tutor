"""
Lecture du référentiel actif, pour les vues et les gabarits.

Compétence visée : C17 (épreuve E4) — application web

Ces fonctions sont le seul chemin par lequel le reste de l'application atteint
le référentiel. Elles rendent toutes quelque chose d'exploitable quand aucun
référentiel n'est actif — liste vide, `None` — plutôt que de lever : une
application dont la page d'accueil tombe parce qu'un exploitant a oublié
`--activer` serait une application fragile pour une raison administrative.
"""

from apps.referentiel.models import Competence, Referentiel


def referentiel_actif():
    """
    Rend le référentiel actif, ou `None` s'il n'y en a pas.

    Compétence visée : C17 (épreuve E4)
    """
    return Referentiel.objects.filter(est_actif=True).first()


def competences_du_referentiel_actif():
    """
    Rend les compétences du référentiel actif, module par module.

    Compétence visée : C17 (épreuve E4)

    La forme rendue — une liste de couples (module, compétences) — est celle
    dont un gabarit a besoin pour construire un menu groupé. La construire ici
    évite de la reconstruire dans chaque vue, et évite surtout qu'un gabarit
    fasse une requête par module.
    """
    referentiel = referentiel_actif()
    if referentiel is None:
        return []

    return [
        (module, list(module.competences.all()))
        for module in referentiel.modules.prefetch_related("competences")
    ]


def competence_par_code(code):
    """
    Rend la compétence du référentiel actif portant ce code, ou `None`.

    Compétence visée : C17 (épreuve E4)

    Choix : `None` plutôt qu'une exception, et jamais de rattachement
    approchant. Motivation : un code inconnu vient d'un formulaire modifié, ou
    d'un référentiel rechargé entre l'affichage et l'envoi. Rattacher « au plus
    proche » produirait une progression fausse que rien ne signalerait ; ne
    rien rattacher se voit, puisque l'exercice s'affiche alors comme non
    rattaché.
    """
    if not code:
        return None

    return Competence.objects.filter(
        code=code, module__referentiel__est_actif=True,
    ).select_related("module").first()
