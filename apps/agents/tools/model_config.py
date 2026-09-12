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
souveraineté des données, les prompts de l'agent Coach contenant du code
d'apprenant — une production personnelle rattachable à une personne identifiée
(cf. docs/rgpd_eduai_data.md, C4). Le public visé est exclusivement adulte
(décisions 004 et 005) : le repli local ne se justifie donc pas par la
protection des mineurs, mais par le fait que ces prompts n'ont pas à sortir de
la machine.
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

# --- Le modèle du repli local ---
#
# Compétence visée : C10 (épreuve E3)
#
# Il est nommé À PART des modèles Groq, et c'est le point important. Les
# identifiants ci-dessus (`openai/gpt-oss-120b`…) sont ceux du catalogue Groq :
# Ollama ne les connaît pas. Passer l'un d'eux à Ollama produit un 404 sur un
# nom de modèle, c'est-à-dire exactement la panne que la décision 001 était
# censée rendre impossible — un repli qui échoue est pire qu'une absence de
# repli, parce qu'on croit l'avoir.
MODELE_LOCAL_PAR_DEFAUT = "mistral"


def modele_local() -> str:
    """
    Rend le nom du modèle à demander à Ollama.

    Compétence visée : C10 (épreuve E3)

    Choix : une variable dédiée (`OLLAMA_MODEL`) plutôt que la réutilisation de
    `DEFAULT_LLM_MODEL`. Motivation : cette dernière porte un identifiant Groq
    dans le `.env.example` du projet. La partager reviendrait à demander
    `openai/gpt-oss-120b` à Ollama.
    """
    return os.getenv("OLLAMA_MODEL", MODELE_LOCAL_PAR_DEFAUT)


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

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Choix : un simple drapeau d'environnement (USE_LOCAL_LLM) plutôt qu'une
    détection automatique de panne. Le basculement doit rester une décision
    explicite et reproductible, y compris en direct pendant la démonstration.

    **Cette fonction n'était appelée par personne.** Le drapeau est décrit dans
    la décision 001, dans `docs/chaine_livraison.md` et dans le dossier
    d'incident du 25/08 — « un drapeau `USE_LOCAL_LLM` bascule vers Ollama » —
    et il ne basculait rien : `get_llm` choisissait sur la seule présence de
    `GROQ_API_KEY`. Le manque était noté dans le journal du 25/08 et n'avait pas
    été repris.

    Les tests de `tests/test_routage_modeles.py` éprouvaient la fonction, et
    passaient : ils ne pouvaient pas voir qu'aucun appelant ne s'en servait.
    C'est la forme d'assurance la plus trompeuse — un test vert sur une
    fonctionnalité absente. `get_llm` l'appelle désormais en premier, et un test
    éprouve le comportement et non plus seulement la lecture du drapeau.
    """
    return os.getenv("USE_LOCAL_LLM", "false").lower() in {"1", "true", "yes"}
