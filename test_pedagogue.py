# test_pedagogue.py

from apps.agents.agent_pedagogue import get_pedagogue_chain

if __name__ == "__main__":
    chain = get_pedagogue_chain()
    question = "Explique le fonctionnement des décorateurs en Python"
    result = chain.invoke({"query": question})

    print("\n📘 Mini-cours généré :\n")
    print(result['result'])

    print("\n🔍 Sources utilisées :\n")
    for doc in result['source_documents']:
        print(f" - {doc.metadata['source']} → {doc.page_content[:150]}...\n")
