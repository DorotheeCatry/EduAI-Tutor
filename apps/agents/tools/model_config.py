"""
Configuration centralisée des modèles LLM, avec routage par agent.

Compétence visée : C10 (épreuve E3) — intégration du modèle dans l'application
Compétence visée : C7 (épreuve E2) — comparaison de services d'IA

Choix : les identifiants de modèle sont externalisés en variables
d'environnement plutôt qu'écrits en dur dans chaque agent. Motivation directe :
le modèle `meta-llama/llama-4-scout-17b-16e-instruct`, codé en dur dans trois
fichiers, a été retiré du catalogue Groq et a provoqué une panne complète de la
couche IA (404 model_not_found). Voir docs/decisions/001.

Choix : routage par agent plutôt qu'un modèle unique. Les quatre agents ont des
besoins distincts (qualité de raisonnement pour Researcher et Pedagogue,
latence perçue pour Coach, volume d'appels courts pour Watcher). Un modèle
unique surpaie les tâches simples et bride les tâches complexes.

Choix : bascule Ollama en repli. Motivation double — continuité de service en
cas d'indisponibilité du fournisseur (Groq a connu des interruptions), et
possibilité de traiter en local des données d'apprenants potentiellement
mineurs sans transfert à un tiers (cf. RGPD, C4).
"""

import logging
import os

logger = logging.getLogger(__name__)

# --- Catalogue des modèles disponibles sur le projet Groq ---
# Débloqués dans la console Groq (settings > project > limits) le 25/08/2026.
# Source de vérification : capture d'écran datée, annexe du rapport E2.
MODELE_QUALITE = "openai/gpt-oss-120b"   # 500 t/s — raisonnement
MODELE_RAPIDE = "openai/gpt-oss-20b"     # 1000 t/s — latence
MODELE_ALTERNATIF = "qwen/qwen3.6-27b"   # famille distincte — benchmark C7

# --- Routage par défaut, surchargeable par variable d'environnement ---
ROUTAGE_PAR_DEFAUT = {
    "researcher": MODELE_QUALITE,   # synthèse de chunks RAG : risque d'hallucination
    "pedagogue": MODELE_QUALITE,    # adaptation au niveau de l'apprenant : nuance
    "coach": MODELE_RAPIDE,         # feedback interactif dans Monaco : latence perçue
    "watcher": MODELE_RAPIDE,       # classification, appels fréquents et courts
}

AGENTS_CONNUS = tuple(ROUTAGE_PAR_DEFAUT)

# Nom du modèle d'embedding servi par Ollama pour le RAG.
MODELE_EMBEDDING = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")


def get_model_for(agent: str) -> str:
    """
    Retourne l'identifiant du modèle à utiliser pour un agent donné.

    Compétence visée : C10 (épreuve E3)

    L'ordre de résolution est explicite et documenté :
      1. variable d'environnement spécifique à l'agent (GROQ_MODEL_RESEARCHER…) ;
      2. variable d'environnement globale (GROQ_MODEL) ;
      3. routage par défaut défini ci-dessus.

    Cet ordre permet de basculer un seul agent pendant une démonstration sans
    redéploiement, ce qui est une exigence pratique de la soutenance.

    Args:
        agent: nom de l'agent, parmi AGENTS_CONNUS.

    Returns:
        L'identifiant de modèle à passer au client Groq.

    Raises:
        ValueError: si l'agent est inconnu. On échoue explicitement plutôt que
            de retomber silencieusement sur un modèle par défaut : une faute de
            frappe dans un nom d'agent doit être visible immédiatement.
    """
    agent = agent.lower().strip()

    if agent not in ROUTAGE_PAR_DEFAUT:
        raise ValueError(
            f"Agent inconnu : {agent!r}. Agents attendus : {AGENTS_CONNUS}."
        )

    variable_specifique = f"GROQ_MODEL_{agent.upper()}"
    modele = (
        os.getenv(variable_specifique)
        or os.getenv("GROQ_MODEL")
        or ROUTAGE_PAR_DEFAUT[agent]
    )

    logger.debug("Agent %s → modèle %s", agent, modele)
    return modele


def use_local_llm() -> bool:
    """
    Indique si la couche IA doit utiliser Ollama en local plutôt que Groq.

    Compétence visée : C10 (épreuve E3)

    Choix : un simple drapeau d'environnement (USE_LOCAL_LLM) plutôt qu'une
    détection automatique de panne. Le basculement doit rester une décision
    explicite et reproductible, y compris en direct pendant la démonstration.
    """
    return os.getenv("USE_LOCAL_LLM", "false").lower() in {"1", "true", "yes"}
