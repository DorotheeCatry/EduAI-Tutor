"""
Tests de l'enregistrement du résultat d'un quiz solo.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C20 (E5) — données du suivi ; C21 (E5)

Ces tests portent sur l'incident 010, et sur ses deux défauts distincts :

1. Le gabarit du quiz n'appelait jamais la vue d'enregistrement. Rien n'était
   écrit : ni clôture de session, ni erreur, ni compteur.
2. Les erreurs étaient enregistrées avec `topic=session_id` — un identifiant
   de session au lieu de la notion — sous un commentaire « temporary topic ».

Ils vérifient donc ce qui est écrit en base après une soumission, et sous
quel libellé. Un test qui se contenterait d'un code de retour 200 aurait
laissé passer les deux.
"""

import json

import pytest
from django.urls import reverse

from apps.agents.agent_watcher import LearningSession, UserMistake


QUESTIONS = [
    {
        "question": "Que rend `len([1, 2, 3])` ?",
        "options": ["2", "3", "4", "une erreur"],
        "correct_answer": 1,
        "explanation": "La liste porte trois éléments.",
    },
    {
        "question": "Comment ajoute-t-on un élément à une liste ?",
        "options": ["add()", "push()", "append()", "insert_last()"],
        "correct_answer": 2,
        "explanation": "`append` ajoute en fin de liste.",
    },
]


@pytest.fixture
def apprenant(django_user_model):
    """Compte d'essai, propre à chaque test."""
    return django_user_model.objects.create_user(
        username="apprenante_quiz",
        email="quiz@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )


@pytest.fixture
def session_de_quiz(apprenant):
    """
    Session de quiz telle que `create_quiz` la produit.

    Compétence visée : C18 (épreuve E4)

    Les questions sont dans les métadonnées : c'est ce qui permet au serveur
    de corriger lui-même, au lieu de croire ce que le navigateur lui renvoie.
    """
    return LearningSession.objects.create(
        user=apprenant,
        topic="les listes en Python",
        activity_type="quiz",
        metadata={"num_questions": 2, "language": "fr", "questions": QUESTIONS},
    )


def _soumettre(client, session, reponses):
    return client.post(
        reverse("quiz:submit"),
        data=json.dumps({"session_id": session.id, "answers": reponses}),
        content_type="application/json",
        secure=True,
    )


@pytest.mark.django_db
def test_l_erreur_est_enregistree_sous_la_notion_et_non_la_session(
        client, apprenant, session_de_quiz):
    """
    Le sujet d'une erreur est la notion du quiz, pas l'identifiant de session.

    Compétence visée : C21 (épreuve E5) — non-régression de l'incident 010

    C'est le défaut central : `record_mistake(topic=session_id, ...)` écrivait
    un nombre là où une notion est attendue. Le bloc « à revoir » de la page
    d'accueil ne pouvait rien en tirer.
    """
    client.force_login(apprenant)

    reponse = _soumettre(client, session_de_quiz, [1, 0])

    assert reponse.status_code == 200
    erreurs = UserMistake.objects.filter(user=apprenant)
    assert erreurs.count() == 1, "la seule mauvaise réponse doit être enregistrée"

    erreur = erreurs.get()
    assert erreur.topic == "les listes en Python"
    assert erreur.topic != str(session_de_quiz.id)
    assert erreur.question == QUESTIONS[1]["question"]
    assert erreur.user_answer == "add()"
    assert erreur.correct_answer == "append()"


@pytest.mark.django_db
def test_une_question_sans_reponse_se_distingue_d_une_mauvaise_reponse(
        client, apprenant, session_de_quiz):
    """
    Le temps écoulé sans clic est enregistré comme tel.

    Compétence visée : C17 (épreuve E4)

    Confondre les deux ferait compter comme erreur de compréhension ce qui
    n'est qu'un abandon — et le bloc « à revoir » proposerait de réviser une
    notion que l'apprenant n'a peut-être jamais lue.
    """
    client.force_login(apprenant)

    _soumettre(client, session_de_quiz, [1, -1])

    erreur = UserMistake.objects.get(user=apprenant)
    assert erreur.user_answer == "Sans réponse"


@pytest.mark.django_db
def test_la_session_est_close_et_le_score_enregistre(
        client, apprenant, session_de_quiz):
    """
    Une soumission clôt la session et y inscrit le score.

    Compétence visée : C20 (épreuve E5)

    Aucune session n'était close, puisque rien n'appelait cette vue. Une
    session ouverte indéfiniment est indiscernable d'un quiz abandonné.
    """
    client.force_login(apprenant)

    _soumettre(client, session_de_quiz, [1, 2])

    session_de_quiz.refresh_from_db()
    assert session_de_quiz.score == 100.0
    assert session_de_quiz.end_time is not None

    apprenant.refresh_from_db()
    assert apprenant.total_quizzes_completed == 1


@pytest.mark.django_db
def test_le_score_ne_vient_pas_du_navigateur(client, apprenant, session_de_quiz):
    """
    Le serveur corrige d'après les questions qu'il a conservées.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Le corps de la requête n'apporte que les réponses. Un client qui
    annoncerait un score, ou d'autres bonnes réponses, ne serait pas cru —
    ces champs ne sont simplement pas lus.
    """
    client.force_login(apprenant)

    reponse = client.post(
        reverse("quiz:submit"),
        data=json.dumps({
            "session_id": session_de_quiz.id,
            "answers": [0, 0],
            "score": 100,
            "quiz_data": {"questions": [{"correct_answer": 0}, {"correct_answer": 0}]},
        }),
        content_type="application/json",
        secure=True,
    )

    assert reponse.json()["score"] == 0.0
    assert UserMistake.objects.filter(user=apprenant).count() == 2


@pytest.mark.django_db
def test_une_session_sans_questions_ne_produit_pas_de_score(client, apprenant):
    """
    Une session antérieure à la conservation des questions est refusée.

    Compétence visée : C21 (épreuve E5)

    On ne fabrique pas un score à partir de rien. Les quatre sessions ouvertes
    avant le 31/08/2026 ne portent pas leurs questions ; les corriger
    supposerait de deviner ce qui a été demandé.
    """
    client.force_login(apprenant)
    ancienne = LearningSession.objects.create(
        user=apprenant, topic="ancien quiz", activity_type="quiz",
        metadata={"num_questions": 2, "language": "fr"},
    )

    reponse = _soumettre(client, ancienne, [0, 1])

    assert reponse.status_code == 400
    assert reponse.json()["success"] is False
    assert UserMistake.objects.filter(user=apprenant).count() == 0


@pytest.mark.django_db
def test_la_session_d_un_autre_compte_est_inaccessible(
        client, django_user_model, session_de_quiz):
    """
    On ne peut pas enregistrer un résultat sur la session d'autrui.

    Compétence visée : C13 (épreuve E3) — contrôle d'accès

    La session est filtrée sur le compte connecté. Sans ce filtre,
    l'identifiant suffirait à écrire dans le suivi de quelqu'un d'autre.
    """
    autre = django_user_model.objects.create_user(
        username="quelqu_un_d_autre", email="autre@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )
    client.force_login(autre)

    reponse = _soumettre(client, session_de_quiz, [1, 2])

    assert reponse.status_code == 400
    assert UserMistake.objects.filter(user=autre).count() == 0


@pytest.mark.django_db
def test_la_vue_refuse_une_requete_get(client, apprenant):
    """
    L'enregistrement n'est accessible qu'en POST.

    Compétence visée : C13 (épreuve E3)
    """
    client.force_login(apprenant)

    assert client.get(reverse("quiz:submit"), secure=True).status_code == 405
