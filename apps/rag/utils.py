import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = "apps/rag/chroma"

def load_embedding_function():
    return embedding_functions.OllamaEmbeddingFunction(
        model_name="mxbai-embed-large"
    )

def get_chroma_collection(embedding_fn):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name="eduai_knowledge_base",
        embedding_function=embedding_fn
    )
