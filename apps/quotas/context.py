"""
Mise à disposition du quota restant dans les gabarits.

Compétence visée : C17 (épreuve E4) — application web
Compétence visée : C13 (épreuve E3) — le coût est visible, pas seulement borné

Un apprenant ne doit pas découvrir le plafond au moment du refus. Le compteur
s'affiche donc avant la génération, sur les pages qui en déclenchent une.
"""

from __future__ import annotations

import logging

from django.utils.functional import SimpleLazyObject

from .service import etat

logger = logging.getLogger(__name__)


def quota_generation(request) -> dict:
    """
    Expose l'état du quota du jour aux gabarits.

    Compétence visée : C17 (épreuve E4)

    Choix : un processeur de contexte plutôt qu'un ajout au contexte de chaque
    vue. Motivation : quatre vues déclenchent une génération, et rien n'empêche
    qu'une cinquième apparaisse. Un ajout par vue serait oublié une fois ; le
    processeur rend le compteur disponible partout, et c'est le gabarit qui
    décide de l'afficher.

    Choix : `SimpleLazyObject`. Motivation : sans lui, chaque page du site
    paierait une requête d'agrégation pour un compteur que la plupart
    n'affichent pas. La valeur n'est calculée qu'au premier accès depuis un
    gabarit — donc uniquement sur les pages qui l'affichent réellement.

    Choix : `None` en cas d'échec, jamais d'exception. Motivation : le compteur
    est une indication de confort. Une table absente ou une base momentanément
    injoignable ne doit pas faire tomber une page qui, sans lui, fonctionne. Le
    contrôle du quota, lui, reste appliqué au moment de la génération : ce qui
    est facultatif ici, c'est l'affichage, pas la limite.
    """
    def calculer():
        utilisateur = getattr(request, "user", None)
        if utilisateur is None or not utilisateur.is_authenticated:
            return None
        try:
            return etat(utilisateur)
        except Exception as exception:  # noqa: BLE001 — l'affichage n'est pas critique
            logger.warning(
                "Compteur de quota non affichable (%s : %s). "
                "La limite reste appliquée à la génération.",
                type(exception).__name__, exception,
            )
            return None

    return {"quota_generation": SimpleLazyObject(calculer)}
