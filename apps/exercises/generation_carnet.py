"""
Engendrer une série d'exercices pour un carnet, en un seul appel.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétences concernées : C13 (E3) — quotas ; C17 (E4)

Un carnet demande cinq à vingt énoncés. Les produire un par un coûterait autant
de générations — vingt sur un quota qui en compte quinze par jour, donc un
carnet impossible à composer. Ils sont donc demandés **en une fois**, et
l'appel est décompté **une fois**.

Ce que le carnet n'a pas besoin de recevoir : ni tests, ni solution. Il
n'évalue pas — l'exercice seul s'en charge, avec sa correction et sa
soumission enregistrée. Ne pas les demander raccourcit la réponse, réduit le
risque qu'elle soit tronquée, et évite de faire voyager une solution que
personne n'affichera.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

#: Les bornes du carnet. En deçà, l'exercice seul fait mieux ; au-delà, la
#: réponse du modèle s'allonge au point d'être tronquée, et une séance de plus
#: de vingt énoncés ne se fait pas d'une traite.
MINIMUM, MAXIMUM = 5, 20

INVITE = """Tu prépares un carnet d'exercices Python pour un apprenant adulte.

Sujet : {sujet}
Nombre d'exercices : {nombre}

Rends UNIQUEMENT un tableau JSON, sans texte autour, sans balise de code.
Chaque élément porte exactement ces trois clés :
  "titre"  : un titre court, en français
  "enonce" : la consigne en Markdown, quelques lignes, avec un exemple attendu
  "code"   : le code de départ en Python, avec une signature et un `pass`

Règles :
- les exercices vont du plus simple au plus difficile ;
- chacun se résout en moins de vingt lignes ;
- n'inclus JAMAIS la solution, ni dans le code de départ, ni dans l'énoncé ;
- pas de dépendance externe : la bibliothèque standard suffit.
"""


def _extraire_le_tableau(texte: str):
    """
    Retrouve le tableau JSON dans la réponse du modèle.

    Compétence visée : C10 (épreuve E3)

    Choix : chercher le tableau plutôt que d'exiger une réponse propre.
    Motivation : les modèles encadrent volontiers leur JSON d'une phrase ou
    d'une balise de code, et refuser ces réponses reviendrait à jeter un
    contenu correct pour un emballage. Ce qui n'est pas analysable, en
    revanche, est écarté : mieux vaut un carnet vide qu'un carnet inventé.
    """
    if not texte:
        return []
    depouille = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.M).strip()
    debut, fin = depouille.find("["), depouille.rfind("]")
    if debut == -1 or fin <= debut:
        return []
    try:
        # `strict=False` : un modèle place volontiers de vrais sauts de ligne
        # dans ses chaînes plutôt que la séquence `\n`. Le JSON est alors
        # invalide à la lettre, et parfaitement lisible — le refuser ferait
        # perdre un contenu correct pour une question de forme.
        charge = json.loads(depouille[debut:fin + 1], strict=False)
    except json.JSONDecodeError as erreur:
        logger.warning("[carnet] réponse illisible du modèle : %s", erreur)
        return []
    return charge if isinstance(charge, list) else []


def _retenir(entree):
    """Ne garde qu'une entrée complète, et rend ses trois champs nettoyés."""
    if not isinstance(entree, dict):
        return None
    titre = str(entree.get("titre") or "").strip()
    enonce = str(entree.get("enonce") or "").strip()
    if not titre or not enonce:
        return None
    return {
        "titre": titre,
        "enonce": enonce,
        "code": str(entree.get("code") or "# À vous de jouer\n"),
    }


def engendrer(utilisateur, sujet: str, nombre: int):
    """
    Rend une liste d'exercices pour le carnet, ou une liste vide.

    Compétence visée : C10 (épreuve E3)
    Compétence concernée : C13 (E3)

    Le quota est décompté par l'orchestrateur, comme pour toute génération :
    une série, un décompte. `QuotaDepasse` remonte à l'appelant, qui seul sait
    comment l'annoncer — le refus n'est pas une panne.

    Rend une liste vide si la réponse est inexploitable. L'appelant l'affiche
    comme telle : un carnet vide se voit, un carnet d'énoncés inventés non.
    """
    from apps.agents.agent_orchestrator import get_orchestrator

    nombre = max(MINIMUM, min(int(nombre), MAXIMUM))
    orchestrateur = get_orchestrator(utilisateur)

    reponse = orchestrateur.answer_question(
        INVITE.format(sujet=sujet, nombre=nombre))
    texte = reponse.get("answer") or reponse.get("reponse") or ""

    exercices = [e for e in (_retenir(x) for x in _extraire_le_tableau(texte)) if e]
    if not exercices:
        logger.warning("[carnet] aucun exercice exploitable pour « %s »", sujet)
    return exercices[:nombre]
