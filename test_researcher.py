from apps.agents.agent_researcher import get_researcher_chain

if __name__ == "__main__":
    # Initialiser l'agent RAG
    chain = get_researcher_chain()

    # Envoyer une question
    question = "Comment fonctionnent les décorateurs Python ?"
    result = chain.invoke(question)

    # Afficher la réponse
    print("\n📚 Réponse générée :\n")
    print(result['result'])

    # Afficher les documents sources
    print("\n🔍 Sources utilisées :\n")
    for doc in result['source_documents']:
        print(f" - {doc.metadata['source']} (score possible)")
        print(f"   → extrait : {doc.page_content[:150]}...\n")
