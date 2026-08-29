"""
Adaptateur asynchrone vers les agents existants.

Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA
Compétence visée : C10 (épreuve E3) — intégration du modèle

Ce module ne contient aucune logique d'agent. Il fait deux choses, et rien
d'autre : il rend asynchrones des appels qui ne le sont pas, et il borne la
concurrence vers le fournisseur.

POURQUOI FASTAPI PLUTÔT QUE DRF, VISIBLE ICI
Un appel au fournisseur de modèles dure entre deux et dix secondes, et ce temps
est passé à attendre le réseau — le processus ne calcule rien. Sous Django REST
Framework en WSGI, chaque appel occupe un travailleur pendant toute cette
attente : huit travailleurs, huit requêtes simultanées, la neuvième attend qu'un
travailleur se libère.

Ici, chaque attente rend la main à la boucle d'événements. Deux mécanismes,
selon ce que l'appelé sait faire :

  - `await ...ainvoke(...)` quand la chaîne LangChain expose une variante
    asynchrone — l'attente est alors réellement non bloquante de bout en bout ;
  - `await asyncio.to_thread(...)` pour les agents synchrones, qui partent dans
    un fil d'exécution pendant que la boucle continue de servir les autres
    requêtes.

Le second n'est pas le premier : un fil reste mobilisé. Mais il libère la boucle,
ce qui suffit à servir des requêtes courtes — la santé, la recherche — pendant
qu'une génération longue est en cours.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .securite import CONCURRENCE_MAX

logger = logging.getLogger(__name__)

#: Sémaphore bornant les appels simultanés au fournisseur.
#:
#: Choix : un sémaphore et non une file d'attente. Motivation : une file
#: accepterait les requêtes excédentaires et les ferait patienter sans limite,
#: jusqu'à ce que le client abandonne — en ayant tout de même réservé de la
#: mémoire. Le sémaphore fait attendre dans la requête elle-même, où le délai
#: d'expiration du client s'applique.
_verrou_fournisseur = asyncio.Semaphore(CONCURRENCE_MAX)


class ServiceIndisponible(RuntimeError):
    """Levée quand un agent ne peut pas être construit ou appelé."""


async def _appeler(fonction, *args, **kwargs) -> Any:
    """
    Exécute un appel synchrone d'agent hors de la boucle d'événements.

    Compétence visée : C9 (épreuve E2)

    Le sémaphore est pris AVANT le passage en fil d'exécution : borner après
    coup laisserait démarrer autant de fils que de requêtes, et le plafond ne
    protégerait plus rien.
    """
    async with _verrou_fournisseur:
        return await asyncio.to_thread(fonction, *args, **kwargs)


def _texte(resultat: Any) -> str:
    """
    Extrait le texte d'une réponse d'agent, quelle que soit sa forme.

    Compétence visée : C9 (épreuve E2)

    Les agents du projet renvoient tantôt une chaîne, tantôt un message
    LangChain, tantôt un dictionnaire à clé `result`, `text` ou `output_text`
    selon le type de chaîne utilisé. Traiter les quatre coûte quelques lignes ;
    n'en traiter qu'une produirait un contrat de sortie qui échoue sur trois
    points de terminaison sur quatre.
    """
    if resultat is None:
        return ""
    if isinstance(resultat, str):
        return resultat
    contenu = getattr(resultat, "content", None)
    if isinstance(contenu, str):
        return contenu
    if isinstance(resultat, dict):
        for cle in ("result", "text", "output_text", "answer", "contenu"):
            valeur = resultat.get(cle)
            if isinstance(valeur, str) and valeur.strip():
                return valeur
            if hasattr(valeur, "content"):
                return str(valeur.content)
    return str(resultat)


def _fragments(resultat: Any) -> list[Any]:
    """Retrouve les documents sources d'une réponse RAG, s'il y en a."""
    if isinstance(resultat, dict):
        for cle in ("source_documents", "context", "documents"):
            valeur = resultat.get(cle)
            if isinstance(valeur, list):
                return valeur
    return []


def semble_tronquee(texte: str) -> bool:
    """
    Dit si une réponse paraît coupée avant sa fin.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C21 (épreuve E5)

    Choix : signaler plutôt que corriger. Motivation : une réponse tronquée par
    une limite de jetons n'est pas une erreur du service — elle aboutit, elle
    est simplement incomplète. La renvoyer sans le dire ferait porter au client
    la charge de s'en apercevoir ; la refuser gaspillerait un appel déjà
    facturé. Le drapeau laisse l'appelant décider.

    Le contrôle est volontairement grossier : accolades non refermées, ou
    absence de ponctuation finale. Un contrôle fin supposerait de connaître le
    format attendu, qui varie d'un agent à l'autre.
    """
    texte = (texte or "").strip()
    if not texte:
        return True
    if texte.count("{") != texte.count("}"):
        return True
    if texte.count("[") != texte.count("]"):
        return True
    return texte[-1] not in ".!?»\"'`}]…"


async def generer_cours(sujet: str, difficulte: str) -> dict[str, Any]:
    """
    Produit un cours en réutilisant l'orchestrateur existant.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C10 (épreuve E3)

    Choix : passer par `get_orchestrator()` plutôt que d'appeler le Pédagogue
    directement. Motivation : l'orchestrateur porte déjà le repli sans RAG, la
    gestion des variantes d'invocation et la déclaration de l'agent courant au
    monitorage. Le contourner obligerait à réécrire ces trois comportements ici,
    et à les maintenir en double.
    """
    from apps.agents.agent_orchestrator import get_orchestrator

    debut = time.perf_counter()
    orchestrateur = await asyncio.to_thread(
        # Décompté du plafond global du jour, pas d'un quota d'apprenant :
        # cette API est consommée par des programmes (C13).
        get_orchestrator, None, pour_service_ia=True,
    )
    resultat = await _appeler(orchestrateur.generate_course, sujet, difficulte)
    return _emballer("pedagogue", resultat, debut)


async def expliquer(notion: str, niveau: str) -> dict[str, Any]:
    """
    Réexplique une notion, servie par le Pédagogue.

    Compétence visée : C9 (épreuve E2)

    Choix : la question transmise à l'agent porte le niveau de l'apprenant.
    Motivation : c'est la seule différence entre ce point de terminaison et la
    génération de cours, et elle est essentielle — réexpliquer suppose que la
    première explication n'a pas suffi.
    """
    from apps.agents.agent_orchestrator import get_orchestrator

    debut = time.perf_counter()
    orchestrateur = await asyncio.to_thread(
        # Décompté du plafond global du jour, pas d'un quota d'apprenant :
        # cette API est consommée par des programmes (C13).
        get_orchestrator, None, pour_service_ia=True,
    )
    question = (
        f"Réexplique la notion suivante à un apprenant de niveau {niveau}, "
        f"autrement qu'un cours classique, avec un exemple concret : {notion}"
    )
    resultat = await _appeler(orchestrateur.answer_question, question)
    return _emballer("pedagogue", resultat, debut)


async def generer_exercice(sujet: str, nombre: int) -> dict[str, Any]:
    """
    Produit un exercice de code, servi par le Coach.

    Compétence visée : C9 (épreuve E2)
    """
    from apps.agents.agent_orchestrator import get_orchestrator

    debut = time.perf_counter()
    orchestrateur = await asyncio.to_thread(
        # Décompté du plafond global du jour, pas d'un quota d'apprenant :
        # cette API est consommée par des programmes (C13).
        get_orchestrator, None, pour_service_ia=True,
    )
    resultat = await _appeler(orchestrateur.create_quiz, sujet, nombre)
    return _emballer("coach", resultat, debut)


async def donner_feedback(enonce: str, code: str,
                          message_erreur: str | None) -> dict[str, Any]:
    """
    Produit un retour sur une soumission de code, servi par le Coach.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C4 (épreuve E1) — minimisation

    Choix : le prompt est construit ici, à partir des seuls champs reçus.
    Motivation : aucun identifiant d'apprenant n'entre dans ce contrat, donc
    aucun ne peut atteindre le fournisseur. Ce qui n'est pas reçu ne peut pas
    être transmis par distraction.
    """
    from apps.agents.tools.llm_loader import get_llm
    from apps.agents.tools.model_config import get_model_for
    from apps.monitoring.sondes import contexte_agent

    debut = time.perf_counter()
    modele = get_model_for("coach")

    invite = (
        "Tu es un formateur qui relit le code d'un apprenant.\n\n"
        f"ÉNONCÉ :\n{enonce}\n\n"
        f"CODE SOUMIS :\n```\n{code}\n```\n"
    )
    if message_erreur:
        invite += f"\nERREUR OBTENUE À L'EXÉCUTION :\n{message_erreur}\n"
    invite += (
        "\nDonne un retour bref et actionnable : ce qui va, ce qui ne va pas, "
        "et la piste de correction. Ne réécris pas le code entier — l'apprenant "
        "doit le corriger lui-même."
    )

    async def _executer():
        # La déclaration de l'agent courant est posée DANS le fil d'exécution,
        # les variables de contexte n'étant pas partagées entre fils.
        def _appel_synchrone():
            with contexte_agent("coach"):
                return get_llm(model_name=modele).invoke(invite)

        return await _appeler(_appel_synchrone)

    resultat = await _executer()
    emballe = _emballer("coach", resultat, debut)
    emballe["modele"] = modele
    return emballe


async def rechercher(requete: str, nombre: int) -> dict[str, Any]:
    """
    Interroge le corpus sans appeler de modèle de langage.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C20 (épreuve E5)

    Choix : `ainvoke` et non `invoke`. Motivation : c'est le seul chemin du
    service où LangChain expose une variante réellement asynchrone. L'attente
    du vector store rend alors la main à la boucle d'événements sans mobiliser
    de fil — c'est la démonstration la plus nette de ce que FastAPI apporte ici.

    Choix : aucun sémaphore sur ce chemin. Motivation : le sémaphore protège le
    quota du fournisseur, or cette recherche ne l'atteint pas. La brider au
    rythme des générations reviendrait à payer une protection dont elle n'a pas
    besoin.
    """
    from langchain_community.vectorstores import Chroma

    from apps.monitoring.sondes import contexte_agent
    from apps.rag.utils import COLLECTION_DOCUMENTAIRE, load_embedding_function

    debut = time.perf_counter()
    try:
        with contexte_agent("researcher"):
            magasin = await asyncio.to_thread(
                Chroma,
                persist_directory="apps/rag/chroma",
                embedding_function=load_embedding_function(),
                # Le corpus collecté par le pipeline (21 189 fragments), et non
                # les supports de formation (387). C'est la question posée à ce
                # point de terminaison : ce que dit la documentation, pas ce que
                # le programme prévoit. Voir apps/rag/utils.py.
                collection_name=COLLECTION_DOCUMENTAIRE,
            )
            recuperateur = magasin.as_retriever(search_kwargs={"k": nombre})
            fragments = await recuperateur.ainvoke(requete)
    except Exception as exception:  # noqa: BLE001 — converti en erreur de service
        raise ServiceIndisponible(
            f"Recherche impossible dans le corpus : {exception}"
        ) from exception

    return {
        "fragments": fragments or [],
        "latence_secondes": round(time.perf_counter() - debut, 3),
    }


def _emballer(agent: str, resultat: Any, debut: float) -> dict[str, Any]:
    """
    Ramène une réponse d'agent au contrat de sortie de l'API.

    Compétence visée : C9 (épreuve E2)
    """
    from apps.agents.tools.model_config import get_model_for

    texte = _texte(resultat)
    fragments = _fragments(resultat)
    return {
        "agent": agent,
        "modele": get_model_for(agent),
        "contenu": texte,
        "fragments_utilises": len(fragments),
        "latence_secondes": round(time.perf_counter() - debut, 3),
        "tronquee": semble_tronquee(texte),
    }
