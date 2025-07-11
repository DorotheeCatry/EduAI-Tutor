# apps/agents/agent_pedagogue.py

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function, get_chroma_collection_langchain

def get_pedagogue_chain(model_name="llama3-70b-8192"):
    """
    Agent Pédagogue : génère un mini-cours structuré à partir des documents retrouvés.
    """
    # Embeddings + vectorstore
    embedding_fn = load_embedding_function()
    vectorstore = Chroma(
        persist_directory="apps/rag/chroma",
        embedding_function=embedding_fn,
        collection_name="eduai_knowledge_base"
    )

    retriever = vectorstore.as_retriever()
    llm = get_llm(model_name=model_name)

    # Prompt de synthèse structuré
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
Tu es un excellent pédagogue. À partir du contenu suivant, génère un mini-cours structuré.

==== CONTEXTE ====
{context}

==== INSTRUCTION ====
Écris une leçon pédagogique claire et concise pour répondre à la question suivante :
{question}

Ta réponse doit inclure :
- Une introduction
- Une explication progressive
- Des exemples si pertinent
- Un résumé ou points clés à retenir
"""
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )
