# apps/agents/agent_coach.py

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from apps.agents.tools.llm_loader import get_llm
from langchain_community.vectorstores import Chroma
from apps.rag.utils import load_embedding_function
from apps.agents.utils import load_prompt, parse_text_quiz
import json
import random

def get_coach_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    Agent Coach IA : génère des QCM et exercices à partir d'un sujet donné.
    """
    llm = get_llm(model_name=model_name)
    
    # Prompt pour générer des QCM
    quiz_prompt = PromptTemplate(
        input_variables=["topic", "num_questions"],
        template=load_prompt("coach")
    )
    return LLMChain(llm=llm, prompt=quiz_prompt)

def get_code_exercise_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    Agent Coach IA : génère des exercices de code à compléter.
    """
    llm = get_llm(model_name=model_name)
    
    code_prompt = PromptTemplate(
        input_variables=["topic"],
        template="""
Tu es un expert en programmation qui crée des exercices de code.

SUJET : {topic}

Crée un exercice de code pratique sur "{topic}" de niveau intermédiaire.

L'exercice doit inclure :
- Un énoncé clair
- Du code à compléter avec des parties manquantes (marquées par # TODO)
- La solution complète
- Des tests pour vérifier la solution

FORMAT DE RÉPONSE (JSON strict) :
{{
  "title": "Titre de l'exercice",
  "description": "Description détaillée de ce qu'il faut faire",
  "starter_code": "Code de départ avec # TODO",
  "solution": "Code solution complet",
  "tests": [
    {{"input": "valeur d'entrée", "expected": "résultat attendu"}}
  ]
}}

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire.
"""
    )
    
    return LLMChain(llm=llm, prompt=code_prompt)

def generate_quiz(topic, num_questions=5):
    try:
        chain = get_coach_chain()
        result = chain.run(
            topic=topic,
            num_questions=num_questions
        )
        print("🧠 Raw model output:", result)

        quiz_data = parse_text_quiz(result)
        if quiz_data and quiz_data.get("questions"):
            return quiz_data

    except Exception as e:
        print(f"❌ Quiz generation failed: {e}")

    # Fallback
    return {
        "questions": [
            {
                "question": f"Example question on {topic}",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": 0,
                "explanation": "Sample explanation"
            }
        ]
    }

def generate_code_exercise(topic):
    """
    Génère un exercice de code sur un sujet donné.
    """
    try:
        chain = get_code_exercise_chain()
        result = chain.run(topic=topic)
        
        # Parser le JSON
        exercise_data = json.loads(result)
        return exercise_data
        
    except Exception as e:
        print(f"Erreur lors de la génération de l'exercice : {e}")
        # Fallback avec un exercice exemple
        return {
            "title": f"Exercice sur {topic}",
            "description": f"Exercice pratique sur {topic}",
            "starter_code": f"# TODO: Implémentez {topic}\npass",
            "solution": f"# Solution pour {topic}\nprint('Hello World')",
            "tests": [{"input": "test", "expected": "result"}]
        }