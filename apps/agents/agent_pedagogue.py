# apps/agents/agent_pedagogue.py

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function

def get_pedagogue_chain(model_name="llama3-70b-8192"):
    """
    Agent Pédagogue : génère un mini-cours structuré à partir des documents retrouvés.
    """
    try:
        # Embeddings + vectorstore
        embedding_fn = load_embedding_function()
        vectorstore = Chroma(
            persist_directory="apps/rag/chroma",
            embedding_function=embedding_fn,
            collection_name="eduai_knowledge_base"
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        llm = get_llm(model_name=model_name)
    except Exception as e:
        print(f"Erreur lors de l'initialisation du pédagogue : {e}")
        # Fallback sans RAG
        llm = get_llm(model_name=model_name)
        retriever = None

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
- 📖 **Introduction** : Présentation du concept
- 🔍 **Explication détaillée** : Théorie et fonctionnement
- 💡 **Exemples pratiques** : Code et cas d'usage concrets
- 📝 **Points clés à retenir** : Résumé des éléments essentiels
- 🚀 **Pour aller plus loin** : Suggestions d'approfondissement

Utilise un ton pédagogique et structure bien ton contenu avec des sections claires.
"""
    )

    if retriever:
        return RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )
    else:
        # Fallback sans RAG
        from langchain.chains import LLMChain
        simple_prompt = PromptTemplate(
            input_variables=["question"],
            template="""
Tu es un excellent pédagogue en programmation. Génère un mini-cours structuré sur le sujet suivant :
{question}

Ta réponse doit inclure :
- 📖 **Introduction** : Présentation du concept
- 🔍 **Explication détaillée** : Théorie et fonctionnement  
- 💡 **Exemples pratiques** : Code et cas d'usage concrets
- 📝 **Points clés à retenir** : Résumé des éléments essentiels
- 🚀 **Pour aller plus loin** : Suggestions d'approfondissement

Utilise un ton pédagogique et structure bien ton contenu avec des sections claires.
"""
        )
        return LLMChain(llm=llm, prompt=simple_prompt)