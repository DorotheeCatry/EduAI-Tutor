import os
from langchain.chat_models import ChatOllama
from langchain.chat_models import ChatGroq

def get_llm(model_name="mistral"):
    """
    Retourne un LLM LangChain compatible, prioritairement via Groq (cloud), sinon Ollama (local).
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    
    if groq_key:
        print("🔗 Using Groq API")
        return ChatGroq(model_name=model_name, api_key=groq_key)
    else:
        print("💻 Using local Ollama")
        return ChatOllama(model=model_name)
