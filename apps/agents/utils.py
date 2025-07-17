from importlib.resources import files
from pathlib import Path

def load_prompt(name: str) -> str:
    """
    Charge le contenu d’un fichier prompt dans apps/agents/prompts/.
    Le nom ne doit pas contenir l’extension (.txt est ajoutée automatiquement).
    Ex : load_prompt("pedagogue") => apps/agents/prompts/pedagogue.txt
    """
    try:
        prompt_path = files("apps.agents.prompts").joinpath(f"{name}.txt")
        if not prompt_path.is_file():
            raise FileNotFoundError(f"Prompt '{name}.txt' non trouvé dans agents/prompts/")
        return prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Erreur lors du chargement du prompt '{name}': {e}")

import re

import re

def parse_text_quiz(text):
    """
    Parses a free-text quiz with potential code blocks.
    Expected format:
        Q1. ...
        ```python
        code
        ```
        A. ...
        Answer: X
        Explanation: ...
    Returns:
        {"questions": [...]}
    """
    questions = []

    # Split into blocks using Q<number>.
    blocks = re.split(r"\nQ\d+\.", "\n" + text.strip())

    for block in blocks[1:]:
        lines = block.strip().splitlines()

        question_lines = []
        options = []
        correct_letter = None
        explanation = ""

        # Phase 1: Extract question lines (everything before A./B./C.)
        in_question = True
        for line in lines:
            stripped = line.strip()
            if re.match(r"^[A-D]\. ", stripped):
                in_question = False
                options.append(stripped[3:].strip())
            elif in_question:
                question_lines.append(line)
            elif re.match(r"^[A-D]\. ", stripped):
                options.append(stripped[3:].strip())
            elif stripped.lower().startswith("answer:"):
                correct_letter = stripped.split(":", 1)[1].strip().upper()
            elif stripped.lower().startswith("explanation:"):
                explanation = stripped.split(":", 1)[1].strip()

        question_text = "\n".join(question_lines).strip()

        if question_text and options and correct_letter in "ABCD":
            questions.append({
                "question": question_text,
                "options": options,
                "correct_answer": "ABCD".index(correct_letter),
                "explanation": explanation
            })

    print("✅ Parsed questions:", questions)
    return {"questions": questions}


