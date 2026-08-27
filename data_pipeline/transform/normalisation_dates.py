"""
Normalisation des formats de date sur l'ensemble des sources.

Compétence visée : C3 (épreuve E1) — homogénéisation des données

Constat mesuré sur les 6 876 enregistrements bruts des cinq extracteurs :

    source     champ      forme rencontrée
    ---------  ---------  ----------------------------------------
    api_rest   cree_le    entier   1217844432   (époque Unix, UTC)
    big_data   cree_le    chaîne   2015-01-06T05:34:09.967000 (sans fuseau)
    scraping   —          absent
    fichier    —          absent
    base_donnees cree_le  chaîne   ISO 8601 avec fuseau

Quatre formes différentes pour une même notion. Sans normalisation, tout tri
chronologique du corpus, toute purge par ancienneté et toute comparaison entre
sources sont faussés — un entier et une chaîne ne se comparent pas, et une
date sans fuseau se décale selon la machine qui la lit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

#: Bornes de plausibilité pour une époque Unix exprimée en secondes.
#: 2001-09-09 et 2033-05-18. Un horodatage en millisecondes tombe très
#: au-delà : la borne haute le démasque au lieu de produire une date en 55 000.
EPOQUE_MIN = 1_000_000_000
EPOQUE_MAX = 2_000_000_000


def normaliser_horodatage(valeur: Any) -> str | None:
    """
    Ramène un horodatage de n'importe quelle source à l'ISO 8601 UTC.

    Compétence visée : C3 (épreuve E1)

    Choix : ISO 8601 avec fuseau explicite, en UTC. Motivation : c'est le seul
    format qui se trie correctement comme une chaîne de caractères, que
    PostgreSQL accepte tel quel en `timestamptz`, et qui ne dépend pas du
    fuseau de la machine qui l'écrit ou le lit. Les trois propriétés sont
    nécessaires ici, puisque le corpus est trié, chargé en base, et produit sur
    un poste dont le fuseau n'est pas celui du serveur.

    Choix : une date sans fuseau est interprétée comme UTC et non comme heure
    locale. Motivation : les deux sources concernées — l'API Stack Exchange et
    les dumps Stack Exchange — publient en UTC. Supposer l'heure locale
    décalerait tout le corpus de deux heures en été.

    Choix : retourner None plutôt qu'une date de repli en cas d'échec.
    Motivation : une date inventée est indétectable en aval, alors qu'une date
    absente se voit et se compte. Le rapport de transformation dénombre les
    échecs.

    Returns:
        Chaîne ISO 8601 en UTC, ou None si la valeur est absente ou illisible.
    """
    if valeur is None or valeur == "":
        return None

    if isinstance(valeur, bool):
        # Un booléen est un entier en Python : sans ce cas, True deviendrait
        # le 1er janvier 1970 à 00:00:01.
        return None

    if isinstance(valeur, (int, float)):
        return _depuis_epoque(valeur)

    if isinstance(valeur, datetime):
        return _forcer_utc(valeur)

    if isinstance(valeur, str):
        return _depuis_chaine(valeur)

    return None


def _depuis_epoque(valeur: int | float) -> str | None:
    """
    Convertit une époque Unix en ISO 8601 UTC.

    Compétence visée : C3 (épreuve E1)

    Choix : contrôler la plausibilité avant de convertir. Motivation : une API
    qui change d'unité — secondes vers millisecondes — produirait sinon des
    dates en l'an 55 000 que rien ne signalerait. Le contrôle transforme un
    changement silencieux de contrat en erreur comptée.
    """
    if not EPOQUE_MIN <= valeur <= EPOQUE_MAX:
        logger.warning(
            "Horodatage hors bornes de plausibilité, écarté : %r "
            "(secondes attendues entre %d et %d)",
            valeur, EPOQUE_MIN, EPOQUE_MAX,
        )
        return None
    return datetime.fromtimestamp(valeur, tz=timezone.utc).isoformat()


def _depuis_chaine(valeur: str) -> str | None:
    """
    Analyse une chaîne de date ISO, avec ou sans fuseau.

    Compétence visée : C3 (épreuve E1)

    Choix : `datetime.fromisoformat` plutôt qu'une expression régulière ou une
    dépendance de parsing. Motivation : les formats effectivement rencontrés
    sont tous des variantes d'ISO 8601. Ajouter une bibliothèque pour couvrir
    des formats que le corpus ne contient pas serait une dépendance sans
    justification.
    """
    texte = valeur.strip()
    if not texte:
        return None

    # Le suffixe Z est admis par la norme mais refusé par fromisoformat avant
    # Python 3.11. La substitution garantit le même comportement quelle que
    # soit la version.
    if texte.endswith("Z"):
        texte = texte[:-1] + "+00:00"

    try:
        moment = datetime.fromisoformat(texte)
    except ValueError:
        logger.warning("Date non analysable, écartée : %r", valeur)
        return None

    return _forcer_utc(moment)


def _forcer_utc(moment: datetime) -> str:
    """
    Attache le fuseau UTC à une date qui n'en a pas, convertit celles qui en ont.

    Compétence visée : C3 (épreuve E1)
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def normaliser_dates_du_document(document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Normalise toutes les dates d'un enregistrement brut.

    Compétence visée : C3 (épreuve E1)

    Les dates vivent à deux endroits : `extrait_le` à la racine, produit par le
    socle commun, et un champ de création dans les métadonnées, dont le nom et
    la forme varient selon la source.

    Returns:
        Le document modifié, et un drapeau indiquant si une date a été perdue
        en chemin — le rapport de transformation les dénombre.
    """
    perte = False

    extrait = normaliser_horodatage(document.get("extrait_le"))
    if extrait is None and document.get("extrait_le"):
        perte = True
    document["extrait_le"] = extrait

    metadonnees = document.get("metadonnees") or {}
    for cle in ("cree_le", "date_echec", "date_erreur", "date_correction"):
        if cle in metadonnees:
            valeur_initiale = metadonnees[cle]
            metadonnees[cle] = normaliser_horodatage(valeur_initiale)
            if metadonnees[cle] is None and valeur_initiale not in (None, ""):
                perte = True

    document["metadonnees"] = metadonnees
    return document, perte
