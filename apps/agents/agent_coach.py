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
    AI Coach Agent: generates MCQs and exercises from a given topic.
    """
    llm = get_llm(model_name=model_name)
    
    # Prompt for generating MCQs
    quiz_prompt = PromptTemplate(
        input_variables=["topic", "num_questions", "language"],
        template=load_prompt("coach")
    )
    return LLMChain(llm=llm, prompt=quiz_prompt)

def get_code_exercise_chain(model_name="meta-llama/llama-4-scout-17b-16e-instruct"):
    """
    AI Coach Agent: generates code completion exercises.
    """
    llm = get_llm(model_name=model_name)
    
    code_prompt = PromptTemplate(
        input_variables=["topic"],
        template="""
You are a programming expert who creates code exercises.

TOPIC: {topic}

Create a practical code exercise on "{topic}" at intermediate level.

The exercise should include:
- A clear statement
- Code to complete with missing parts (marked with # TODO)
- The complete solution
- Tests to verify the solution

RESPONSE FORMAT (strict JSON):
{{
  "title": "Exercise title",
  "description": "Detailed description of what to do",
  "starter_code": "Starting code with # TODO",
  "solution": "Complete solution code",
  "tests": [
    {{"input": "input value", "expected": "expected result"}}
  ]
}}

Respond ONLY with JSON, no additional text.
"""
    )
    
    return LLMChain(llm=llm, prompt=code_prompt)

def generate_quiz(topic, num_questions=5, language="fr"):
    try:
        chain = get_coach_chain()
        result = chain.run(
            topic=topic,
            num_questions=num_questions,
            language=language
        )
        print("🧠 Raw model output:", result)

        quiz_data = parse_text_quiz(result)
        if quiz_data and quiz_data.get("questions"):
            return quiz_data

    except Exception as e:
        print(f"❌ Quiz generation failed: {e}")

    # Fallback with language support
    fallback_text = {
        "fr": {
            "question": f"Question d'exemple sur {topic}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "Explication d'exemple"
        },
        "en": {
            "question": f"Example question on {topic}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "Sample explanation"
        }
    }
    
    lang_text = fallback_text.get(language, fallback_text["en"])
    
    return {
        "questions": [
            {
                "question": lang_text["question"],
                "options": lang_text["options"],
                "correct_answer": 0,
                "explanation": lang_text["explanation"]
            }
        ]
    }

def generate_code_exercise(topic):
    """
    Generates a code exercise on a given topic.
    """
    try:
        chain = get_code_exercise_chain()
        result = chain.run(topic=topic)
        
        # Parse the JSON
        exercise_data = json.loads(result)
        return exercise_data
        
    except Exception as e:
        print(f"Error during exercise generation: {e}")
        # Fallback with example exercise
        return {
            "title": f"Exercise on {topic}",
            "description": f"Practical exercise on {topic}",
            "starter_code": f"# TODO: Implement {topic}\npass",
            "solution": f"# Solution for {topic}\nprint('Hello World')",
            "tests": [{"input": "test", "expected": "result"}]
        }