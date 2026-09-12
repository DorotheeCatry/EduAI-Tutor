"""
Agent Coach : compose les quiz et les exercices à partir d'un sujet.

Compétence visée : C10 (épreuve E3) — agents et interactions
Compétences concernées : C13 (E3) — maîtrise du coût ; C17 (E4)

**Ce module ne fabrique rien.** C'est sa règle principale, et elle a été
introduite le 12/09/2026 en remplacement d'un comportement inverse.

Auparavant, un échec de génération ne remontait pas : `generate_quiz` rendait
un quiz d'exemple — « Question d'exemple sur X », quatre options « Option A » à
« Option D », et `correct_answer: 0`. Ce quiz était affiché comme un vrai. Il
était répondable, notable, et sa « bonne réponse » était l'option A, choisie
arbitrairement. L'apprenant qui répondait autre chose enregistrait un
`UserMistake`, qui alimente `notions_a_revoir`, que Koda cite ensuite dans sa
salutation. Une erreur inventée devenait une notion à revoir.

C'est le même défaut que les sept foyers de données fabriquées retirés du
projet en une semaine, à une différence près qui l'aggrave : celui-ci
**écrivait** en base au lieu de seulement afficher.

`generate_code_exercise` portait le même défaut — solution attendue
`print('Hello World')`, test `{"input": "test", "expected": "result"}`. Elle a
été **supprimée** plutôt que corrigée : elle n'avait aucun appelant. La
génération d'exercices de l'application passe par `apps/exercises/views.py`,
qui compose sa propre invite et appelle `answer_question`. Garder une seconde
implémentation que personne n'exécute, c'est garder du code que personne ne
corrige — et c'est bien ce qui s'était passé.

Un échec lève donc désormais `GenerationImpossible`. Les appelants savent déjà
traiter l'absence de questions — `AIOrchestrator.create_quiz` rend
`{"questions": []}` avec le motif, et les deux vues de quiz vérifient la liste
avant d'en faire quoi que ce soit. Dire « la génération a échoué » est une
information ; rendre un faux quiz n'en est pas une.

Distinction avec le repli des exercices (`apps/exercises/views.py`), qui, lui,
est conservé : celui-là crée un gabarit vide, **le dit à l'apprenant** par un
message d'avertissement, et refuse de le rattacher à une compétence pour qu'il
ne fasse progresser personne. Un repli annoncé et neutralisé n'est pas une
donnée fabriquée. Un repli silencieux qui se fait passer pour un résultat, si.
"""

import logging

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from apps.agents.tools.llm_loader import get_llm
from apps.agents.tools.model_config import get_model_for
from apps.agents.utils import load_prompt, parse_text_quiz

logger = logging.getLogger(__name__)


class GenerationImpossible(RuntimeError):
    """
    L'agent n'a pas pu produire ce qu'on lui demandait.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Choix : une exception nommée plutôt qu'un `None` ou un objet vide.
    Motivation : un appelant qui reçoit `None` doit se souvenir de le tester ;
    un appelant qui reçoit une exception ne peut pas l'ignorer par distraction.
    Et le motif voyage avec — ce qui permet de l'afficher et de le journaliser
    au lieu de le perdre.
    """


def get_coach_chain(model_name=None):
    """
    Chaîne du Coach : engendre un questionnaire à choix multiples.

    Compétence visée : C10 (épreuve E3)
    Choix : le modèle n'est pas codé en dur mais résolu par `get_model_for`.
    Motivation : voir `tools/model_config.py` — un identifiant écrit en dur dans
    trois fichiers a déjà provoqué une panne complète de la couche IA quand le
    fournisseur l'a retiré de son catalogue (décision 001).
    """
    if model_name is None:
        model_name = get_model_for("coach")

    invite = PromptTemplate(
        input_variables=["topic", "num_questions", "language"],
        template=load_prompt("coach"),
    )
    return LLMChain(llm=get_llm(model_name=model_name), prompt=invite)


def generate_quiz(topic, num_questions=5, language="fr"):
    """
    Engendre un quiz sur un sujet, ou lève si le modèle n'a rien donné d'exploitable.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Choix : `invoke` et non `run`. Motivation : `Chain.run` est déprécié dans
    LangChain 0.3 et supprimé en 1.0 ; `invoke` est l'appel qui survivra à la
    prochaine montée de version. La sortie se lit alors sous la clé `text`.

    Choix : deux échecs distincts, un seul type d'exception. Motivation : que
    le modèle soit injoignable ou qu'il ait répondu hors format, le résultat
    pour l'apprenant est le même — pas de quiz. Mais le motif diffère, et il
    est journalisé séparément.

    Raises:
        GenerationImpossible: le modèle n'a pas répondu, ou sa réponse ne
            contient aucune question analysable.
    """
    try:
        chaine = get_coach_chain()
        sortie = chaine.invoke({
            "topic": topic,
            "num_questions": num_questions,
            "language": language,
        })
    except Exception as erreur:
        logger.exception("Quiz sur %r : appel au modele en echec.", topic)
        raise GenerationImpossible(
            f"le modèle n'a pas répondu ({type(erreur).__name__})"
        ) from erreur

    brut = sortie.get("text", "") if isinstance(sortie, dict) else str(sortie)
    logger.debug("Quiz sur %r : %d caracteres recus.", topic, len(brut))

    quiz = parse_text_quiz(brut)
    if not quiz or not quiz.get("questions"):
        logger.warning(
            "Quiz sur %r : reponse du modele non analysable, aucune question.",
            topic,
        )
        raise GenerationImpossible(
            "la réponse du modèle ne contient aucune question exploitable"
        )

    return quiz
