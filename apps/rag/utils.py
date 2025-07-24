from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
import chromadb
from chromadb.utils import embedding_functions



CHROMA_PATH = "apps/rag/chroma"

# === For LangChain (used in agent_researcher.py) ===
def load_embedding_function():
    return OllamaEmbeddings(model="mxbai-embed-large")

def get_chroma_collection_langchain():
    return Chroma(
        persist_directory=CHROMA_PATH,
        collection_name="eduai_knowledge_base"
    )


# === For native Chroma (used in prepare_chroma.py) ===
def get_chroma_collection_native():
    embedding_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name="mxbai-embed-large"
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name="eduai_knowledge_base",
        embedding_function=embedding_fn
    )