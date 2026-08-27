"""
Point de lancement unique du flux de données complet.

Compétence visée : C1 (épreuve E1) — « le script comprend un point de lancement »
Compétence visée : C3 (épreuve E1) — enchaînement de la transformation
Compétence visée : C4 (épreuve E1) — enchaînement du chargement
Compétence visée : C20 (épreuve E5) — rapport d'exécution consolidé

    extraction (cinq sources) -> transformation -> chargement

Lancement :

    uv run python -m data_pipeline.orchestrator

Choix : un orchestrateur qui appelle les mêmes classes et fonctions que les
scripts individuels, et non un script qui les relance en sous-processus.
Motivation : les extracteurs restent lançables séparément — c'est ce qui rend
la couverture des cinq types lisible pour un lecteur du dépôt, et ce qui permet
de rejouer une seule source après incident. L'orchestrateur ajoute
l'enchaînement, il ne le remplace pas.

Choix : l'échec d'une source n'interrompt pas le flux par défaut. Motivation :
les cinq sources sont indépendantes. Perdre l'extraction de Stack Overflow ne
justifie pas de renoncer aux quatre autres, ni de laisser la base sur un corpus
plus ancien. L'échec est consigné, le code de sortie le reflète, et la sortie
précédente de la source en échec est conservée par le socle d'extraction.

Choix : le chargement est sauté si la transformation échoue. Motivation : le
chargeur lirait alors un corpus absent ou périmé, et écrirait en base un état
qui ne correspond à aucune extraction. Les deux étapes ne sont pas symétriques
— l'une produit ce que l'autre consomme.
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances ---

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .extract.base_extractor import REPERTOIRE_BRUT
from .extract.s1_api_stackoverflow import ExtracteurStackOverflow
from .extract.s2_scraping_python_docs import ExtracteurPythonDocs
from .extract.s3_fichiers_corpus import ExtracteurCorpusLocal
from .extract.s4_base_donnees_eduai_app import ExtracteurBaseDonneesEduaiApp
from .extract.s5_bigdata_stackexchange import ExtracteurBigDataStackExchange
from .load.chargeur import Chargeur, ecrire_rapport as ecrire_rapport_chargement
from .transform.transformer import (
    REPERTOIRE_TRANSFORME,
    transformer as transformer_corpus,
)

logger = logging.getLogger(__name__)

#: Les cinq sources, dans l'ordre des codes.
#:
#: Choix : une table explicite plutôt qu'une découverte automatique des modules
#: du paquet `extract`. Motivation : le référentiel exige cinq types de sources
#: distincts, et cette table est la preuve, lisible d'un coup d'œil, qu'ils sont
#: tous branchés au flux. Une découverte dynamique masquerait une source
#: silencieusement retirée.
SOURCES = [
    ("s1", "Stack Overflow (service web)", ExtracteurStackOverflow),
    ("s2", "Documentation Python (scraping)", ExtracteurPythonDocs),
    ("s3", "Corpus local (fichiers)", ExtracteurCorpusLocal),
    ("s4", "eduai_app (base de données)", ExtracteurBaseDonneesEduaiApp),
    ("s5", "Dump Stack Exchange (big data)", ExtracteurBigDataStackExchange),
]

#: Statuts d'extraction considérés comme un déroulement normal.
#: « vide » en fait partie : une base applicative sans production d'apprenant
#: n'est pas une panne (voir docs/decisions/010).
STATUTS_NORMAUX = {"succes", "vide"}


# --- 2. Règles logiques de traitement ---

def executer_extractions(codes: list[str] | None = None) -> dict[str, Any]:
    """
    Lance les extracteurs demandés et rassemble leurs bilans.

    Compétence visée : C1 (épreuve E1)

    Choix : chaque extracteur est protégé individuellement. Motivation : une
    exception dans S1 ne doit pas empêcher S3 de s'exécuter. Le socle
    d'extraction relance ses exceptions après les avoir journalisées ; c'est
    ici qu'elles sont rattrapées, pour que le flux continue.

    Args:
        codes: codes de source à lancer, ou None pour les cinq.
    """
    bilans: dict[str, Any] = {}

    for code, libelle, classe in SOURCES:
        if codes and code not in codes:
            logger.info("[%s] %s — non demandée, sautée.", code, libelle)
            continue

        logger.info("─" * 72)
        logger.info("[%s] %s", code, libelle)
        debut = datetime.now(timezone.utc)
        try:
            bilan = classe().executer()
        except Exception as exception:  # noqa: BLE001 — consigné, le flux continue
            duree = (datetime.now(timezone.utc) - debut).total_seconds()
            logger.exception("[%s] Extraction interrompue : %s", code, exception)
            bilans[code] = {
                "code_source": code,
                "statut": "echec",
                "enregistrements": 0,
                "erreurs": 1,
                "duree_secondes": round(duree, 2),
                "exception": f"{type(exception).__name__}: {exception}",
            }
            continue

        bilans[code] = bilan
        if bilan["statut"] not in STATUTS_NORMAUX:
            logger.error(
                "[%s] Statut « %s » : la sortie précédente a été conservée, "
                "le corpus n'a pas été appauvri.", code, bilan["statut"],
            )

    return bilans


def executer_transformation() -> dict[str, Any]:
    """
    Lance la couche de transformation sur l'ensemble des sorties brutes.

    Compétence visée : C3 (épreuve E1)
    """
    logger.info("─" * 72)
    logger.info("Transformation du corpus")
    return transformer_corpus(REPERTOIRE_BRUT, REPERTOIRE_TRANSFORME)


def executer_chargement() -> dict[str, Any]:
    """
    Lance le chargement du corpus transformé dans eduai_data.

    Compétence visée : C4 (épreuve E1)
    """
    logger.info("─" * 72)
    logger.info("Chargement dans eduai_data")
    chargeur = Chargeur()
    try:
        chargeur.initialiser()
        rapport = chargeur.charger()
    finally:
        chargeur.nettoyer()
    ecrire_rapport_chargement(rapport, REPERTOIRE_TRANSFORME)
    return rapport


# --- 3. Gestion des erreurs et exceptions ---

def evaluer(rapport: dict[str, Any]) -> int:
    """
    Traduit le rapport consolidé en code de sortie.

    Compétence visée : C1 (épreuve E1)
    Compétence visée : C21 (épreuve E5)

    Choix : un code de sortie distinct par nature de problème, et jamais zéro
    quand une étape a échoué. Motivation : c'est le seul signal qu'un
    ordonnanceur ou une intégration continue sait lire. Un flux qui rend zéro
    après avoir perdu une source répète l'erreur des deux incidents du projet —
    rendre compte de son intention plutôt que de son effet.

        0  tout s'est bien passé
        1  le chargement a échoué
        2  la transformation a échoué, le chargement n'a pas été tenté
        3  au moins une source a échoué, le reste du flux a abouti
    """
    if rapport["etapes"].get("transformation", {}).get("statut") == "echec":
        return 2
    if rapport["etapes"].get("chargement", {}).get("statut") == "echec":
        return 1
    sources_en_echec = [
        code for code, bilan in rapport["etapes"].get("extraction", {}).items()
        if bilan.get("statut") not in STATUTS_NORMAUX
    ]
    return 3 if sources_en_echec else 0


# --- 4. Sauvegarde des résultats ---

def ecrire_rapport_consolide(rapport: dict[str, Any], repertoire: Path) -> Path:
    """
    Écrit le rapport d'exécution du flux complet.

    Compétence visée : C20 (épreuve E5) — suivi d'un traitement

    Choix : un rapport horodaté par exécution, et non un fichier unique écrasé.
    Motivation : la comparaison de deux exécutions successives est ce qui révèle
    une source qui se dégrade — un volume qui s'effondre, une durée qui dérive.
    Un fichier écrasé à chaque passage détruit précisément cette information.
    C'est la leçon tirée du rapport de métriques de S5, écrasé deux fois avant
    d'être protégé.
    """
    repertoire.mkdir(parents=True, exist_ok=True)
    horodatage = rapport["horodatage"].replace(":", "").replace("-", "")[:15]
    chemin = repertoire / f"execution_{horodatage}.json"
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Rapport d'exécution écrit : %s", chemin)
    return chemin


def resumer(rapport: dict[str, Any]) -> None:
    """
    Affiche le tableau récapitulatif du flux.

    Compétence visée : C20 (épreuve E5)
    """
    logger.info("═" * 72)
    logger.info("RAPPORT D'EXÉCUTION DU FLUX")
    logger.info("═" * 72)

    extraction = rapport["etapes"].get("extraction", {})
    if extraction:
        logger.info("  Extraction")
        for code, bilan in sorted(extraction.items()):
            logger.info(
                "    %-4s %-8s %6d enregistrements  %5d erreurs  %8.2f s",
                code, bilan.get("statut", "?"), bilan.get("enregistrements", 0),
                bilan.get("erreurs", 0), bilan.get("duree_secondes", 0),
            )

    transformation = rapport["etapes"].get("transformation")
    if transformation and transformation.get("statut") != "saute":
        detail = transformation.get("detail", {})
        dedup = detail.get("deduplication", {})
        logger.info(
            "  Transformation  %d entrants, %d doublons retirés, %d sortants, %.2f s",
            detail.get("entrants", 0),
            dedup.get("doublons_identifiant", 0) + dedup.get("doublons_contenu", 0),
            detail.get("sortants", 0), detail.get("duree_secondes", 0),
        )

    chargement = rapport["etapes"].get("chargement")
    if chargement and chargement.get("statut") != "saute":
        detail = chargement.get("detail", {})
        logger.info(
            "  Chargement      %d documents, %d campagnes, %d mots-clés, "
            "%d collectes, %d rejets, %.2f s",
            detail.get("documents_charges", 0),
            len(detail.get("campagnes_chargees", {})),
            detail.get("mots_cles_charges", 0),
            detail.get("collectes_chargees", 0),
            len(detail.get("rejets", [])), detail.get("duree_secondes", 0),
        )

    logger.info("  Durée totale    %.2f s", rapport["duree_secondes"])
    logger.info("═" * 72)


# --- 5. Point de lancement ---

def executer_flux(codes: list[str] | None = None, avec_extraction: bool = True,
                  avec_chargement: bool = True) -> dict[str, Any]:
    """
    Enchaîne les trois étapes du flux et consolide leurs rapports.

    Compétence visée : C1 (épreuve E1) — point de lancement unique
    """
    debut = datetime.now(timezone.utc)
    rapport: dict[str, Any] = {"horodatage": debut.isoformat(), "etapes": {}}

    if avec_extraction:
        rapport["etapes"]["extraction"] = executer_extractions(codes)
    else:
        logger.info("Extraction sautée — le corpus brut existant est réutilisé.")

    try:
        detail = executer_transformation()
        rapport["etapes"]["transformation"] = {"statut": "succes", "detail": detail}
    except Exception as exception:  # noqa: BLE001 — consigné puis traduit en code
        logger.exception("Transformation interrompue : %s", exception)
        rapport["etapes"]["transformation"] = {
            "statut": "echec", "exception": f"{type(exception).__name__}: {exception}",
        }
        rapport["etapes"]["chargement"] = {
            "statut": "saute",
            "motif": "la transformation a échoué : le chargement lirait un "
                     "corpus absent ou périmé",
        }
        rapport["duree_secondes"] = round(
            (datetime.now(timezone.utc) - debut).total_seconds(), 2)
        return rapport

    if not avec_chargement:
        rapport["etapes"]["chargement"] = {
            "statut": "saute", "motif": "chargement non demandé",
        }
    else:
        try:
            detail = executer_chargement()
            rapport["etapes"]["chargement"] = {"statut": "succes", "detail": detail}
        except Exception as exception:  # noqa: BLE001 — consigné puis traduit
            logger.exception("Chargement interrompu : %s", exception)
            rapport["etapes"]["chargement"] = {
                "statut": "echec",
                "exception": f"{type(exception).__name__}: {exception}",
            }

    rapport["duree_secondes"] = round(
        (datetime.now(timezone.utc) - debut).total_seconds(), 2)
    return rapport


def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement unique du flux de données.

    Compétence visée : C1 (épreuve E1)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    analyseur = argparse.ArgumentParser(
        description=(
            "Flux de données complet : extraction des cinq sources, "
            "transformation, chargement dans eduai_data."
        ),
    )
    analyseur.add_argument(
        "--sources", default=None,
        help="Codes de source à extraire, séparés par des virgules (ex. s3,s5). "
             "Par défaut, les cinq.",
    )
    analyseur.add_argument(
        "--sans-extraction", action="store_true",
        help="Réutilise les sorties brutes existantes au lieu de réextraire.",
    )
    analyseur.add_argument(
        "--sans-chargement", action="store_true",
        help="S'arrête après la transformation, sans écrire en base.",
    )
    arguments = analyseur.parse_args(argv)

    codes = None
    if arguments.sources:
        codes = [c.strip() for c in arguments.sources.split(",") if c.strip()]
        connus = {code for code, _, _ in SOURCES}
        inconnus = sorted(set(codes) - connus)
        if inconnus:
            logger.error(
                "Codes de source inconnus : %s. Codes valides : %s.",
                ", ".join(inconnus), ", ".join(sorted(connus)),
            )
            return 2

    rapport = executer_flux(
        codes=codes,
        avec_extraction=not arguments.sans_extraction,
        avec_chargement=not arguments.sans_chargement,
    )

    resumer(rapport)
    code_sortie = evaluer(rapport)
    rapport["code_sortie"] = code_sortie
    ecrire_rapport_consolide(rapport, REPERTOIRE_TRANSFORME)

    if code_sortie:
        logger.error("Flux terminé avec le code %d — voir le rapport.", code_sortie)
    else:
        logger.info("Flux terminé sans erreur.")
    return code_sortie


if __name__ == "__main__":
    sys.exit(main())
