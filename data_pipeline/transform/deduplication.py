"""
Déduplication du corpus agrégé.

Compétence visée : C3 (épreuve E1) — suppression des doublons

État mesuré sur les 6 876 enregistrements bruts des cinq sources :

    collision                          excédents   verdict
    ---------------------------------  ---------   ---------------------------
    identifiant identique                     40   VRAIS doublons
    contenu strictement identique             40   les mêmes 40
    URL source identique                     359   FAUX doublons — à conserver
    titre identique, contenu différent        34   FAUX doublons — à conserver

Les 40 doublons proviennent tous de S1 : la même question Stack Overflow a été
rapatriée sous plusieurs tags de recherche — `so_16476924` est arrivé par
`python` puis par `pandas`. Leur contenu est strictement identique.

Les 359 excédents d'URL sont le piège de ce module. Ils viennent en majorité de
S3, où un fichier Markdown est découpé en sections : les dix-neuf sections de
`itertools-module.md` partagent l'URL du fichier et ont dix-neuf contenus
différents. Dédupliquer sur l'URL supprimerait dix-huit sections sur dix-neuf.
Les 34 collisions de titre sont de même nature : des sections homonymes.

C'est pourquoi ce module ne déduplique que sur l'identifiant et sur l'empreinte
du contenu, jamais sur l'URL ni sur le titre.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def empreinte_contenu(document: dict[str, Any]) -> str:
    """
    Calcule l'empreinte du contenu normalisé d'un document.

    Compétence visée : C3 (épreuve E1)

    Choix : SHA-256 sur le contenu déjà normalisé, et non sur le contenu brut.
    Motivation : deux copies d'un même texte qui ne diffèrent que par une
    espace en fin de ligne ou une forme Unicode donneraient deux empreintes
    différentes. C'est la raison pour laquelle la déduplication s'exécute après
    l'homogénéisation et non avant.

    Choix : le titre n'entre pas dans l'empreinte. Motivation : deux sections
    homonymes de contenus différents ne sont pas des doublons, et deux copies
    d'un même contenu sous deux titres le sont. Le contenu fait foi.
    """
    return hashlib.sha256(document.get("contenu", "").encode("utf-8")).hexdigest()


def _fusionner(conserve: dict[str, Any], double: dict[str, Any]) -> dict[str, Any]:
    """
    Reporte sur le document conservé ce que le doublon apportait de distinct.

    Compétence visée : C3 (épreuve E1)
    Compétence visée : C1 (épreuve E1) — traçabilité de la collecte

    Choix : fusionner plutôt que supprimer sèchement. Motivation : les deux
    copies de `so_16476924` ne diffèrent que par `tag_recherche` — `python`
    pour l'une, `pandas` pour l'autre. Jeter la seconde ferait perdre
    l'information que cette question a été trouvée par deux chemins de
    collecte, alors que C1 demande la traçabilité de l'extraction. La fusion
    conserve les deux.
    """
    mots = set(conserve.get("mots_cles") or []) | set(double.get("mots_cles") or [])
    conserve["mots_cles"] = sorted(mots)

    meta_conserve = conserve.setdefault("metadonnees", {})
    for cle, valeur in (double.get("metadonnees") or {}).items():
        if cle not in meta_conserve:
            meta_conserve[cle] = valeur
        elif meta_conserve[cle] != valeur:
            # Valeurs concurrentes : on les accumule dans une liste triée
            # plutôt que d'en choisir une arbitrairement.
            existantes = meta_conserve[cle]
            if not isinstance(existantes, list):
                existantes = [existantes]
            if valeur not in existantes:
                existantes.append(valeur)
            meta_conserve[cle] = sorted(existantes, key=str)

    # La date d'extraction retenue est la plus ancienne : c'est celle de la
    # première collecte effective du document.
    dates = [d for d in (conserve.get("extrait_le"), double.get("extrait_le")) if d]
    if dates:
        conserve["extrait_le"] = min(dates)

    return conserve


def dedupliquer(documents: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Supprime les doublons stricts et fusionne ce qu'ils apportaient.

    Compétence visée : C3 (épreuve E1)

    Choix : deux clés successives — l'identifiant, puis l'empreinte du contenu.
    Motivation : l'identifiant attrape les doublons d'une même source, où il
    est stable par construction. L'empreinte attrape les doublons entre sources
    différentes, où les identifiants sont forcément distincts puisque chaque
    extracteur préfixe les siens. Sur le corpus actuel les deux clés désignent
    les mêmes 40 enregistrements ; la seconde n'en reste pas moins nécessaire,
    puisqu'un même texte peut parfaitement arriver par l'API et par le dump.

    Choix : conserver le premier rencontré. Motivation : les extracteurs sont
    lus dans l'ordre S1 à S5, et l'ordre de lecture est stable d'une exécution
    à l'autre. La déduplication est donc déterministe — condition de
    l'idempotence exigée par C1.

    Returns:
        La liste dédupliquée, et un rapport chiffré par motif de suppression.
    """
    par_identifiant: dict[str, dict[str, Any]] = {}
    par_empreinte: dict[str, str] = {}
    conserves: list[str] = []

    rapport = {
        "entrants": 0,
        "doublons_identifiant": 0,
        "doublons_contenu": 0,
        "sortants": 0,
        "exemples": [],
    }

    for document in documents:
        rapport["entrants"] += 1
        identifiant = document["identifiant"]

        if identifiant in par_identifiant:
            rapport["doublons_identifiant"] += 1
            _consigner_exemple(rapport, "identifiant", identifiant)
            _fusionner(par_identifiant[identifiant], document)
            continue

        empreinte = empreinte_contenu(document)
        if empreinte in par_empreinte:
            rapport["doublons_contenu"] += 1
            _consigner_exemple(
                rapport, "contenu", f"{identifiant} ≡ {par_empreinte[empreinte]}",
            )
            _fusionner(par_identifiant[par_empreinte[empreinte]], document)
            continue

        par_identifiant[identifiant] = document
        par_empreinte[empreinte] = identifiant
        conserves.append(identifiant)

    resultat = [par_identifiant[identifiant] for identifiant in conserves]
    rapport["sortants"] = len(resultat)

    logger.info(
        "Déduplication : %d entrants, %d doublons d'identifiant, "
        "%d doublons de contenu, %d sortants",
        rapport["entrants"], rapport["doublons_identifiant"],
        rapport["doublons_contenu"], rapport["sortants"],
    )
    return resultat, rapport


def _consigner_exemple(rapport: dict[str, Any], motif: str, detail: str) -> None:
    """
    Retient quelques cas concrets pour le rapport de transformation.

    Compétence visée : C3 (épreuve E1)

    Choix : cinq exemples au plus, et non la liste complète. Motivation : le
    rapport doit rester lisible. Un décompte prouve l'ampleur, quelques cas
    prouvent la nature — la liste exhaustive n'apporte ni l'un ni l'autre.
    """
    if len(rapport["exemples"]) < 5:
        rapport["exemples"].append({"motif": motif, "document": detail})
