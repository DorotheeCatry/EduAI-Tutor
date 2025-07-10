# agents/tools/agent_researcher.py

from langchain.chains import RetrievalQA
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function

def get_researcher_chain(model_name="meta-llama/llama-guard-4-12b"):
    """
    Initialise le Chercheur RAG, compatible Groq (ou Ollama fallback).
    """
    embedding_fn = load_embedding_function()
    vectorstore = Chroma(
        persist_directory="apps/rag/chroma",
        embedding_function=embedding_fn
    )

    retriever = vectorstore.as_retriever()
    llm = get_llm(model_name=model_name)

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )
