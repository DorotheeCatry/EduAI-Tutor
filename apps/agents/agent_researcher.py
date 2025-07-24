# apps/agents/agent_researcher.py

from langchain.chains import RetrievalQA
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function
from apps.agents.utils import load_prompt

def get_researcher_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    Initialize RAG Researcher, compatible with Groq (or Ollama fallback).
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
