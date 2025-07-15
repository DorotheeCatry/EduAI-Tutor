# apps/agents/agent_pedagogue.py

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from apps.agents.utils import load_prompt
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function


def get_pedagogue_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    Agent Pédagogue : génère un cours structuré au format JSON plat.
    """
    # Initialisation du LLM et du vectorstore
    embedding_fn = load_embedding_function()
    vectorstore = Chroma(
        persist_directory="apps/rag/chroma",
        embedding_function=embedding_fn,
        collection_name="eduai_knowledge_base"
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    llm = get_llm(model_name=model_name)

    # Prompt structuré pour un JSON plat
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=load_prompt("pedagogue")
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )


def test_pedagogue_output():
    """Fonction de test pour vérifier la sortie du pédagogue"""
    chain = get_pedagogue_chain()
    result = chain.invoke({"question": "les fonctions python"})
    print("🔍 Test output:", result)
    return result
