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
