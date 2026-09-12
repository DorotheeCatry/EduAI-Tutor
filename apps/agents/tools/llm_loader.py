"""
Choix du client de modèle : Groq, ou Ollama en repli local.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétences concernées : C13 (E3) — maîtrise du coût ; C21 (E5)

Ce module est le seul endroit du projet qui décide À QUI la requête est
envoyée. Le QUEL modèle est décidé par `model_config.py`, et les deux questions
sont séparées : la première dépend de l'environnement, la seconde de l'agent.
"""

import logging
import os

from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_groq import ChatGroq

from apps.agents.tools.model_config import modele_local, use_local_llm

load_dotenv()

logger = logging.getLogger(__name__)

#: Délai d'attente, en secondes, d'un appel au fournisseur.
#:
#: Compétence visée : C13 (épreuve E3)
#: Compétence concernée : C20 (E5) — la valeur vient d'une mesure
#:
#: Il n'y en avait aucun. Un appel qui ne revient pas immobilisait le worker
#: Django qui l'attendait, et rien ne le relâchait : la page tournait jusqu'à
#: ce que le serveur d'application coupe lui-même.
#:
#: Soixante secondes n'est pas un chiffre rond choisi au jugé. Les 90 latences
#: relevées au monitorage (`data_pipeline/data/monitorage/`) donnent une
#: médiane de 1,52 s, un 95e centile de 6,82 s et un maximum de 6,96 s. Le
#: seuil est donc à près de neuf fois le pire appel observé : il ne coupera
#: jamais une génération qui aboutit, et il coupe ce qui ne reviendra pas.
DELAI_D_ATTENTE = int(os.getenv("LLM_TIMEOUT_SECONDES", "60"))

#: Nombre de reprises sur erreur réseau ou 5xx du fournisseur.
#:
#: Deux, et pas davantage : chaque reprise ajoute le délai d'attente complet au
#: temps que l'apprenant passe devant une page qui charge. Le quota, lui, n'est
#: pas touché — il est décompté une fois par génération demandée, dans
#: l'orchestrateur, et non par tentative de transport.
REPRISES = int(os.getenv("LLM_REPRISES", "2"))


def _client_local(motif: str):
    """
    Construit le client Ollama, avec le nom de modèle QU'OLLAMA CONNAÎT.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Le repli passait jusqu'ici le `model_name` reçu en argument — c'est-à-dire
    un identifiant du catalogue Groq, `openai/gpt-oss-120b` par exemple. Ollama
    ne sert aucun modèle portant ce nom : le repli échouait donc à tous les
    coups, sur une erreur de nom de modèle. La « continuité de service » que la
    décision 001 met en avant ne tenait pas à l'exécution.

    Le nom vient désormais de `modele_local()`, qui lit `OLLAMA_MODEL` et non
    `DEFAULT_LLM_MODEL`.
    """
    modele = modele_local()
    logger.info("Modele local Ollama (%s) : %s", motif, modele)
    return ChatOllama(model=modele)


def get_llm(model_name=None):
    """
    Rend un client de modèle compatible LangChain.

    Compétence visée : C10 (épreuve E3)

    Ordre de décision, et il est explicite dans cet ordre :

    1. `USE_LOCAL_LLM` levé → Ollama, quoi qu'il arrive. C'est un choix de
       l'exploitant : il doit primer sur la présence d'une clé.
    2. `GROQ_API_KEY` présente → Groq, avec le modèle demandé.
    3. Sinon → Ollama, faute de clé.

    Choix : le drapeau est consulté EN PREMIER. Motivation : il ne l'était pas
    du tout. `use_local_llm()` existait, était documenté dans la décision 001 et
    dans la chaîne de livraison, était testé — et n'était appelé par personne.
    Une clé présente dans l'environnement suffisait à envoyer au fournisseur les
    invites que ce drapeau était censé garder sur la machine, ce qui vide de son
    sens l'argument de souveraineté des données du Coach.

    Args:
        model_name: identifiant Groq à employer. Ignoré en mode local, où le
            nom vient de `modele_local()` — voir `_client_local`.
    """
    if use_local_llm():
        return _client_local("USE_LOCAL_LLM leve")

    cle_groq = os.getenv("GROQ_API_KEY")
    if not cle_groq:
        return _client_local("aucune GROQ_API_KEY")

    modele = model_name or os.getenv("DEFAULT_LLM_MODEL", "mistral")
    logger.info("Fournisseur Groq : %s", modele)
    return ChatGroq(
        model=modele,
        api_key=cle_groq,
        # Voir les constantes en tête de module : sans délai d'attente, un
        # appel qui pend immobilise le worker qui l'attend.
        timeout=DELAI_D_ATTENTE,
        max_retries=REPRISES,
    )
