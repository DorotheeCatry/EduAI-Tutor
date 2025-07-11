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
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        llm = get_llm(model_name=model_name)
    except Exception as e:
        print(f"Erreur lors de l'initialisation du pédagogue : {e}")
        # Fallback sans RAG
        llm = get_llm(model_name=model_name)
        retriever = None

    # Prompt de synthèse structuré et amélioré
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
Tu es un excellent formateur en programmation, spécialisé dans la création de cours pédagogiques clairs et structurés.

==== CONTEXTE DOCUMENTAIRE ====
{context}

==== MISSION ====
Crée un cours complet et pédagogique pour répondre à cette question : "{question}"

==== STRUCTURE OBLIGATOIRE ====
Ton cours DOIT suivre exactement cette structure avec les emojis et titres (utilise le format Markdown) :

## 📖 Introduction
[Présentation du concept en 2-3 phrases courtes et claires]

## 🔍 Explication Détaillée
[Théorie approfondie avec définitions et concepts clés]

## 💡 Exemples Pratiques
[Code concret avec commentaires explicatifs]
```python
# Exemple 1 : [Description]
[code]

# Exemple 2 : [Description] 
[code]
```

## 📝 Points Clés à Retenir
• Point important 1
• Point important 2  
• Point important 3
• Point important 4

## 🚀 Pour Aller Plus Loin
[Suggestions d'approfondissement et concepts connexes]

==== RÈGLES IMPORTANTES ====
- Réponds PRÉCISÉMENT à la question posée
- Utilise un langage simple et pédagogique
- Inclus TOUJOURS du code Python commenté
- Reste focalisé sur le sujet demandé
- Évite les digressions
- Utilise les informations du contexte si pertinentes
- Si le contexte ne correspond pas à la question, base-toi sur tes connaissances

==== EXEMPLE DE QUALITÉ ====
Si la question est "Explique la POO en Python", ne parle PAS de notebooks ou d'introduction générale, mais UNIQUEMENT de classes, objets, héritage, etc.
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
        # Fallback sans RAG avec prompt amélioré
        from langchain.chains import LLMChain
        simple_prompt = PromptTemplate(
            input_variables=["question"],
            template="""
Tu es un excellent formateur en programmation, spécialisé dans la création de cours pédagogiques clairs et structurés.

==== MISSION ====
Crée un cours complet et pédagogique pour répondre à cette question : "{question}"

==== STRUCTURE OBLIGATOIRE ====
Ton cours DOIT suivre exactement cette structure avec les emojis et titres (utilise le format Markdown) :

## 📖 Introduction
[Présentation du concept en 2-3 phrases courtes et claires]

## 🔍 Explication Détaillée
[Théorie approfondie avec définitions et concepts clés]

## 💡 Exemples Pratiques
[Code concret avec commentaires explicatifs]
```python
# Exemple 1 : [Description]
[code]

# Exemple 2 : [Description] 
[code]
```

## 📝 Points Clés à Retenir
• Point important 1
• Point important 2  
• Point important 3
• Point important 4

## 🚀 Pour Aller Plus Loin
[Suggestions d'approfondissement et concepts connexes]

==== RÈGLES IMPORTANTES ====
- Réponds PRÉCISÉMENT à la question posée
- Utilise un langage simple et pédagogique
- Inclus TOUJOURS du code Python commenté
- Reste focalisé sur le sujet demandé
- Évite les digressions

==== EXEMPLE DE QUALITÉ ====
Si la question est "Explique la POO en Python", ne parle PAS de notebooks ou d'introduction générale, mais UNIQUEMENT de classes, objets, héritage, encapsulation, polymorphisme avec des exemples de code.
"""
        )
        return LLMChain(llm=llm, prompt=simple_prompt)