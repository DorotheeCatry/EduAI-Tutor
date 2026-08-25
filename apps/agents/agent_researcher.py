# apps/agents/agent_researcher.py

from langchain.chains import RetrievalQA
from apps.agents.tools.llm_loader import get_llm
from apps.agents.tools.model_config import get_model_for
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function
from apps.agents.utils import load_prompt

def get_researcher_chain(model_name=None):
    """
    Initialize RAG Researcher, compatible with Groq (or Ollama fallback).

    Compétence visée : C10 (épreuve E3)
    Choix : le modèle n'est plus codé en dur mais résolu par get_model_for.
    L'argument model_name reste accepté pour permettre une surcharge ponctuelle
    (démonstration, comparaison de modèles pour C7).
    """
    if model_name is None:
        model_name = get_model_for("researcher")

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
        print(f"Error initializing researcher: {e}")
        # Fallback without RAG
        llm = get_llm(model_name=model_name)
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        prompt = PromptTemplate(
            input_variables=["question"],
            template=load_prompt('researcher')
        )
        return LLMChain(llm=llm, prompt=prompt)
