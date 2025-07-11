# apps/agents/agent_pedagogue.py

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function

def get_pedagogue_chain(model_name="llama3-70b-8192"):
    """
    Agent Pédagogue : génère un cours structuré et visuellement attrayant.
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

    # Prompt optimisé pour un cours structuré et beau
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
Tu es un expert formateur en programmation qui crée des cours exceptionnels, clairs et visuellement attrayants.

==== CONTEXTE DOCUMENTAIRE ====
{context}

==== MISSION ====
Crée un cours complet et professionnel sur : "{question}"

==== STRUCTURE OBLIGATOIRE ====
Utilise EXACTEMENT cette structure avec le format JSON suivant :

{{
  "title": "Titre du cours (ex: Les Fonctions en Python)",
  "sections": [
    {{
      "type": "introduction",
      "title": "📖 Introduction",
      "content": "Présentation claire du concept en 2-3 phrases. Explique pourquoi c'est important et ce qu'on va apprendre."
    }},
    {{
      "type": "explanation", 
      "title": "🔍 Concepts Fondamentaux",
      "content": "Explication détaillée avec définitions claires. Utilise **gras** pour les mots-clés importants comme **def**, **return**, **arguments**, etc."
    }},
    {{
      "type": "syntax",
      "title": "⚙️ Syntaxe et Structure", 
      "content": "Syntaxe de base avec explications :\n\n```python\n# Syntaxe générale\ndef nom_fonction(parametre1, parametre2):\n    \"\"\"Documentation de la fonction\"\"\"\n    # Corps de la fonction\n    return resultat\n```\n\nExplique chaque partie de la syntaxe."
    }},
    {{
      "type": "examples",
      "title": "💡 Exemples Pratiques",
      "content": "Minimum 3 exemples progressifs avec du code Python commenté :\n\n**Exemple 1 : Fonction simple**\n```python\ndef saluer(nom):\n    \"\"\"Fonction qui salue une personne\"\"\"\n    return f\"Bonjour {{nom}} !\"\n\n# Utilisation\nresultat = saluer(\"Alice\")\nprint(resultat)  # Affiche: Bonjour Alice !\n```\n\n**Exemple 2 : Fonction avec plusieurs paramètres**\n[Code avec commentaires détaillés]\n\n**Exemple 3 : Fonction avancée**\n[Code plus complexe avec explications]"
    }},
    {{
      "type": "key_points",
      "title": "📝 Points Clés à Retenir", 
      "content": "• **Point important 1** : Explication courte\n• **Point important 2** : Explication courte\n• **Point important 3** : Explication courte\n• **Point important 4** : Explication courte\n• **Point important 5** : Explication courte"
    }},
    {{
      "type": "advanced",
      "title": "🚀 Pour Aller Plus Loin",
      "content": "Concepts avancés et suggestions d'approfondissement avec exemples de code si pertinent."
    }}
  ]
}}

==== RÈGLES CRITIQUES ====
1. **RÉPONDS PRÉCISÉMENT** à la question posée, pas à autre chose
2. **UTILISE LE FORMAT JSON** exact ci-dessus
3. **INCLUS DU CODE PYTHON** dans chaque section d'exemples
4. **UTILISE LE GRAS** pour les mots-clés importants (**def**, **return**, etc.)
5. **COMMENTE TON CODE** de manière pédagogique
6. **RESTE FOCALISÉ** sur le sujet demandé
7. **UTILISE LES INFORMATIONS** du contexte si pertinentes

==== EXEMPLE DE QUALITÉ ====
Si la question est "les boucles for", ne parle PAS de fonctions ou d'introduction générale, mais UNIQUEMENT de boucles for avec syntaxe, exemples, range(), enumerate(), etc.

IMPORTANT: Réponds UNIQUEMENT avec le JSON, rien d'autre.
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
Tu es un expert formateur en programmation qui crée des cours exceptionnels, clairs et visuellement attrayants.

==== MISSION ====
Crée un cours complet et professionnel sur : "{question}"

==== STRUCTURE OBLIGATOIRE ====
Utilise EXACTEMENT cette structure avec le format JSON suivant :

{{
  "title": "Titre du cours (ex: Les Fonctions en Python)",
  "sections": [
    {{
      "type": "introduction",
      "title": "📖 Introduction",
      "content": "Présentation claire du concept en 2-3 phrases. Explique pourquoi c'est important et ce qu'on va apprendre."
    }},
    {{
      "type": "explanation", 
      "title": "🔍 Concepts Fondamentaux",
      "content": "Explication détaillée avec définitions claires. Utilise **gras** pour les mots-clés importants comme **def**, **return**, **arguments**, etc."
    }},
    {{
      "type": "syntax",
      "title": "⚙️ Syntaxe et Structure", 
      "content": "Syntaxe de base avec explications :\n\n```python\n# Syntaxe générale\ndef nom_fonction(parametre1, parametre2):\n    \"\"\"Documentation de la fonction\"\"\"\n    # Corps de la fonction\n    return resultat\n```\n\nExplique chaque partie de la syntaxe."
    }},
    {{
      "type": "examples",
      "title": "💡 Exemples Pratiques",
      "content": "Minimum 3 exemples progressifs avec du code Python commenté :\n\n**Exemple 1 : Fonction simple**\n```python\ndef saluer(nom):\n    \"\"\"Fonction qui salue une personne\"\"\"\n    return f\"Bonjour {{nom}} !\"\n\n# Utilisation\nresultat = saluer(\"Alice\")\nprint(resultat)  # Affiche: Bonjour Alice !\n```\n\n**Exemple 2 : Fonction avec plusieurs paramètres**\n[Code avec commentaires détaillés]\n\n**Exemple 3 : Fonction avancée**\n[Code plus complexe avec explications]"
    }},
    {{
      "type": "key_points",
      "title": "📝 Points Clés à Retenir", 
      "content": "• **Point important 1** : Explication courte\n• **Point important 2** : Explication courte\n• **Point important 3** : Explication courte\n• **Point important 4** : Explication courte\n• **Point important 5** : Explication courte"
    }},
    {{
      "type": "advanced",
      "title": "🚀 Pour Aller Plus Loin",
      "content": "Concepts avancés et suggestions d'approfondissement avec exemples de code si pertinent."
    }}
  ]
}}

==== RÈGLES CRITIQUES ====
1. **RÉPONDS PRÉCISÉMENT** à la question posée, pas à autre chose
2. **UTILISE LE FORMAT JSON** exact ci-dessus
3. **INCLUS DU CODE PYTHON** dans chaque section d'exemples
4. **UTILISE LE GRAS** pour les mots-clés importants (**def**, **return**, etc.)
      "content": "Les fonctions sont des blocs de code reutilisables..."
6. **RESTE FOCALISÉ** sur le sujet demandé

IMPORTANT: Réponds UNIQUEMENT avec le JSON, rien d'autre.
ATTENTION: N'utilise JAMAIS de caractères spéciaux comme les guillemets courbes (" "), apostrophes courbes (' '), ou autres caractères Unicode dans le JSON. Utilise uniquement des guillemets droits (") et apostrophes droites (').
"""
        )
        return LLMChain(llm=llm, prompt=simple_prompt)

def test_pedagogue_output():
    """Fonction de test pour vérifier la sortie du pédagogue"""
    chain = get_pedagogue_chain()
    result = chain.invoke({"question": "les fonctions python"})
    print("🔍 Test output:", result)
    return result