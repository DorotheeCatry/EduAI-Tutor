"""
Tests du quiz multijoueur : ce qu'une partie écrit en base.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C20 (E5) — données du suivi ; C13 (E3)

Ces tests portent sur l'état de la base à la fin d'une partie, pas sur
l'affichage. Une partie qui se termine sans trace est la panne que le quiz solo
a connue jusqu'au 31/08 (incident 010), et l'affichage n'en disait rien.

Ils partent des URL réelles du sondage HTTP — la seule voie que le navigateur
emprunte depuis la suppression du consumer WebSocket (décision 031).
"""

import json
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.agents.agent_watcher import LearningSession, UserMistake
from apps.quiz.models import (
    DELAI_DE_PRESENCE_SECONDES,
    GameAnswer,
    GameParticipant,
    GameQuestion,
    GameRoom,
)
from apps.quiz.views import cloturer_les_sessions_de_la_partie
from apps.referentiel.models import Competence

FICHIER_LIVRE = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    call_command("importer_referentiel", FICHIER_LIVRE, "--activer", stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def hote(django_user_model):
    return django_user_model.objects.create_user(
        username="hote", email="hote@exemple.test", password="mot-de-passe-d-essai-2026")


@pytest.fixture
def invitee(django_user_model):
    return django_user_model.objects.create_user(
        username="invitee", email="invitee@exemple.test",
        password="mot-de-passe-d-essai-2026")


@pytest.fixture
def salle(hote, referentiel):
    salle = GameRoom.objects.create(
        code="ABC123", host=hote, topic=referentiel.intitule,
        competence=referentiel, num_questions=2, max_players=10,
        status="in_progress", current_question=1,
        question_start_time=timezone.now(),
    )
    GameQuestion.objects.create(
        room=salle, question_number=1,
        question_text="Que rend `len([1, 2, 3])` ?",
        options=["2", "3", "4", "une erreur"], correct_answer=1,
    )
    GameQuestion.objects.create(
        room=salle, question_number=2,
        question_text="Comment ajoute-t-on un élément ?",
        options=["add()", "push()", "append()", "insert()"], correct_answer=2,
    )
    return salle


def _repondre(client, salle, reponse):
    return client.post(
        reverse("quiz:multiplayer_quiz_api", args=[salle.code]),
        data=json.dumps({"answer": reponse}),
        content_type="application/json", secure=True,
    )


# --- L'horodatage serveur ------------------------------------------------


@pytest.mark.django_db
def test_le_temps_de_reponse_vient_du_serveur_et_non_du_navigateur(
        client, hote, salle):
    """
    Le temps annoncé par le client n'est pas lu.

    Compétence visée : C17 (épreuve E4)

    Il l'était : `data.get('response_time', 60)`. N'importe qui pouvait
    annoncer 0,1 seconde depuis une console et rafler le bonus de rapidité. Un
    classement falsifiable en une ligne n'est pas un classement — et l'écart
    portait sur l'équité entre participants, pas seulement sur l'exactitude.
    """
    GameParticipant.objects.create(room=salle, user=hote)
    salle.question_start_time = timezone.now() - timedelta(seconds=12)
    salle.save(update_fields=["question_start_time"])
    client.force_login(hote)

    client.post(
        reverse("quiz:multiplayer_quiz_api", args=[salle.code]),
        data=json.dumps({"answer": 1, "response_time": 0.1}),
        content_type="application/json", secure=True,
    )

    reponse = GameAnswer.objects.get(participant__user=hote)
    assert reponse.response_time >= 11, (
        "le temps mesuré doit être celui du serveur, pas les 0,1 s annoncées"
    )
    assert reponse.response_time <= 60


@pytest.mark.django_db
def test_une_partie_sans_horodatage_ne_donne_pas_le_bonus_maximal(
        client, hote, salle):
    """
    Sans horodatage de départ, le temps retenu est le maximum.

    Compétence visée : C17 (épreuve E4)

    C'est le cas des parties lancées avant ce correctif. Un repli haut plutôt
    que bas : il ne donne aucun point immérité, là où un repli à zéro en
    donnerait le maximum.
    """
    GameParticipant.objects.create(room=salle, user=hote)
    salle.question_start_time = None
    salle.save(update_fields=["question_start_time"])
    client.force_login(hote)

    _repondre(client, salle, 1)

    assert GameAnswer.objects.get(participant__user=hote).response_time == 60.0


# --- Ce qu'une partie laisse dans le parcours ----------------------------


@pytest.mark.django_db
def test_une_mauvaise_reponse_alimente_le_bloc_a_revoir(
        client, invitee, salle, referentiel):
    """
    Une erreur en multijoueur revient dans le parcours du participant.

    Compétence visée : C17 (épreuve E4), C20 (E5)

    Une partie multijoueur n'écrivait RIEN dans le parcours : ni progression —
    c'est voulu, un quiz ne certifie pas une production — ni lacune signalée,
    ce qui l'était moins. Elle se terminait sans que rien n'en subsiste.
    """
    GameParticipant.objects.create(room=salle, user=invitee)
    client.force_login(invitee)

    _repondre(client, salle, 0)

    erreur = UserMistake.objects.get(user=invitee)
    assert erreur.competence == referentiel, (
        "l'erreur doit nommer la compétence, comme le reste de la page"
    )
    assert erreur.topic == referentiel.intitule
    assert erreur.mistake_type == "quiz_multijoueur"
    assert erreur.user_answer == "2"
    assert erreur.correct_answer == "3"


@pytest.mark.django_db
def test_une_bonne_reponse_ne_cree_aucune_erreur(client, invitee, salle):
    """
    Seules les mauvaises réponses alimentent « à revoir ».

    Compétence visée : C17 (épreuve E4)
    """
    GameParticipant.objects.create(room=salle, user=invitee)
    client.force_login(invitee)

    _repondre(client, salle, 1)

    assert UserMistake.objects.filter(user=invitee).count() == 0


@pytest.mark.django_db
def test_une_partie_ne_fait_progresser_aucun_niveau(
        client, invitee, salle, referentiel):
    """
    Le multijoueur ne donne pas de niveau, comme le solo.

    Compétence visée : C17 (épreuve E4)

    Les trois niveaux nomment des actes de production ; un questionnaire mesure
    la reconnaissance. Faire attester une production par une reconnaissance
    n'aurait pas de sens (décision 028), et cela vaut aussi en multijoueur.
    """
    from apps.referentiel.progression import progression_par_competence

    GameParticipant.objects.create(room=salle, user=invitee)
    client.force_login(invitee)
    _repondre(client, salle, 1)

    entree = next(e for e in progression_par_competence(invitee)
                  if e["competence"].code == "collections")
    assert entree["niveau_atteint"] == 0


# --- Présence, départ, retour --------------------------------------------


@pytest.mark.django_db
def test_la_partie_n_attend_pas_un_participant_parti(client, hote, invitee, salle):
    """
    Un joueur qui a fermé son onglet ne bloque plus la partie.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    La partie comptait les participants marqués actifs — un drapeau que rien ne
    remettait à faux sur cette voie. Un joueur qui partait bloquait donc la
    partie pour tous les autres, indéfiniment, en attendant une réponse qui ne
    viendrait jamais.
    """
    GameParticipant.objects.create(room=salle, user=hote,
                                   derniere_activite=timezone.now())
    parti = GameParticipant.objects.create(
        room=salle, user=invitee,
        derniere_activite=timezone.now() - timedelta(
            seconds=DELAI_DE_PRESENCE_SECONDES + 10),
    )
    assert parti.est_present is False

    client.force_login(hote)
    _repondre(client, salle, 1)

    salle.refresh_from_db()
    assert salle.current_question == 2, (
        "la partie doit avancer dès que les PRÉSENTS ont répondu"
    )


@pytest.mark.django_db
def test_un_participant_qui_revient_retrouve_sa_partie(client, invitee, salle):
    """
    Un retour après coupure n'est pas refusé.

    Compétence visée : C17 (épreuve E4)

    La page répondait « vous n'êtes pas autorisé » à sa propre partie, et
    renvoyait au salon. Le retour est la règle, pas l'exception : un onglet
    fermé, un portable en veille, un réseau qui saute.
    """
    participant = GameParticipant.objects.create(
        room=salle, user=invitee, is_active=False)
    client.force_login(invitee)

    reponse = client.get(reverse("quiz:multiplayer_game", args=[salle.code]),
                         secure=True)

    assert reponse.status_code == 200
    participant.refresh_from_db()
    assert participant.is_active is True


@pytest.mark.django_db
def test_le_sondage_tient_lieu_de_battement_de_coeur(client, invitee, salle):
    """
    Interroger l'état de la salle met à jour la présence.

    Compétence visée : C17 (épreuve E4)

    Le sondage a lieu toutes les deux secondes tant que la page est ouverte :
    il n'y a rien à ajouter côté client pour savoir qui est là.
    """
    participant = GameParticipant.objects.create(
        room=salle, user=invitee,
        derniere_activite=timezone.now() - timedelta(minutes=5))
    client.force_login(invitee)

    client.get(reverse("quiz:room_status_api", args=[salle.code]), secure=True)

    participant.refresh_from_db()
    assert participant.est_present is True


# --- Le rattachement au référentiel --------------------------------------


@pytest.mark.django_db
def test_la_creation_d_une_salle_rattache_la_competence_choisie(
        client, hote, referentiel):
    """
    L'hôte choisit une compétence, et la salle la porte.

    Compétence visée : C17 (épreuve E4)

    Même mécanique que le solo et les exercices : un choix explicite, jamais
    une déduction sur le sujet libre.
    """
    client.force_login(hote)

    client.post(reverse("quiz:create_room"),
                {"competence": "collections", "num_questions": 5,
                 "max_players": 10}, secure=True)

    salle = GameRoom.objects.latest("created_at")
    assert salle.competence == referentiel
    assert salle.topic == referentiel.intitule, (
        "le sujet de la partie doit être celui de la compétence choisie"
    )


@pytest.mark.django_db
def test_un_sujet_libre_laisse_la_salle_hors_referentiel(client, hote, referentiel):
    """
    Sans choix, la salle n'est rattachée à rien — et pas « au plus proche ».

    Compétence visée : C17 (épreuve E4)
    """
    client.force_login(hote)

    client.post(reverse("quiz:create_room"),
                {"topic": "un sujet libre", "num_questions": 5,
                 "max_players": 10}, secure=True)

    salle = GameRoom.objects.latest("created_at")
    assert salle.competence is None
    assert salle.topic == "un sujet libre"


@pytest.mark.django_db
def test_le_formulaire_de_salle_propose_les_competences(client, hote, referentiel):
    """
    La page de création affiche le sélecteur.

    Compétence visée : C17 (épreuve E4)

    Sans ce menu, la clé étrangère resterait vide sur toutes les salles : le
    chemin de remplissage passe par cette page et par elle seule.
    """
    client.force_login(hote)

    contenu = client.get(reverse("quiz:create_room"),
                         secure=True).content.decode("utf-8")

    assert 'name="competence"' in contenu
    assert referentiel.intitule in contenu


# --- Le code mort retiré --------------------------------------------------


def test_le_consumer_websocket_n_existe_plus():
    """
    Le serveur WebSocket sans client a été retiré, pas laissé en sommeil.

    Compétence visée : C21 (épreuve E5) — famille C des motifs

    465 lignes qu'aucun client n'appelait, doublant une implémentation par
    sondage qui, elle, fonctionne. Du code jamais exécuté est une invitation à
    croire qu'une fonctionnalité existe (décision 031).
    """
    from pathlib import Path

    assert not Path("apps/quiz/consumers.py").exists()
    assert not Path("apps/quiz/routing.py").exists()

    # Le contrôle porte sur des IDENTIFIANTS de code, non sur la prose : un
    # premier essai découpait la docstring du fichier pour l'en exclure, et
    # échouait sur le commentaire qui explique la suppression. Un test qui
    # analyse un commentaire mesure la rédaction, pas le code.
    asgi = Path("eduai_project/asgi.py").read_text(encoding="utf-8")
    for identifiant in ("URLRouter", "websocket_urlpatterns", "AuthMiddlewareStack"):
        assert identifiant not in asgi, (
            f"« {identifiant} » subsiste : le routage WebSocket est encore déclaré"
        )


# --- La fin de partie appartient au serveur -------------------------------


@pytest.mark.django_db
def test_le_gabarit_n_annonce_pas_la_fin_de_partie_de_lui_meme():
    """
    Le client attend le verdict du serveur après sa dernière réponse.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le gabarit concluait la partie dès sa propre dernière réponse : le joueur
    le plus rapide voyait « partie terminée » pendant que l'autre répondait
    encore, sur un classement figé à un état intermédiaire. Il pouvait donc se
    croire vainqueur sans l'être.
    """
    gabarit = (
        Path("apps/quiz/templates/quiz/multiplayer_game.html")
        .read_text(encoding="utf-8")
    )
    # Les quatre cents caractères qui suivent le test « reste-t-il des
    # questions ? » portent les deux branches. On n'y compte pas les accolades
    # — un découpage qui casse au premier reformatage — on y cherche le nom de
    # ce qui est appelé.
    branchement = gabarit.split(
        "if (currentQuestionNumber < totalQuestions)")[1][:400]

    assert "attendreLaFinDeLaPartie" in branchement, (
        "après la dernière question, le client doit attendre le serveur"
    )
    assert "showFinalResults" not in branchement, (
        "le client ne doit plus prononcer la fin de partie lui-même"
    )
    assert "data.status === 'finished'" in gabarit, (
        "la fin de partie doit être lue sur l'état renvoyé par le serveur"
    )


@pytest.mark.django_db
def test_le_sondage_conclut_une_partie_que_plus_personne_ne_joue(
        client, hote, invitee, salle):
    """
    Une partie se termine même quand plus aucune réponse n'arrive.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    L'arbitrage ne vivait que dans la soumission d'une réponse. Faire attendre
    le joueur qui a fini y aurait introduit un blocage : si le dernier
    participant attendu ferme son navigateur, plus personne ne soumet, donc
    personne ne prononce la fin. Le sondage d'état arbitre à son tour.
    """
    GameParticipant.objects.create(room=salle, user=hote,
                                   derniere_activite=timezone.now())
    parti = GameParticipant.objects.create(
        room=salle, user=invitee,
        derniere_activite=timezone.now() - timedelta(
            seconds=DELAI_DE_PRESENCE_SECONDES + 10),
    )

    salle.current_question = salle.num_questions
    salle.save()
    derniere = GameQuestion.objects.get(room=salle,
                                        question_number=salle.num_questions)
    GameAnswer.objects.create(
        participant=GameParticipant.objects.get(room=salle, user=hote),
        question=derniere, selected_answer=2, response_time=4.0,
    )
    assert parti.est_present is False

    client.force_login(hote)
    reponse = client.get(
        reverse("quiz:room_status_api", args=[salle.code]), secure=True)

    assert reponse.json()["status"] == "finished", (
        "le sondage doit pouvoir conclure la partie sans nouvelle réponse"
    )


# --- Le multijoueur compte comme un quiz terminé --------------------------


@pytest.mark.django_db
def test_une_partie_terminee_laisse_une_session_close_par_joueur(
        client, hote, invitee, salle):
    """
    Chaque participant repart avec une session d'apprentissage close.

    Compétence visée : C20 (épreuve E5), C17 (E4)

    La génération du quiz ouvrait une session pour le seul hôte, que rien ne
    clôturait en multijoueur. La page Référentiel filtre sur `end_time` et
    `score` : elle comptait donc zéro quiz terminé pour des joueurs qui
    venaient d'en finir un, et ignorait entièrement les invités (incident 012).
    """
    GameParticipant.objects.create(room=salle, user=hote,
                                   derniere_activite=timezone.now(),
                                   correct_answers=2)
    GameParticipant.objects.create(room=salle, user=invitee,
                                   derniere_activite=timezone.now(),
                                   correct_answers=1)
    salle.current_question = salle.num_questions
    salle.save()

    client.force_login(hote)
    _repondre(client, salle, 2)
    client.force_login(invitee)
    _repondre(client, salle, 0)

    salle.refresh_from_db()
    assert salle.status == "finished"

    sessions = LearningSession.objects.filter(activity_type="quiz_multijoueur")
    assert sessions.count() == 2, "un joueur sans session est un joueur invisible"
    for session in sessions:
        assert session.end_time is not None
        assert session.score is not None
        assert session.competence == salle.competence, (
            "la session doit nommer la compétence, comme le reste de la page"
        )


@pytest.mark.django_db
def test_la_cloture_des_sessions_ne_double_pas_les_lignes(hote, invitee, salle):
    """
    Deux arbitrages successifs n'écrivent qu'une session par joueur.

    Compétence visée : C20 (épreuve E5)

    Le sondage arbitre toutes les deux secondes et plusieurs clients sondent en
    parallèle : la clôture doit pouvoir être demandée plusieurs fois sans
    gonfler les compteurs.
    """
    GameParticipant.objects.create(room=salle, user=hote, correct_answers=2)
    GameParticipant.objects.create(room=salle, user=invitee, correct_answers=0)

    cloturer_les_sessions_de_la_partie(salle)
    cloturer_les_sessions_de_la_partie(salle)

    assert LearningSession.objects.filter(
        activity_type="quiz_multijoueur").count() == 2


@pytest.mark.django_db
def test_le_score_de_la_session_est_un_pourcentage_et_non_des_points(
        hote, salle):
    """
    La session retient le pourcentage de bonnes réponses, pas les points.

    Compétence visée : C20 (épreuve E5)

    Les points récompensent la vitesse. La page Référentiel affiche une moyenne
    que l'apprenant lira comme une réussite : y verser des points ferait dire à
    ce chiffre autre chose que ce qu'il annonce.
    """
    GameParticipant.objects.create(room=salle, user=hote,
                                   correct_answers=1, score=1730)

    cloturer_les_sessions_de_la_partie(salle)

    session = LearningSession.objects.get(activity_type="quiz_multijoueur")
    assert session.score == 50.0, "1 bonne réponse sur 2 questions"
    assert session.metadata["points"] == 1730, "les points restent, à leur place"


@pytest.mark.django_db
def test_la_page_referentiel_compte_les_parties_multijoueur(client, hote, salle):
    """
    Le compteur « quiz terminés » voit les deux formes de quiz.

    Compétence visée : C20 (épreuve E5), C17 (E4)

    Un compteur qui n'en voit qu'une forme sur deux annonce autre chose que ce
    qu'il mesure — la famille B du registre des motifs.
    """
    GameParticipant.objects.create(room=salle, user=hote, correct_answers=2)
    cloturer_les_sessions_de_la_partie(salle)

    client.force_login(hote)
    page = client.get(reverse("tracker:dashboard"), secure=True)

    assert page.context["quiz_termines"] == 1
    assert page.context["score_moyen"] == 100.0


# --- Le salon d'attente ---------------------------------------------------


@pytest.mark.django_db
def test_le_sondage_annonce_un_joueur_qui_vient_de_rejoindre(
        client, hote, invitee, salle):
    """
    L'arrivée d'un joueur se voit sans recharger la page.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le compteur du salon ne bougeait pas, et le nouveau venu n'apparaissait
    pas : le sondage n'actualisait que du texte, et le visait mal.
    """
    salle.status = "waiting"
    salle.save()
    GameParticipant.objects.create(room=salle, user=hote)
    client.force_login(hote)
    url = reverse("quiz:room_status_api", args=[salle.code])

    avant = client.get(url, secure=True).json()
    assert avant["player_count"] == 1

    GameParticipant.objects.create(room=salle, user=invitee)
    apres = client.get(url, secure=True).json()

    assert apres["player_count"] == 2
    assert [p["username"] for p in apres["participants"]] == ["hote", "invitee"], (
        "le sondage doit nommer les joueurs, pas seulement les compter"
    )


def test_le_salon_ne_designe_pas_son_titre_par_sa_position():
    """
    Le titre des joueurs est atteint par identifiant, jamais par position.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    `document.querySelector('h3')` rend le PREMIER h3 de la page — celui des
    réglages de la partie. Le sondage réécrivait donc « Réglages » toutes les
    deux secondes, pendant que le nombre de joueurs ne bougeait jamais.
    """
    gabarit = (
        Path("apps/quiz/templates/quiz/room_detail.html")
        .read_text(encoding="utf-8")
    )

    # Les lignes de commentaire sont écartées : celle qui décrit le défaut le
    # cite forcément, et un test qui s'y déclenche interdit d'expliquer ce
    # qu'on a corrigé.
    code = [ligne for ligne in gabarit.split("\n")
            if not ligne.strip().startswith("//")]

    assert "querySelector('h3')" not in "\n".join(code), (
        "un sélecteur de balise nue désigne le premier élément venu"
    )
    assert 'id="titre-joueurs"' in gabarit
    assert 'getElementById(\'titre-joueurs\')' in gabarit


def test_le_podium_ne_peut_etre_recouvert_par_aucun_affichage_tardif():
    """
    Rien ne s'affiche par-dessus le podium une fois la partie close.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le podium apparaissait puis disparaissait au bout de deux secondes : le
    sondage du classement prononçait la fin pendant que l'affichage de la
    correction attendait encore son délai, et l'attente venait recouvrir le
    podium — que plus rien ne ramenait, la partie étant déjà marquée finie.
    """
    gabarit = (
        Path("apps/quiz/templates/quiz/multiplayer_game.html")
        .read_text(encoding="utf-8")
    )

    for fonction in ("attendreLaFinDeLaPartie", "showQuestion"):
        debut = gabarit.index("function %s(" % fonction)
        entete = gabarit[debut:debut + 700]
        assert "if (gameFinished)" in entete, (
            "%s doit renoncer si la partie est déjà close" % fonction
        )
