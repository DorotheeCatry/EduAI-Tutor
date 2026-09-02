"""
Point de lancement unique de la couche de transformation.

Compétence visée : C3 (épreuve E1) — nettoyage et agrégation des données

Lit les sorties brutes des cinq extracteurs, applique les trois traitements
dans un ordre imposé, et écrit un corpus unique que le chargeur versera dans
`eduai_data`.

    data_pipeline/data/raw/*.jsonl
        -> 1. normalisation des dates
        -> 2. homogénéisation des formats
        -> 3. déduplication
        -> data_pipeline/data/processed/corpus.jsonl
           data_pipeline/data/processed/rapport_transformation.json

Choix : le chargeur lira `processed/corpus.jsonl` et jamais `raw/`. Motivation :
brancher le chargement sur le brut ferait de la transformation une étape
facultative, que rien n'obligerait à rejouer après modification d'un
extracteur. La couche brute reste intacte et rejouable ; la couche transformée
est la seule entrée du chargement.

Choix : un rapport de qualité écrit à côté du corpus. Motivation : C3 demande
de démontrer le nettoyage, pas seulement de l'effectuer. Un corpus propre ne
prouve rien par lui-même — c'est l'écart chiffré entre l'entrée et la sortie
qui le prouve.
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances ---

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .deduplication import dedupliquer
from .homogeneisation_formats import homogeneiser_document
from .normalisation_dates import normaliser_dates_du_document

logger = logging.getLogger(__name__)

REPERTOIRE_BRUT = Path("data_pipeline/data/raw")
REPERTOIRE_TRANSFORME = Path("data_pipeline/data/processed")

#: Séparateurs de ligne Unicode que `json.dumps` laisse tels quels et qui
#: coupent une ligne JSON Lines en deux pour certains lecteurs. Même
#: neutralisation qu'au niveau du socle d'extraction, pour la même raison :
#: le format repose sur l'équivalence « une ligne = un enregistrement ».
SEPARATEURS_UNICODE = (" ", " ", "")


# --- 2. Règles logiques de traitement ---

def lire_corpus_brut(repertoire: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Lit les sorties de tous les extracteurs, dans un ordre stable.

    Compétence visée : C3 (épreuve E1)

    Choix : parcours trié des fichiers, et lecture ligne à ligne. Motivation :
    l'ordre décide quel exemplaire d'un doublon est conservé. Trié, il est
    identique d'une exécution à l'autre, donc la transformation est idempotente.
    Un `glob` non trié rendrait le corpus légèrement différent à chaque passage,
    ce qui suffirait à casser toute comparaison entre deux exécutions.

    Choix : une ligne illisible est comptée et ignorée, pas fatale. Motivation :
    perdre un corpus entier de plusieurs milliers de documents pour une ligne
    tronquée par une extraction interrompue serait disproportionné.
    """
    for fichier in sorted(repertoire.glob("*.jsonl")):
        lignes = 0
        illisibles = 0
        for numero, ligne in enumerate(fichier.open(encoding="utf-8"), start=1):
            if not ligne.strip():
                continue
            try:
                enregistrement = json.loads(ligne)
            except json.JSONDecodeError as exception:
                illisibles += 1
                logger.warning(
                    "%s ligne %d illisible, ignorée : %s",
                    fichier.name, numero, exception,
                )
                continue
            lignes += 1
            yield fichier.name, enregistrement
        logger.info("%s : %d enregistrements lus, %d illisibles",
                    fichier.name, lignes, illisibles)


def transformer(repertoire_brut: Path, repertoire_sortie: Path) -> dict[str, Any]:
    """
    Enchaîne les trois traitements et produit le corpus transformé.

    Compétence visée : C3 (épreuve E1)

    Choix : l'ordre normalisation, homogénéisation, déduplication n'est pas
    interchangeable. Motivation : la déduplication compare des contenus. Si
    elle passait en premier, deux copies d'un même texte qui ne diffèrent que
    par une espace en fin de ligne ou une forme Unicode seraient tenues pour
    distinctes. Elle vient donc en dernier, sur des documents déjà canoniques.
    """
    debut = datetime.now(timezone.utc)

    rapport: dict[str, Any] = {
        "horodatage": debut.isoformat(),
        "par_fichier": {},
        "dates_perdues": 0,
        "licences_sans_correspondance": {},
    }

    documents: list[dict[str, Any]] = []
    compte_fichier: Counter[str] = Counter()

    for nom_fichier, brut in lire_corpus_brut(repertoire_brut):
        compte_fichier[nom_fichier] += 1

        # Le document porte son code de source, tiré du nom du fichier brut.
        #
        # Compétence visée : C3 (épreuve E1), C4 (E1)
        # Choix : le préfixe du fichier (`s6_documentation…jsonl` → `s6`) plutôt
        # que le type de source. Motivation : le chargeur rattachait jusqu'ici
        # un document à sa source **par son type**, ce qui supposait une source
        # par type. La sixième source est un second scraping : deux sources
        # partagent désormais le type, et le rattachement devenait ambigu — le
        # chargeur refusait de continuer, à juste titre. Le nom du fichier, lui,
        # désigne l'extracteur sans ambiguïté.
        brut["code_source"] = nom_fichier.split("_", 1)[0]

        # 1. Normalisation des dates, avant toute comparaison.
        brut, perte = normaliser_dates_du_document(brut)
        if perte:
            rapport["dates_perdues"] += 1

        # 2. Homogénéisation des champs, des licences et des mots-clés.
        document = homogeneiser_document(brut)

        if document["code_licence"] is None and document["licence_declaree"]:
            libelle = document["licence_declaree"]
            rapport["licences_sans_correspondance"][libelle] = (
                rapport["licences_sans_correspondance"].get(libelle, 0) + 1
            )

        documents.append(document)

    rapport["par_fichier"] = dict(compte_fichier)
    rapport["entrants"] = len(documents)

    # 3. Déduplication, en dernier, sur des documents déjà canoniques.
    documents, rapport_dedup = dedupliquer(documents)
    rapport["deduplication"] = rapport_dedup

    rapport["sortants"] = len(documents)
    rapport["par_type_source"] = dict(Counter(d["code_type_source"] for d in documents))
    rapport["par_licence"] = dict(Counter(d["code_licence"] or "SANS_CORRESPONDANCE"
                                          for d in documents))
    rapport["sans_date_creation"] = sum(1 for d in documents if not d["cree_le"])
    rapport["duree_secondes"] = round(
        (datetime.now(timezone.utc) - debut).total_seconds(), 2
    )

    chemin_corpus = _ecrire_corpus(documents, repertoire_sortie)
    rapport["corpus"] = str(chemin_corpus)
    _ecrire_rapport(rapport, repertoire_sortie)

    return rapport


# --- 3. Gestion des erreurs et exceptions ---
# Les lignes illisibles sont comptées et ignorées dans `lire_corpus_brut`, les
# dates non analysables dans `normalisation_dates`, les licences non reconnues
# dans `homogeneisation_formats`. Chacune est dénombrée dans le rapport plutôt
# que traitée en silence. Seule une erreur d'écriture interrompt le traitement :
# un corpus partiel serait pris pour complet par le chargeur.


# --- 4. Sauvegarde des résultats ---

def _ecrire_corpus(documents: list[dict[str, Any]], repertoire: Path) -> Path:
    """
    Écrit le corpus transformé en JSON Lines.

    Compétence visée : C3 (épreuve E1)

    Choix : écriture dans un fichier temporaire puis renommage atomique, comme
    le fait le socle d'extraction. Motivation : une transformation interrompue
    ne doit pas laisser un corpus partiel que le chargeur prendrait pour
    complet — il insérerait alors un jeu de données tronqué sans que rien ne le
    signale.
    """
    repertoire.mkdir(parents=True, exist_ok=True)
    chemin = repertoire / "corpus.jsonl"
    temporaire = chemin.with_suffix(".jsonl.tmp")

    with temporaire.open("w", encoding="utf-8") as flux:
        for document in documents:
            ligne = json.dumps(document, ensure_ascii=False)
            for separateur in SEPARATEURS_UNICODE:
                ligne = ligne.replace(
                    separateur, "\\u{:04x}".format(ord(separateur)),
                )
            flux.write(ligne + "\n")

    temporaire.replace(chemin)
    logger.info("Corpus transformé écrit : %d documents dans %s",
                len(documents), chemin)
    return chemin


def _ecrire_rapport(rapport: dict[str, Any], repertoire: Path) -> Path:
    """
    Écrit le rapport de qualité de la transformation.

    Compétence visée : C3 (épreuve E1)
    """
    chemin = repertoire / "rapport_transformation.json"
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Rapport de transformation écrit : %s", chemin)
    return chemin


# --- 5. Point de lancement ---

def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement de la transformation.

    Compétence visée : C3 (épreuve E1)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    analyseur = argparse.ArgumentParser(
        description="Transformation du corpus : dates, formats, doublons.",
    )
    analyseur.add_argument(
        "--brut", type=Path, default=REPERTOIRE_BRUT,
        help=f"Répertoire des sorties d'extraction (défaut : {REPERTOIRE_BRUT}).",
    )
    analyseur.add_argument(
        "--sortie", type=Path, default=REPERTOIRE_TRANSFORME,
        help=f"Répertoire du corpus transformé (défaut : {REPERTOIRE_TRANSFORME}).",
    )
    arguments = analyseur.parse_args(argv)

    if not arguments.brut.is_dir():
        logger.error(
            "Répertoire brut introuvable : %s. "
            "Lancer les extracteurs avant la transformation.", arguments.brut,
        )
        return 2

    try:
        rapport = transformer(arguments.brut, arguments.sortie)
    except Exception as exception:  # noqa: BLE001 — journalisé puis remonté
        logger.exception("Transformation interrompue : %s", exception)
        return 1

    dedup = rapport["deduplication"]
    logger.info(
        "Bilan — %d entrants, %d doublons retirés, %d sortants, %.2f s",
        rapport["entrants"],
        dedup["doublons_identifiant"] + dedup["doublons_contenu"],
        rapport["sortants"], rapport["duree_secondes"],
    )
    if rapport["licences_sans_correspondance"]:
        logger.warning(
            "Licences sans correspondance dans la nomenclature : %s. "
            "Le chargement devra trancher avant insertion.",
            rapport["licences_sans_correspondance"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
