# apps/agents/agent_researcher.py

import logging

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from apps.agents.tools.model_config import get_model_for
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function
from apps.agents.utils import load_prompt

logger = logging.getLogger(__name__)


def gabarit_de_reponse():
    """
    Rend le gabarit d'invite du chercheur, celui qui porte les consignes.

    Compétence visée : C10 (épreuve E3)

    Choix : un gabarit explicite, et non celui que LangChain pose par défaut.
    **Motivation constatée, et c'est le défaut le plus coûteux qu'ait eu le
    tuteur.** `RetrievalQA.from_chain_type` appelé sans `prompt` retombe sur le
    gabarit intégré de la bibliothèque :

        Use the following pieces of context to answer the question at the end.
        If you don't know the answer, just say that you don't know…

    Trois conséquences, toutes visibles à l'écran. Il est en anglais, donc rien
    n'impose le français. Il ne dit rien de la longueur, donc le modèle répond
    au format qu'il juge bon — un chapitre pour « une liste, c'est quoi ? ». Et
    il ordonne de s'appuyer sur le contexte trouvé, ce qui, quand la recherche
    a ramené des fragments à côté, produit une réponse qui ne parle pas de la
    question posée. Les consignes que les appelants ajoutaient à leur demande
    ne pouvaient pas corriger cela : elles arrivaient dans le champ `question`,
    sous un gabarit qui disait déjà autre chose.

    Choix : le gabarit est un fichier de `prompts/`, comme ceux du pédagogue et
    du coach. Motivation : les invites du projet se relisent au même endroit, et
    celle-ci est celle que le jury lira en premier s'il demande pourquoi Koda
    répond comme il répond.
    """
    return PromptTemplate(
        input_variables=["context", "question"],
        template=load_prompt("researcher_rag"),
    )


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
            return_source_documents=True,
            chain_type_kwargs={"prompt": gabarit_de_reponse()},
        )
    except Exception as e:
        logger.warning(
            "Chaine RAG du chercheur non construite (%s : %s), repli sans RAG.",
            type(e).__name__, e,
        )
        # Fallback without RAG
        llm = get_llm(model_name=model_name)
        from langchain.chains import LLMChain

        prompt = PromptTemplate(
            input_variables=["question"],
            template=load_prompt('researcher')
        )
        return LLMChain(llm=llm, prompt=prompt)
