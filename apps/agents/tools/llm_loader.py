# apps/agents/tools/llm_loader.py

import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_groq import ChatGroq


load_dotenv()

def get_llm(model_name=None):
    """
    Returns a LangChain compatible LLM.
    If model_name is None, takes DEFAULT_LLM_MODEL from environment.
    Priority: Groq, otherwise Ollama.
    """
    model_name = model_name or os.getenv("DEFAULT_LLM_MODEL", "mistral")
    groq_key = os.getenv("GROQ_API_KEY")

    if groq_key:
        print(f"🔗 Using Groq API ({model_name})")
        return ChatGroq(model_name=model_name, api_key=groq_key)
    else:
        print(f"💻 Using local Ollama ({model_name})")
        return ChatOllama(model=model_name)