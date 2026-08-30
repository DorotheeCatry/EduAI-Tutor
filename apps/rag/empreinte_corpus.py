"""
Empreinte du corpus vectoriel — ce qui permet de constater qu'il est le bon.

Compétence visée : C13 (épreuve E3) — livraison et déploiement
Compétences concernées : C10 (E3), C20 (E5)

Depuis la décision 023, le corpus ne voyage plus dans l'image de conteneur
mais sur un volume persistant chez l'hébergeur. Le couple corpus/code n'est
donc plus atomique : un corpus réindexé sur le poste et non téléversé laisse
tourner l'application sur l'ancien, sans qu'aucune erreur ne se produise.

Ce module produit l'empreinte qui rend cette divergence constatable. Il ne
l'empêche pas — un dispositif découplé ne le peut pas — il fait qu'on puisse
la voir en une requête, plutôt que de la découvrir par une réponse du RAG qui
ne cite pas le document attendu.

Choix : un fichier posé DANS le corpus, et non une valeur en base ou une
variable d'environnement. Motivation : l'empreinte doit voyager avec ce
qu'elle décrit. Téléversée séparément, elle pourrait elle-même diverger, et
l'on aurait déplacé le problème d'un cran.

Choix : la somme SHA-256 porte sur `chroma.sqlite3` seul, et non sur
l'arborescence entière. Motivation : les répertoires d'index binaires
accompagnant les collections sont réécrits par ChromaDB à des moments qui ne
correspondent pas à un changement de contenu ; les inclure produirait une
empreinte qui change sans que le corpus change, donc une alerte à laquelle
plus personne ne prêterait attention.

Sortie : apps/rag/chroma/EMPREINTE.json

Usage :
    uv run python -m apps.rag.empreinte_corpus
"""

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- 1. Initialisation des dépendances et connexions externes ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CHEMIN_CORPUS = Path("apps/rag/chroma")
FICHIER_EMPREINTE = CHEMIN_CORPUS / "EMPREINTE.json"
BASE_CHROMA = CHEMIN_CORPUS / "chroma.sqlite3"

# Les deux collections du projet, nommées ici plutôt qu'énumérées depuis le
# client : une collection attendue mais absente doit apparaître dans
# l'empreinte comme absente, pas disparaître du relevé.
COLLECTIONS_ATTENDUES = ("eduai_corpus_documentaire", "eduai_knowledge_base")


def somme_de_controle(chemin: Path) -> str:
    """
    Calcule la somme SHA-256 d'un fichier, par blocs.

    Compétence visée : C13 (épreuve E3)

    Choix : lecture par blocs de 1 Mio plutôt qu'en une fois. Motivation : le
    fichier pèse plusieurs centaines de mégaoctets, et le charger entièrement
    en mémoire pour le hacher n'apporte rien.
    """
    empreinte = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


# --- 2. Règles logiques de traitement ---


def relever_collections() -> dict[str, int | None]:
    """
    Relève le nombre de fragments de chaque collection attendue.

    Compétence visée : C13 (épreuve E3)

    Choix : `count()` et non une lecture des documents. Motivation : le
    décompte est la seule grandeur dont la comparaison poste/serveur soit
    immédiate, et il n'exige ni modèle d'embarquement ni chargement du
    contenu — donc aucun appel à Ollama.

    Une collection absente vaut `None` et non zéro : « je n'ai pas trouvé la
    collection » et « la collection est vide » sont deux états différents, et
    les confondre est exactement ce que ce projet a déjà payé (incident 001).
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(CHEMIN_CORPUS))
    releve: dict[str, int | None] = {}

    for nom in COLLECTIONS_ATTENDUES:
        try:
            releve[nom] = client.get_collection(nom).count()
        except Exception as erreur:
            # Volontairement large : le client lève des exceptions de types
            # différents selon les versions pour un même cas — collection
            # inexistante. Le motif est journalisé, l'empreinte reste
            # produite : une collection manquante est une information, pas un
            # échec du relevé.
            logger.warning("collection %s illisible : %s", nom, erreur)
            releve[nom] = None

    return releve


def construire_empreinte() -> dict:
    """
    Construit le relevé complet du corpus présent sur le disque.

    Compétence visée : C13 (épreuve E3)
    """
    from apps.rag.utils import MODELE_EMBARQUEMENT

    logger.info("lecture du corpus dans %s", CHEMIN_CORPUS)
    collections = relever_collections()
    for nom, nombre in collections.items():
        logger.info("  %s : %s fragments", nom, "absente" if nombre is None else nombre)

    logger.info("calcul de la somme de contrôle de %s", BASE_CHROMA.name)
    return {
        "date_releve": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "empreinte_sha256": somme_de_controle(BASE_CHROMA),
        "octets_base": BASE_CHROMA.stat().st_size,
        "modele_embarquement": MODELE_EMBARQUEMENT,
        "collections": collections,
    }


# --- 3. Gestion des erreurs et exceptions ---


def verifier_le_corpus() -> None:
    """
    Interrompt le traitement si le corpus n'est pas là où il est attendu.

    Compétence visée : C13 (épreuve E3)

    Choix : arrêt explicite plutôt qu'empreinte vide. Motivation : une
    empreinte produite sur un corpus absent décrirait le vide, et serait
    téléversée comme si elle décrivait quelque chose.
    """
    if not CHEMIN_CORPUS.is_dir():
        raise FileNotFoundError(
            f"{CHEMIN_CORPUS} est absent. Le corpus se produit par "
            f"apps/rag/indexation_corpus.py, hors ligne."
        )
    if not BASE_CHROMA.is_file():
        raise FileNotFoundError(
            f"{BASE_CHROMA} est absent : le répertoire existe mais ne contient "
            f"aucun corpus ChromaDB."
        )


# --- 4. Sauvegarde des résultats ---


def ecrire(empreinte: dict) -> None:
    """
    Écrit l'empreinte dans le corpus lui-même.

    Compétence visée : C13 (épreuve E3)
    """
    FICHIER_EMPREINTE.write_text(
        json.dumps(empreinte, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("empreinte écrite : %s", FICHIER_EMPREINTE)


def lire() -> dict | None:
    """
    Relit l'empreinte du corpus présent, ou `None` s'il n'en porte pas.

    Compétence visée : C13 (épreuve E3)
    Compétence visée : C20 (épreuve E5) — lue par la sonde de santé

    Choix : cette fonction ne lève jamais. Motivation : elle est appelée par
    `/ai/sante`, dont la raison d'être est de répondre quand quelque chose ne
    va pas. Une sonde qui échoue parce que l'objet observé est en défaut
    n'observe rien.
    """
    try:
        return json.loads(FICHIER_EMPREINTE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --- 5. Point de lancement ---


def main() -> int:
    """
    Produit l'empreinte du corpus local.

    Compétence visée : C13 (épreuve E3)

    À exécuter après chaque réindexation, AVANT le téléversement du corpus sur
    le volume de l'hébergeur — voir docs/chaine_livraison.md.
    """
    try:
        verifier_le_corpus()
    except FileNotFoundError as erreur:
        logger.error("%s", erreur)
        return 2

    empreinte = construire_empreinte()
    ecrire(empreinte)

    logger.info("relevé du %s", empreinte["date_releve"])
    logger.info("empreinte %s", empreinte["empreinte_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
