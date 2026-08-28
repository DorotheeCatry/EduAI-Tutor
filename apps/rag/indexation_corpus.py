"""
Indexation du corpus documentaire de `eduai_data` dans ChromaDB.

Compétence visée : C10 (épreuve E3) — intégration du modèle dans l'application
Compétence visée : C4 (épreuve E1) — respect des règles de diffusion du corpus
Compétence visée : C20 (épreuve E5) — le traitement rend compte de son effet

Le pipeline charge 6 836 documents dans PostgreSQL, mais rien ne les portait
jusqu'au vector store : ChromaDB ne contenait que les 387 fragments du corpus
de cours. Les deux moitiés du système ne se parlaient pas. Ce module est le
chaînon manquant.

--- Les trois règles qui gouvernent ce module ---

**1. Le filtre de diffusion n'est pas réécrit, il est réutilisé.**

`Document.objects` EST le gestionnaire d'exposition : il n'expose que les
documents dont la licence autorise la redistribution et qui n'ont pas été
marqués `retire_le`. Ce module ne reformule pas cette condition, il appelle ce
gestionnaire. Motivation : une seconde formulation de la même règle finirait par
diverger de la première, et c'est le vector store — interrogé par les agents,
donc lu par les apprenants — qui deviendrait la porte de sortie que l'API ferme.
Un document non redistribuable ne doit pas être diffusable par un autre chemin.

**2. Le retrait doit être un effacement, pas un filtrage.**

Un document marqué `retire_le` après avoir été indexé reste dans Chroma tant
qu'on ne l'en retire pas. Filtrer à la lecture ne suffirait pas : le fragment
resterait sur le disque et remonterait dès qu'un appelant oublierait le filtre.
Ce module compare donc l'ensemble indexé à l'ensemble exposable et **supprime**
les fragments devenus non diffusables.

**3. Le corpus documentaire ne se mélange pas au corpus de cours.**

Deux collections distinctes. Motivation : les 387 fragments de
`eduai_knowledge_base` proviennent des supports de formation, sans contrainte de
licence externe ni de retrait. Les documents de `eduai_data` viennent de sources
tierces, sous licences hétérogènes, et peuvent disparaître de leur source. Les
verser dans la même collection ferait dépendre le corpus de cours d'un
réindexage du corpus documentaire — et une purge de l'un emporterait l'autre.

Sortie : collection `eduai_corpus_documentaire` dans apps/rag/chroma

--- Point de lancement ---
    uv run python -m apps.rag.indexation_corpus [--limite N] [--purger] [--a-blanc]
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances et connexions externes -------------

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import django
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eduai_project.settings")
django.setup()

import chromadb  # noqa: E402
from chromadb.utils import embedding_functions  # noqa: E402

from apps.api_data.models import Document  # noqa: E402
from apps.rag.splitter import get_splitter  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("indexation_corpus")

#: Emplacement du magasin vectoriel, aligné sur celui du corpus de cours.
CHEMIN_CHROMA = Path("apps/rag/chroma")

#: Collection dédiée au corpus documentaire, distincte de `eduai_knowledge_base`.
COLLECTION = "eduai_corpus_documentaire"

#: Modèle d'embarquement, identique à celui du corpus de cours.
#:
#: Choix : réutiliser `mxbai-embed-large` plutôt qu'un modèle plus récent.
#: Motivation : les 387 fragments existants sont en 1024 dimensions. En changer
#: imposerait de tout réindexer, ce qui n'est ni au programme ni justifié par un
#: besoin mesuré. Le vérifier est le rôle de `verifier_dimension`.
MODELE_EMBARQUEMENT = "mxbai-embed-large"
DIMENSION_ATTENDUE = 1024

#: Taille de lot pour l'écriture dans Chroma.
#:
#: Choix : des lots plutôt qu'un versement unique. Motivation : plusieurs
#: dizaines de milliers de fragments embarqués en une transaction tiendraient
#: tout en mémoire et perdraient tout sur une interruption. Les lots rendent le
#: traitement reprenable.
TAILLE_LOT = 64


def construire_collection(client):
    """
    Ouvre ou crée la collection du corpus documentaire.

    Compétence visée : C10 (épreuve E3)
    """
    fonction_embarquement = embedding_functions.OllamaEmbeddingFunction(
        model_name=MODELE_EMBARQUEMENT,
        url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434") + "/api/embeddings",
    )
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=fonction_embarquement,
        metadata={"corpus": "eduai_data", "modele": MODELE_EMBARQUEMENT},
    )


# --- 2. Règles logiques de traitement -------------------------------------

def identifiant_fragment(id_document: int, rang: int) -> str:
    """
    Compose l'identifiant stable d'un fragment.

    Compétence visée : C10 (épreuve E3)

    Choix : un identifiant déterministe, dérivé de la clé primaire du document
    et du rang du fragment, plutôt qu'un UUID. Motivation : c'est ce qui rend le
    traitement idempotent. Relancer l'indexation réécrit les mêmes
    identifiants au lieu d'empiler des doublons — la même exigence que celle
    posée aux extracteurs du pipeline.
    """
    return f"doc-{id_document}-{rang:04d}"


def fragmenter(document, decoupeur) -> list[tuple[str, str, dict]]:
    """
    Découpe un document en fragments et leur attache leurs métadonnées.

    Compétence visée : C10 (épreuve E3)
    Compétence visée : C4 (épreuve E1) — l'attribution voyage avec le fragment

    Choix : le code de licence et l'obligation d'attribution sont portés par
    CHAQUE fragment, pas seulement par le document. Motivation : c'est le
    fragment qui remonte dans une réponse d'agent. Si l'obligation d'attribution
    restait au niveau du document, l'agent citerait un extrait de contenu
    sous CC-BY-SA sans pouvoir savoir qu'il doit en nommer l'auteur.
    """
    morceaux = decoupeur.split_text(document.contenu or "")
    fragments = []
    for rang, morceau in enumerate(morceaux):
        if not morceau.strip():
            continue
        fragments.append((
            identifiant_fragment(document.id_document, rang),
            morceau,
            {
                "id_document": document.id_document,
                "titre": document.titre or "",
                "url_source": document.url_source or "",
                "langue": document.langue or "",
                "code_type_source": document.code_type_source or "",
                "code_licence": document.licence_id or "",
                "attribution_requise": bool(document.attribution_requise),
                "rang_fragment": rang,
            },
        ))
    return fragments


def fragments_indexes(collection) -> set[str]:
    """
    Relit les identifiants déjà présents dans la collection.

    Compétence visée : C20 (épreuve E5)

    Choix : relire le magasin plutôt que tenir un compteur. Motivation : la
    règle du projet depuis l'incident de chargement — un traitement constate son
    effet sur le support, il ne rapporte pas son intention.
    """
    connus: set[str] = set()
    decalage = 0
    while True:
        lot = collection.get(limit=1000, offset=decalage, include=[])
        identifiants = lot.get("ids") or []
        if not identifiants:
            break
        connus.update(identifiants)
        decalage += len(identifiants)
    return connus


def retirer_les_non_diffusables(collection, connus: set[str],
                                attendus: set[str], a_blanc: bool) -> int:
    """
    Supprime de Chroma les fragments qui ne sont plus diffusables.

    Compétence visée : C4 (épreuve E1) — le retrait est un effacement

    C'est la règle 2 de l'en-tête. Un document dont la licence a changé, ou qui
    a disparu de sa source et porte `retire_le`, sort du gestionnaire
    d'exposition — mais son fragment reste sur le disque tant qu'on ne l'efface
    pas. Filtrer à la lecture laisserait une porte ouverte.
    """
    a_retirer = sorted(connus - attendus)
    if not a_retirer:
        logger.info("aucun fragment à retirer : l'index correspond au corpus diffusable")
        return 0

    logger.warning("%d fragment(s) indexés ne sont plus diffusables — retrait",
                   len(a_retirer))
    if a_blanc:
        logger.warning("exécution à blanc : aucun retrait effectué")
        return 0

    for depart in range(0, len(a_retirer), 500):
        collection.delete(ids=a_retirer[depart:depart + 500])
    return len(a_retirer)


def verifier_dimension(collection) -> int | None:
    """
    Constate la dimension réellement stockée, plutôt que de la supposer.

    Compétence visée : C20 (épreuve E5)

    Une collection alimentée par deux modèles d'embarquement différents rend des
    voisins insensés sans jamais lever d'erreur. Le contrôle est bon marché et
    la panne qu'il évite est silencieuse.
    """
    echantillon = collection.get(limit=1, include=["embeddings"])
    vecteurs = echantillon.get("embeddings")
    if vecteurs is None or len(vecteurs) == 0:
        return None
    dimension = len(vecteurs[0])
    if dimension != DIMENSION_ATTENDUE:
        logger.error(
            "dimension %d au lieu de %d attendues : la collection mélange deux "
            "modèles d'embarquement, les recherches seront incohérentes",
            dimension, DIMENSION_ATTENDUE,
        )
    return dimension


def main() -> int:
    """
    Point de lancement de l'indexation.

    Compétence visée : C10 (épreuve E3)
    """
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--limite", type=int, default=None,
                           help="plafond de documents traités, pour les essais")
    analyseur.add_argument("--purger", action="store_true",
                           help="vide la collection avant d'indexer")
    analyseur.add_argument("--a-blanc", action="store_true",
                           help="ne rien écrire ; annoncer ce qui serait fait")
    options = analyseur.parse_args()

    debut = time.perf_counter()
    client = chromadb.PersistentClient(path=str(CHEMIN_CHROMA))

    if options.purger and not options.a_blanc:
        try:
            client.delete_collection(COLLECTION)
            logger.warning("collection %s supprimée avant réindexation", COLLECTION)
        except Exception:  # noqa: BLE001 — absente : rien à purger
            logger.info("collection %s absente, rien à purger", COLLECTION)

    collection = construire_collection(client)
    decoupeur = get_splitter()

    # `Document.objects` EST le gestionnaire d'exposition : la condition de
    # diffusion est appliquée ici sans être réécrite. Voir la règle 1.
    requete = Document.objects.select_related("licence").order_by("id_document")
    total_diffusables = requete.count()
    if options.limite:
        requete = requete[:options.limite]

    # Aucun compte « total en base » n'est affiché : le modèle ne fournit
    # délibérément aucun gestionnaire non filtré (voir apps/api_data/models.py),
    # afin qu'aucun appelant ne puisse contourner la règle de diffusion par
    # inadvertance. Ce module ne fait pas exception à cette règle pour se
    # donner un chiffre de plus.
    logger.info("corpus diffusable à indexer : %d documents", total_diffusables)

    connus = fragments_indexes(collection)
    logger.info("fragments déjà indexés : %d", len(connus))

    attendus: set[str] = set()
    lot_ids: list[str] = []
    lot_textes: list[str] = []
    lot_metadonnees: list[dict] = []
    ecrits = 0
    documents_vus = 0
    echecs = 0

    def verser() -> int:
        """Écrit un lot et rend le nombre de fragments versés."""
        nonlocal lot_ids, lot_textes, lot_metadonnees
        if not lot_ids:
            return 0
        nombre = len(lot_ids)
        if not options.a_blanc:
            collection.upsert(ids=lot_ids, documents=lot_textes,
                              metadatas=lot_metadonnees)
        lot_ids, lot_textes, lot_metadonnees = [], [], []
        return nombre

    for document in requete.iterator(chunk_size=200):
        documents_vus += 1
        try:
            fragments = fragmenter(document, decoupeur)
        # --- 3. Gestion des erreurs et exceptions -------------------------
        except Exception as exception:  # noqa: BLE001
            # Un document au contenu illisible ne doit pas arrêter les 6 800
            # autres. Il est compté, et le compte figure au bilan.
            echecs += 1
            logger.error("document %s : découpage impossible — %s",
                         document.id_document, exception)
            continue

        for identifiant, texte, metadonnees in fragments:
            attendus.add(identifiant)
            lot_ids.append(identifiant)
            lot_textes.append(texte)
            lot_metadonnees.append(metadonnees)

            if len(lot_ids) >= TAILLE_LOT:
                try:
                    ecrits += verser()
                except Exception as exception:  # noqa: BLE001
                    # Le service d'embarquement peut tomber en cours de route :
                    # c'est arrivé toute la semaine. On perd le lot, jamais la
                    # campagne, et le compte d'échecs le dit.
                    echecs += len(lot_ids)
                    lot_ids, lot_textes, lot_metadonnees = [], [], []
                    logger.error("lot perdu — %s : %s",
                                 type(exception).__name__, str(exception)[:200])

        if documents_vus % 250 == 0:
            logger.info("  %d documents parcourus, %d fragments versés",
                        documents_vus, ecrits)

    try:
        ecrits += verser()
    except Exception as exception:  # noqa: BLE001
        echecs += len(lot_ids)
        logger.error("dernier lot perdu — %s", exception)

    # --- 4. Sauvegarde des résultats et bilan -----------------------------

    # Le retrait ne s'applique qu'à un parcours COMPLET : sur un parcours
    # tronqué par --limite, les fragments non revus ne sont pas « non
    # diffusables », ils sont simplement hors du sous-ensemble examiné. Les
    # supprimer viderait l'index à chaque essai.
    retires = 0
    if options.limite:
        logger.warning("--limite actif : aucun retrait, le parcours est partiel")
    else:
        retires = retirer_les_non_diffusables(collection, connus, attendus,
                                              options.a_blanc)

    dimension = verifier_dimension(collection)
    presents = collection.count()
    duree = time.perf_counter() - debut

    logger.info("─── bilan ───")
    logger.info("documents diffusables parcourus : %d", documents_vus)
    logger.info("fragments attendus              : %d", len(attendus))
    logger.info("fragments versés                : %d", ecrits)
    logger.info("fragments retirés               : %d", retires)
    logger.info("échecs                          : %d", echecs)
    logger.info("fragments dans la collection    : %d", presents)
    logger.info("dimension constatée             : %s", dimension)
    logger.info("durée                           : %.1f s", duree)

    if options.a_blanc:
        logger.warning("exécution à blanc : rien n'a été écrit")
        return 0

    # Le contrôle final confronte l'effet au but. Sans lui, ce module
    # rapporterait un succès sans savoir ce qu'il a produit — le motif que ce
    # projet documente depuis huit incidents.
    if not options.limite and presents != len(attendus):
        logger.error(
            "la collection contient %d fragments pour %d attendus : "
            "l'indexation n'est PAS conforme au corpus diffusable",
            presents, len(attendus),
        )
        return 1

    return 0 if echecs == 0 else 2


# --- 5. Point de lancement ------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
