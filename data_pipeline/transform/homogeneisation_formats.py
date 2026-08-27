"""
Homogénéisation des formats entre les cinq sources.

Compétence visée : C3 (épreuve E1) — nettoyage et mise en cohérence

Constat mesuré sur les 6 876 enregistrements bruts : chaque extracteur a nommé
ses métadonnées selon le vocabulaire de sa source.

    api_rest      tags          score            vues   nombre_reponses
    big_data      mots_cles     score_question   vues   nombre_reponses
    scraping      —             —                —      —
    fichier       —             —                —      —

Un corpus où le même concept porte deux noms n'est pas agrégeable : une requête
sur les mots-clés en manquerait les trois quarts. Ce module ramène ces champs à
un vocabulaire unique, et traduit les libellés de licence en codes de la
nomenclature `licence` de `eduai_data`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

#: Traduction des libellés de licence vers les codes de la nomenclature.
#:
#: Choix : une correspondance explicite et fermée plutôt qu'une déduction par
#: expression régulière. Motivation : une licence mal identifiée engage la
#: redistribution du corpus. Mieux vaut une source non reconnue, signalée et
#: comptée, qu'une source rattachée par erreur à une licence permissive.
CODES_LICENCE = {
    "CC BY-SA 4.0": "CC-BY-SA-4.0",
    # CC BY-SA 3.0 et 4.0 sont deux licences distinctes. Le code a été ajouté
    # à la nomenclature après que cette couche eut signalé 1 663 documents
    # sans correspondance — la transformation a servi de contrôle de complétude
    # de la nomenclature, ce qui n'était pas son objet mais reste utile.
    "CC BY-SA 3.0": "CC-BY-SA-3.0",
    "PSF License Agreement": "PSF",
    "Propriétaire — autrice du projet": "PROPRIETAIRE",
    "A VERIFIER": "A_VERIFIER",
    # Source S4. Redistribution interdite : voir 04_donnees_reference.sql.
    "Production des apprenants — usage interne à l'organisme de formation":
        "PRODUCTION-APPRENANT",
}

#: Champs de métadonnées qui décrivent une mesure et non une propriété.
#: Le nom d'arrivée est à gauche, les noms de départ rencontrés à droite.
MESURES = {
    "score": ("score", "score_question"),
    "score_reponse": ("score_reponse",),
    "vues": ("vues",),
    "nombre_reponses": ("nombre_reponses",),
    "minutes_jusqu_correction": ("minutes_jusqu_correction",),
}

#: Noms sous lesquels les extracteurs ont livré les mots-clés.
CHAMPS_MOTS_CLES = ("mots_cles", "tags")

#: Caractères invisibles qui traversent les extractions sans se voir : espace
#: insécable étroit, marque d'ordre des octets, largeur nulle, jointeurs.
INVISIBLES = re.compile(r"[​‌‍⁠﻿]")


def normaliser_texte(texte: str | None) -> str:
    """
    Nettoie un texte sans toucher à sa mise en forme signifiante.

    Compétence visée : C3 (épreuve E1)

    Choix : normalisation Unicode NFC, suppression des caractères invisibles,
    réduction des lignes vides consécutives — et rien de plus. Motivation : la
    tentation serait de réduire aussi les suites d'espaces, ce qui rendrait le
    corpus plus régulier. Ce serait une faute ici : les documents contiennent
    du code Python, dont l'indentation est syntaxique. Un extrait désindenté
    est faux, donc pire qu'absent dans un index sémantique.

    Choix : NFC et non NFD. Motivation : deux écritures d'un « é » — précomposé
    ou lettre suivie d'un accent combinant — sont visuellement identiques mais
    différentes pour une comparaison de chaînes, donc pour la déduplication qui
    suit. NFC est la forme composée, celle que produisent les claviers.
    """
    if not texte:
        return ""
    texte = unicodedata.normalize("NFC", texte)
    texte = INVISIBLES.sub("", texte)
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    texte = re.sub(r"[ \t]+\n", "\n", texte)      # espaces en fin de ligne
    texte = re.sub(r"\n{3,}", "\n\n", texte)      # lignes vides en série
    return texte.strip()


def normaliser_mots_cles(valeurs: Any) -> list[str]:
    """
    Ramène les mots-clés à une liste canonique, triée et sans doublon.

    Compétence visée : C3 (épreuve E1)

    Choix : minuscules, tirets conservés, tri alphabétique. Motivation : les
    étiquettes Stack Exchange sont déjà en minuscules avec tirets
    (`machine-learning`), celles d'autres sources ne le sont pas forcément. Le
    tri rend deux listes identiques comparables sans dépendre de l'ordre
    d'arrivée — ce dont la déduplication a besoin.

    Choix : aucune traduction ni fusion de synonymes. Motivation : décider que
    `ml` et `machine-learning` désignent la même chose est un choix éditorial,
    pas une normalisation de format. Il n'a pas sa place dans cette couche.
    """
    if not valeurs:
        return []
    if isinstance(valeurs, str):
        valeurs = re.split(r"[|,;<>]", valeurs)
    if not isinstance(valeurs, (list, tuple, set)):
        return []

    propres = set()
    for valeur in valeurs:
        mot = normaliser_texte(str(valeur)).lower().strip()
        if mot:
            propres.add(mot)
    return sorted(propres)


def code_licence(libelle: str | None) -> str | None:
    """
    Traduit un libellé de licence en code de la nomenclature `eduai_data`.

    Compétence visée : C3 (épreuve E1)
    Compétence visée : C4 (épreuve E1) — intégrité référentielle

    Choix : retourner None plutôt que de rattacher d'office à une licence
    voisine. Motivation : `CC BY-SA 3.0` et `CC BY-SA 4.0` sont deux licences
    distinctes ; les confondre ferait redistribuer 1 663 documents sous des
    conditions qui ne sont pas les leurs. Une licence non reconnue est
    signalée, comptée dans le rapport, et le chargement tranchera.
    """
    if not libelle:
        return None
    return CODES_LICENCE.get(libelle.strip())


def homogeneiser_document(document: dict[str, Any]) -> dict[str, Any]:
    """
    Applique l'ensemble des règles d'homogénéisation à un enregistrement.

    Compétence visée : C3 (épreuve E1)

    Choix : les métadonnées propres à une source ne sont pas jetées, mais
    reléguées dans `metadonnees` après extraction des champs communs.
    Motivation : `tag_recherche` en S1 ou `site` en S5 n'ont pas d'équivalent
    ailleurs et n'entrent pas dans le vocabulaire commun ; les supprimer
    priverait pourtant le corpus de la traçabilité que C1 exige.
    """
    metadonnees = dict(document.get("metadonnees") or {})

    mots_cles: list[str] = []
    for champ in CHAMPS_MOTS_CLES:
        if champ in metadonnees:
            mots_cles.extend(normaliser_mots_cles(metadonnees.pop(champ)))
    mots_cles = sorted(set(mots_cles))

    metriques: dict[str, Any] = {}
    for nom_arrivee, noms_depart in MESURES.items():
        for nom_depart in noms_depart:
            if nom_depart in metadonnees:
                valeur = metadonnees.pop(nom_depart)
                if valeur is not None:
                    metriques[nom_arrivee] = valeur
                break

    libelle_licence = document.get("licence") or ""

    return {
        "identifiant": document["identifiant"],
        "titre": normaliser_texte(document.get("titre")),
        "contenu": normaliser_texte(document.get("contenu")),
        "code_type_source": document["source_type"],
        "source_nom": document.get("source_nom") or "",
        "source_url": document.get("source_url") or None,
        "code_licence": code_licence(libelle_licence),
        "licence_declaree": libelle_licence,
        "langue": (document.get("langue") or "en").strip().lower()[:2],
        "extrait_le": document.get("extrait_le"),
        "cree_le": metadonnees.pop("cree_le", None),
        "mots_cles": mots_cles,
        "metriques": metriques,
        "metadonnees": metadonnees,
    }
