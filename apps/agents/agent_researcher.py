from langchain.chains import RetrievalQA
from apps.agents.tools.llm_loader import get_llm
from langchain.vectorstores import Chroma
from apps.rag.utils import load_embedding_function

def get_researcher_chain():
    embedding_fn = load_embedding_function()
    vectorstore = Chroma(
        persist_directory="apps/rag/chroma",
        embedding_function=embedding_fn
    )

    retriever = vectorstore.as_retriever()
    llm = get_llm(model_name="mistral-7b")  # ou "mixtral-8x7b-32768" pour test Groq

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )
