# agents/tools/agent_researcher.py

from langchain.chains import RetrievalQA
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function

def get_researcher_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    Initialise le Chercheur RAG, compatible Groq (ou Ollama fallback).
    """
    try:
        embedding_fn = load_embedding_function()
        vectorstore = Chroma(
            persist_directory="apps/rag/chroma",
            embedding_function=embedding_fn,
            collection_name="eduai_knowledge_base"
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        llm = get_llm(model_name=model_name)
        
        return RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=True
        )
    except Exception as e:
        print(f"Erreur lors de l'initialisation du chercheur : {e}")
        # Fallback sans RAG
        llm = get_llm(model_name=model_name)
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        prompt = PromptTemplate(
            input_variables=["question"],
            template="""
Tu es un expert en programmation. Réponds de manière détaillée et pédagogique à la question suivante :
{question}

Fournis une réponse complète avec des explications claires et des exemples si pertinent.
"""
        )
        return LLMChain(llm=llm, prompt=prompt)
