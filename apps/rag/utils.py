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

# === For LangChain (used in agent_researcher.py) ===
def load_embedding_function():
    return OllamaEmbeddings(model=MODELE_EMBARQUEMENT, base_url=URL_OLLAMA)

def get_chroma_collection_langchain():
    return Chroma(
        persist_directory=CHROMA_PATH,
        collection_name="eduai_knowledge_base"
    )


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
