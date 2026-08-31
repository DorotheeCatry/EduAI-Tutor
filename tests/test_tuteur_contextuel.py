"""
Tests du tuteur contextuel : ce qu'il reçoit, et ce qu'il ne recevra jamais.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C10 (E3) ; C9 (E2) — quotas ; C13 (E3)

Le premier test de ce fichier est le plus important du chantier : il échoue si
`correct_answer` réapparaît dans ce qui est transmis au modèle. C'est le genre
de garantie qui se perd à la première refonte, et qu'un test seul retient.
"""

import json
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.chat.actions import ACTIONS_PAR_PAGE, invite_de_l_action
from apps.chat.contexte import (
    BORNES,
    composer_l_invite,
    contexte_de_quiz,
    contexte_d_exercice,
)
from apps.exercises.models import Exercise
from apps.quotas import service as service_quotas
from apps.quotas.models import ConsommationJournaliere

QUESTION = {
    "question": "Que rend `len([1, 2, 3])` ?",
    "options": ["2", "3", "4", "une erreur"],
    "correct_answer": 1,
    "explanation": "La liste porte trois éléments, donc len rend 3.",
}


@pytest.fixture
def apprenant(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante_tuteur", email="tuteur@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )


# --- Le refus qui fonde la décision 029 ---------------------------------


def test_la_bonne_reponse_d_un_quiz_n_est_jamais_transmise():
    """
    `correct_answer` et `explanation` n'entrent pas dans le contexte du tuteur.

    Compétence visée : C10 (épreuve E3)
    Compétences concernées : C17 (E4), C21 (E5)

    Un tuteur qui connaît la réponse attendue transforme un instrument de
    mesure en distributeur de solutions. Toute la progression du produit repose
    sur des résultats mesurés (décision 028) : une seule fuite ici les rendrait
    tous douteux.

    `explanation` est écartée pour la même raison — elle contient l'explication
    de la bonne réponse, donc la bonne réponse.
    """
    contexte = contexte_de_quiz(QUESTION, reponse_donnee="4")

    serialise = json.dumps(contexte, ensure_ascii=False)

    assert "correct_answer" not in serialise
    assert "explanation" not in serialise
    assert "trois éléments" not in serialise, (
        "l'explication de la bonne réponse ne doit pas transiter"
    )
    assert QUESTION["question"] in serialise, "la question, elle, est transmise"
    assert "4" in serialise, "la réponse donnée par l'apprenant est transmise"


def test_l_invite_composee_ne_contient_pas_la_bonne_reponse():
    """
    Le refus tient jusque dans le texte envoyé au modèle.

    Compétence visée : C10 (épreuve E3)

    Vérifier le contexte ne suffit pas : c'est l'invite composée qui part au
    modèle, et c'est elle qu'il faut regarder.
    """
    contexte = contexte_de_quiz(QUESTION, reponse_donnee="2")

    invite = composer_l_invite("Je ne comprends pas la question", contexte)

    assert "correct_answer" not in invite
    assert "trois éléments" not in invite
    assert "Je ne comprends pas la question" in invite


@pytest.mark.django_db
def test_la_page_de_quiz_n_ecrit_pas_la_bonne_reponse_dans_le_contexte_du_tuteur(
        client, apprenant):
    """
    Le contexte écrit dans la page est déjà expurgé, côté serveur.

    Compétence visée : C10 (épreuve E3), C13 (E3)

    L'expurgation ne doit pas dépendre du JavaScript : une refonte de
    l'interface la ferait disparaître sans bruit. Le bloc que la page contient
    ne porte pas la réponse, quoi que fasse le navigateur.
    """
    client.force_login(apprenant)
    with patch("apps.quiz.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.create_quiz.return_value = {
            "questions": [QUESTION], "topic": "les listes", "session_id": 1,
        }
        contenu = client.get(
            reverse("quiz:start") + "?topic=les+listes", secure=True,
        ).content.decode("utf-8")

    bloc = contenu.split('id="contexte-tuteur"')[1].split("</script>")[0]

    assert "questions_sans_reponse" in bloc
    assert "correct_answer" not in bloc
    assert "explanation" not in bloc


# --- Le contexte des autres pages ---------------------------------------


@pytest.mark.django_db
def test_la_page_d_exercice_transmet_l_enonce_et_le_code(client, apprenant):
    """
    Le contexte de l'exercice est écrit par le serveur dans la page.

    Compétence visée : C10 (épreuve E3)

    C'est la parade à la famille C : un panneau qui attendrait un contexte que
    rien ne produit afficherait une bannière vide sans que rien n'échoue. Ce
    test part de la page réelle.
    """
    exercice = Exercise.objects.create(
        title="Parcourir une liste", description="Écrire une fonction.",
        difficulty="beginner", topic="listes", starter_code="", solution="",
        tests=[], created_by=apprenant,
    )
    client.force_login(apprenant)

    contenu = client.get(
        reverse("exercises:detail", args=[exercice.id]), secure=True,
    ).content.decode("utf-8")

    assert 'id="contexte-tuteur"' in contenu
    assert "Parcourir une liste" in contenu


def test_la_solution_de_l_exercice_n_est_pas_transmise():
    """
    Le tuteur ne reçoit pas la solution attendue d'un exercice.

    Compétence visée : C10 (épreuve E3)

    Même raison que pour le quiz : un tuteur qui l'a la donne, et l'exercice
    cesse de mesurer une production.
    """
    class ExerciceFactice:
        title = "Parcourir une liste"
        description = "Écrire une fonction qui parcourt une liste."
        solution = "def parcourir(liste): return list(liste)"

    serialise = json.dumps(contexte_d_exercice(ExerciceFactice()), ensure_ascii=False)

    assert "return list(liste)" not in serialise
    assert "Écrire une fonction" in serialise


def test_le_contexte_est_borne_et_la_troncature_signalee():
    """
    Un contexte trop long est tronqué, et la troncature se voit.

    Compétence visée : C10 (épreuve E3)

    Un cours entier plus un historique saturerait la fenêtre du modèle et se
    paierait à chaque appel. Une coupure silencieuse ferait croire à
    l'apprenant que le tuteur a tout lu.
    """
    class ExerciceFactice:
        title = "Long"
        description = "x" * 5000
        solution = ""

    contexte = contexte_d_exercice(ExerciceFactice(), code_saisi="y" * 5000)

    assert len(contexte["charge"]["enonce"]) <= BORNES["enonce_d_exercice"] + 1
    assert contexte["charge"]["enonce"].endswith("…")
    assert len(contexte["charge"]["code"]) <= BORNES["code_saisi"] + 1


def test_l_historique_transmis_est_borne_a_deux_echanges():
    """
    Seuls les deux derniers échanges accompagnent la question.

    Compétence visée : C10 (épreuve E3)
    """
    historique = [{"question": f"q{n}", "reponse": f"r{n}"} for n in range(5)]

    invite = composer_l_invite("nouvelle question", {}, historique)

    assert "q4" in invite and "q3" in invite
    assert "q2" not in invite
    assert invite.rstrip().endswith("Question : nouvelle question"), (
        "la question de l'apprenant vient en dernier, sinon le contexte la noie"
    )


# --- Les actions préformées ---------------------------------------------


def test_aucune_action_ne_demande_la_solution():
    """
    Aucune invite préformée ne demande au tuteur de résoudre à la place.

    Compétence visée : C10 (épreuve E3)

    Les invites sont rassemblées dans un module pour être relisibles d'un coup ;
    ce test est ce qui rend la relecture inutile.
    """
    for page, actions in ACTIONS_PAR_PAGE.items():
        for action in actions:
            invite = action["invite"].lower()
            if page in ("exercice", "quiz"):
                assert ("ne donne pas" in invite or "n'écris ni" in invite
                        or "ne donne pas la réponse" in invite), (
                    f"l'action « {action['code']} » ne protège pas la solution"
                )


@pytest.mark.django_db
def test_une_action_inconnue_est_refusee(client, apprenant):
    """
    Un code d'action absent du module est refusé, non traité comme une question.

    Compétence visée : C13 (épreuve E3)
    """
    client.force_login(apprenant)

    reponse = client.post(
        reverse("chat:send_message"),
        data=json.dumps({"action": "donne-moi-la-solution"}),
        content_type="application/json", secure=True,
    )

    assert reponse.status_code == 400
    assert invite_de_l_action("donne-moi-la-solution") is None


# --- Quotas et sécurité --------------------------------------------------


@pytest.mark.django_db
def test_une_question_au_tuteur_decompte_le_quota(client, apprenant):
    """
    Le chat dépense, et le compteur le sait.

    Compétence visée : C9 (épreuve E2) — quotas
    Compétence visée : C13 (E3) — maîtrise du coût

    Un chemin de dépense qui échappe au compteur est un budget qui fuit. Le
    vérifier, pas le supposer : c'est la consigne du chantier.
    """
    client.force_login(apprenant)
    avant = service_quotas.etat(apprenant)["consommees"]

    def repondre(invite):
        # Le décompte a lieu dans l'orchestrateur, avant l'appel au modèle :
        # on le rejoue ici pour éprouver le chemin de la vue sans appeler Groq.
        service_quotas.consommer(apprenant)
        return {"success": True, "answer": "réponse"}

    with patch("apps.chat.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.answer_question.side_effect = repondre
        client.post(
            reverse("chat:send_message"),
            data=json.dumps({"message": "une question"}),
            content_type="application/json", secure=True,
        )

    assert service_quotas.etat(apprenant)["consommees"] == avant + 1


@pytest.mark.django_db
def test_le_quota_restant_est_renvoye_avec_la_reponse(client, apprenant):
    """
    Le panneau peut afficher ce qu'il reste : un apprenant ne doit pas
    découvrir la limite en la heurtant.

    Compétence visée : C9 (épreuve E2), C17 (E4)
    """
    client.force_login(apprenant)

    with patch("apps.chat.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.answer_question.return_value = {
            "success": True, "answer": "réponse",
        }
        corps = client.post(
            reverse("chat:send_message"),
            data=json.dumps({"message": "une question"}),
            content_type="application/json", secure=True,
        ).json()

    assert "quota" in corps
    assert corps["quota"]["quota"] == service_quotas.quota_individuel()
    assert "restantes" in corps["quota"]


@pytest.mark.django_db
def test_l_horodatage_est_celui_du_serveur(client, apprenant):
    """
    L'heure d'un message n'est plus « 12:34:56 ».

    Compétence visée : C21 (épreuve E5) — non-régression, réserve 12

    Trois occurrences de cette valeur figuraient en dur : chaque message du
    tuteur portait la même heure, sur tous les comptes.
    """
    client.force_login(apprenant)

    with patch("apps.chat.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.answer_question.return_value = {
            "success": True, "answer": "réponse",
        }
        corps = client.post(
            reverse("chat:send_message"),
            data=json.dumps({"message": "une question"}),
            content_type="application/json", secure=True,
        ).json()

    assert corps["horodatage"] != "12:34:56"
    assert len(corps["horodatage"]) == 5, "format HH:MM attendu"


@pytest.mark.django_db
def test_le_tuteur_refuse_une_requete_get(client, apprenant):
    """
    L'envoi n'est accessible qu'en POST, et la vue ne porte plus `@csrf_exempt`.

    Compétence visée : C13 (épreuve E3)

    Deuxième occurrence du même défaut dans ce projet, après la soumission de
    quiz : un point de terminaison qui dépense sans protection CSRF est
    déclenchable depuis n'importe quelle page tierce ouverte dans le navigateur
    de l'apprenant (réserve 14).
    """
    client.force_login(apprenant)

    assert client.get(reverse("chat:send_message"), secure=True).status_code == 405


@pytest.mark.django_db
def test_le_plafond_individuel_par_defaut_est_de_quinze(monkeypatch, apprenant):
    """
    Le plafond de repli est celui que le service applique sans configuration.

    Compétence visée : C9 (épreuve E2)

    Relevé de 5 à 15 parce que le tuteur est devenu contextuel : une question
    coûte une génération, et trois questions sur un exercice épuisaient un
    plafond de cinq avant qu'aucun cours n'ait été demandé. Un plafond se
    relève parce que ce qu'il mesure a changé, pas parce qu'il gêne
    (décision 030).

    La variable d'environnement est RETIRÉE avant la vérification. Un premier
    essai lisait la valeur effective et échouait sur le poste, où `.env` porte
    encore l'ancien plafond : un test qui dépend de la configuration ambiante
    n'éprouve pas le code, il éprouve la machine — leçon de l'incident 007.
    """
    monkeypatch.delenv("EDUAI_QUOTA_GENERATIONS_PAR_JOUR", raising=False)

    assert service_quotas.QUOTA_INDIVIDUEL_DEFAUT == 15
    assert service_quotas.quota_individuel() == 15
    assert ConsommationJournaliere.objects.filter(utilisateur=apprenant).count() == 0
