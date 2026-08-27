"""
Estimation du coût des appels au fournisseur de modèles.

Compétence visée : C20 (épreuve E5) — suivi de l'exploitation
Compétence visée : C7 (épreuve E2) — comparaison de services d'IA

Choix : les tarifs vivent dans un fichier JSON distinct du code, et un modèle
sans tarif connu donne un coût NUL et non zéro. Motivation : un coût de zéro se
confond avec un appel gratuit, alors qu'un coût inconnu doit se voir. Inventer
un tarif produirait un chiffre présentable et faux — exactement le motif des
quatre incidents du projet, un rapport plausible qui ne correspond à rien.

Le fichier `tarifs.json` porte pour chaque modèle le prix au million de jetons
en entrée et en sortie, la devise, et un drapeau `a_verifier`. Tant que ce
drapeau est vrai, chaque événement de coût le transporte : le rapport annonce
alors une estimation explicitement non vérifiée, plutôt qu'un chiffre sec.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CHEMIN_TARIFS = Path(__file__).resolve().parent / "tarifs.json"

#: Modèles déjà signalés comme sans tarif. Évite de répéter l'avertissement à
#: chaque appel — un journal noyé sous la répétition ne se lit plus.
_MODELES_SIGNALES: set[str] = set()

_TARIFS_CACHE: dict[str, Any] | None = None


def _charger_tarifs() -> dict[str, Any]:
    """
    Charge la table des tarifs, une seule fois par processus.

    Compétence visée : C20 (épreuve E5)

    Choix : un fichier absent n'est pas une erreur. Motivation : le monitorage
    doit fonctionner sans table de tarifs — les jetons, eux, sont mesurés
    réellement. Seule l'estimation monétaire manque, et son absence est dite.
    """
    global _TARIFS_CACHE
    if _TARIFS_CACHE is not None:
        return _TARIFS_CACHE

    if not CHEMIN_TARIFS.is_file():
        logger.warning(
            "Table de tarifs absente (%s) : les coûts ne seront pas estimés. "
            "Les jetons restent comptés.", CHEMIN_TARIFS,
        )
        _TARIFS_CACHE = {}
        return _TARIFS_CACHE

    try:
        _TARIFS_CACHE = json.loads(CHEMIN_TARIFS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        logger.error(
            "Table de tarifs illisible (%s) : %s. Les coûts ne seront pas "
            "estimés.", CHEMIN_TARIFS, exception,
        )
        _TARIFS_CACHE = {}
    return _TARIFS_CACHE


def estimer(modele: str, jetons_entree: int | None,
            jetons_sortie: int | None) -> dict[str, Any]:
    """
    Estime le coût d'un appel à partir des jetons réellement consommés.

    Compétence visée : C20 (épreuve E5)

    Choix : l'estimation part des jetons rapportés par le fournisseur, jamais
    d'une longueur de texte multipliée par un ratio. Motivation : le ratio
    caractères/jetons varie du simple au double selon la langue et le contenu.
    Le fournisseur, lui, facture ce qu'il a compté.

    Returns:
        Un dictionnaire toujours renseigné, dont `cout_estime` peut valoir
        None. La clé `motif_sans_cout` dit alors pourquoi.
    """
    tarifs = _charger_tarifs()
    tarif = (tarifs.get("modeles") or {}).get(modele)

    if tarif is None:
        if modele not in _MODELES_SIGNALES:
            _MODELES_SIGNALES.add(modele)
            logger.warning(
                "Aucun tarif connu pour le modèle « %s » : coût non estimé. "
                "Compléter %s pour l'obtenir.", modele, CHEMIN_TARIFS.name,
            )
        return {
            "cout_estime": None,
            "devise": None,
            "tarif_a_verifier": None,
            "motif_sans_cout": "modele_absent_de_la_table",
        }

    if jetons_entree is None or jetons_sortie is None:
        return {
            "cout_estime": None,
            "devise": tarif.get("devise"),
            "tarif_a_verifier": tarif.get("a_verifier", True),
            "motif_sans_cout": "jetons_non_rapportes_par_le_fournisseur",
        }

    cout = (
        jetons_entree / 1_000_000 * float(tarif.get("entree_par_million", 0))
        + jetons_sortie / 1_000_000 * float(tarif.get("sortie_par_million", 0))
    )
    return {
        # Six décimales : un appel court coûte quelques millionièmes d'unité,
        # arrondir à deux décimales afficherait zéro partout.
        "cout_estime": round(cout, 6),
        "devise": tarif.get("devise"),
        "tarif_a_verifier": tarif.get("a_verifier", True),
        "motif_sans_cout": None,
    }
