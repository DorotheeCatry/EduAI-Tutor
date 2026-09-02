import os

from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
import chromadb
from chromadb.utils import embedding_functions



CHROMA_PATH = "apps/rag/chroma"

#: Adresse du serveur d'embarquement.
#
# Compétence visée : C13 (épreuve E3) — configuration par l'environnement
#
# Choix : lue dans l'environnement, avec la boucle locale par défaut.
# Motivation : l'adresse était figée à `localhost:11434` par la valeur par
# défaut de la bibliothèque. Sur le poste de développement, c'est exact. Hors
# de ce poste, il n'y a pas de serveur d'embarquement sur la boucle locale, et
# le RAG échouerait sans que rien dans le code ne laisse voir pourquoi —
# `apps/rag/indexation_corpus.py` lisait déjà cette variable, ce qui rendait la
# configuration vraie pour l'indexation et fausse pour la recherche.
URL_OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

#: Modèle d'embarquement.
#
# Choix : la valeur par défaut n'est pas libre. Le corpus a été indexé avec
# `mxbai-embed-large` ; interroger ces vecteurs avec un autre modèle ne produit
# pas de moins bons résultats, il en produit des dénués de sens — les deux
# espaces vectoriels n'ont aucun rapport. Changer ce modèle impose de
# réindexer l'intégralité du corpus.
MODELE_EMBARQUEMENT = os.environ.get("OLLAMA_EMBED_MODEL", "mxbai-embed-large")

#: Collection servant la recherche documentaire de l'API du service IA (C9).
#
# Compétence visée : C9 (épreuve E2), C10 (épreuve E3)
#
# Le corpus vectoriel porte deux collections, et elles n'ont pas le même objet :
#
#   - `eduai_knowledge_base` — 387 fragments issus des supports de formation.
#     C'est le contexte pédagogique des agents : ce que le Pédagogue doit avoir
#     sous les yeux pour composer un cours conforme au programme.
#   - `eduai_corpus_documentaire` — 21 189 fragments issus des cinq sources du
#     pipeline (C1 à C4). C'est de la documentation technique publique, filtrée
#     par licence.
#
# Choix : la recherche documentaire du service IA interroge la seconde, les
# agents Django restent sur la première. Motivation : ce sont deux questions
# différentes. « Que dit la documentation sur les listes ? » appelle le corpus
# collecté ; « quel contexte donner au Pédagogue ? » appelle les supports de
# formation. Jusqu'au 29/08/2026, les deux interrogeaient la première, et les
# 21 189 fragments produits par le pipeline n'étaient lus par personne.
#
# Les deux collections sont indexées avec le même modèle d'embarquement, ce qui
# est la condition pour que les vecteurs soient comparables.
COLLECTION_DOCUMENTAIRE = "eduai_corpus_documentaire"

#: Collection de contexte pédagogique des agents.
COLLECTION_PEDAGOGIQUE = "eduai_knowledge_base"

# === For LangChain (used in agent_researcher.py) ===
def load_embedding_function():
    return OllamaEmbeddings(model=MODELE_EMBARQUEMENT, base_url=URL_OLLAMA)



# === For native Chroma (used in prepare_chroma.py) ===
def get_chroma_collection_native():
    embedding_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name=MODELE_EMBARQUEMENT,
        url=URL_OLLAMA,
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name="eduai_knowledge_base",
        embedding_function=embedding_fn
    )
