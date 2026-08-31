"""
Tests de la règle de progression par compétences.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C4 (E1)

La règle tient en trois phrases ; ces tests en vérifient chacune, ainsi que ce
qu'elle refuse de mesurer. Les cas négatifs comptent autant que les positifs :
un quiz qui ferait progresser un niveau, ou un exercice hors référentiel qui
compterait, seraient des progressions fausses et muettes.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.agents.agent_watcher import LearningSession
from apps.exercises.models import Exercise, ExerciseSubmission, UserExerciseProgress
from apps.referentiel.models import Competence
from apps.referentiel.progression import (
    ATTEINT,
    NON_ATTEINT,
    NON_MESURE,
    SEUIL_NIVEAU_ADAPTER,
    progression_par_competence,
    resume_par_module,
)

FICHIER_LIVRE = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    call_command("importer_referentiel", FICHIER_LIVRE, "--activer", stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenant(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante_progression",
        email="progression@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )


def _exercice(apprenant, competence, titre):
    return Exercise.objects.create(
        title=titre, description="…", difficulty="beginner",
        topic=titre, starter_code="", solution="", tests=[],
        created_by=apprenant, competence=competence,
    )


def _reussir(apprenant, exercice, tentatives_avant=0):
    """
    Simule une réussite après un nombre d'échecs donné.

    Compétence visée : C18 (épreuve E4)

    Les soumissions sont créées dans l'ordre, puis la progression close comme
    la vue le fait : c'est l'état que la règle lira.
    """
    for _ in range(tentatives_avant):
        ExerciseSubmission.objects.create(
            exercise=exercice, user=apprenant, submitted_code="", status="failed",
        )
    reussie = ExerciseSubmission.objects.create(
        exercise=exercice, user=apprenant, submitted_code="", status="success",
    )
    UserExerciseProgress.objects.update_or_create(
        user=apprenant, exercise=exercice,
        defaults={"is_completed": True, "completed_at": timezone.now(),
                  "best_submission": reussie,
                  "attempts_count": tentatives_avant + 1},
    )
    return reussie


def _entree(apprenant, code="collections"):
    for entree in progression_par_competence(apprenant):
        if entree["competence"].code == code:
            return entree
    raise AssertionError(f"compétence {code} absente de la progression")


@pytest.mark.django_db
def test_sans_exercice_reussi_aucun_niveau_n_est_atteint(apprenant, referentiel):
    """
    Une compétence non travaillée n'est à aucun niveau.

    Compétence visée : C17 (épreuve E4)
    """
    entree = _entree(apprenant)

    assert entree["niveau_atteint"] == 0
    assert entree["etats"][1] == NON_ATTEINT
    assert entree["restant_avant_niveau_2"] == SEUIL_NIVEAU_ADAPTER


@pytest.mark.django_db
def test_un_exercice_reussi_donne_le_niveau_1(apprenant, referentiel):
    """
    Niveau 1 — imiter : un exercice rattaché à la compétence a été réussi.

    Compétence visée : C17 (épreuve E4)
    """
    _reussir(apprenant, _exercice(apprenant, referentiel, "listes 1"))

    entree = _entree(apprenant)
    assert entree["niveau_atteint"] == 1
    assert entree["etats"][1] == ATTEINT
    assert entree["etats"][2] == NON_ATTEINT


@pytest.mark.django_db
def test_trois_exercices_distincts_donnent_le_niveau_2(apprenant, referentiel):
    """
    Niveau 2 — adapter : trois exercices DISTINCTS réussis.

    Compétence visée : C17 (épreuve E4)
    """
    for numero in range(SEUIL_NIVEAU_ADAPTER):
        _reussir(apprenant, _exercice(apprenant, referentiel, f"listes {numero}"))

    entree = _entree(apprenant)
    assert entree["exercices_reussis"] == SEUIL_NIVEAU_ADAPTER
    assert entree["niveau_atteint"] == 2
    assert entree["etats"][2] == ATTEINT


@pytest.mark.django_db
def test_resoumettre_le_meme_exercice_ne_fait_pas_progresser(apprenant, referentiel):
    """
    Trois réussites sur le MÊME exercice valent une seule.

    Compétence visée : C17 (épreuve E4), C4 (E1)

    Le décompte porte sur des exercices distincts. Compter les soumissions
    réussies laisserait atteindre le niveau 2 en renvoyant trois fois la même
    solution.
    """
    exercice = _exercice(apprenant, referentiel, "toujours le même")
    for _ in range(5):
        ExerciseSubmission.objects.create(
            exercise=exercice, user=apprenant, submitted_code="", status="success",
        )
    UserExerciseProgress.objects.update_or_create(
        user=apprenant, exercise=exercice,
        defaults={"is_completed": True, "completed_at": timezone.now()},
    )

    assert _entree(apprenant)["niveau_atteint"] == 1


@pytest.mark.django_db
def test_le_niveau_3_est_non_mesure_et_jamais_atteint(apprenant, referentiel):
    """
    Niveau 3 — transposer : non mesuré, quel que soit le nombre de réussites.

    Compétence visée : C17 (épreuve E4)

    « Transposer » suppose un contexte non rencontré, et rien dans les données
    n'établit qu'un énoncé engendré à partir du même libellé de compétence en
    constitue un. Un seuil plus élevé mesurerait la même preuve en plus grand
    nombre : ce serait mettre un mot fort sur un compteur.
    """
    for numero in range(10):
        _reussir(apprenant, _exercice(apprenant, referentiel, f"listes {numero}"))

    entree = _entree(apprenant)
    assert entree["etats"][3] == NON_MESURE
    assert entree["etats"][3] != NON_ATTEINT, (
        "« non mesuré » et « non atteint » sont deux états distincts"
    )
    assert entree["niveau_atteint"] == 2, "aucun cumul ne fait atteindre le niveau 3"


@pytest.mark.django_db
def test_un_exercice_reussi_a_la_douzieme_tentative_compte(apprenant, referentiel):
    """
    Le nombre de tentatives n'entre pas dans la règle de progression.

    Compétence visée : C17 (épreuve E4)

    Ce que les niveaux mesurent est « sait produire », pas « sait produire
    vite ». Exiger la réussite immédiate punirait l'apprentissage par essais.
    """
    _reussir(apprenant, _exercice(apprenant, referentiel, "après 11 échecs"),
             tentatives_avant=11)

    entree = _entree(apprenant)
    assert entree["niveau_atteint"] == 1
    assert entree["reussis_du_premier_coup"] == 0, (
        "…mais il ne compte pas comme une réussite du premier coup"
    )


@pytest.mark.django_db
def test_la_reussite_du_premier_coup_est_comptee_sans_donner_de_niveau(
        apprenant, referentiel):
    """
    L'indicateur de premier essai informe, il ne certifie pas.

    Compétence visée : C17 (épreuve E4)
    """
    _reussir(apprenant, _exercice(apprenant, referentiel, "du premier coup"))
    _reussir(apprenant, _exercice(apprenant, referentiel, "au bout de trois"),
             tentatives_avant=2)

    entree = _entree(apprenant)
    assert entree["exercices_reussis"] == 2
    assert entree["reussis_du_premier_coup"] == 1
    assert entree["niveau_atteint"] == 1, "deux réussites ne font pas le niveau 2"


@pytest.mark.django_db
def test_un_exercice_hors_referentiel_ne_compte_pour_aucune_competence(
        apprenant, referentiel):
    """
    Un exercice non rattaché ne fait progresser personne.

    Compétence visée : C17 (épreuve E4)

    C'est ce que l'interface annonce — « hors référentiel, ne compte pas dans
    la progression » — et ce test est ce qui rend l'annonce vraie.
    """
    _reussir(apprenant, _exercice(apprenant, None, "sujet libre"))

    assert all(entree["niveau_atteint"] == 0
               for entree in progression_par_competence(apprenant))


@pytest.mark.django_db
def test_un_quiz_ne_fait_progresser_aucun_niveau(apprenant, referentiel):
    """
    Les quiz sont exclus de la progression, même rattachés à une compétence.

    Compétence visée : C17 (épreuve E4)

    Les trois niveaux nomment des actes de production ; un questionnaire mesure
    la reconnaissance. Faire attester une production par une reconnaissance
    n'aurait pas de sens.
    """
    for numero in range(5):
        LearningSession.objects.create(
            user=apprenant, topic=referentiel.intitule, activity_type="quiz",
            score=100.0, competence=referentiel,
            metadata={"questions": [], "num_questions": 0},
        )

    assert _entree(apprenant)["niveau_atteint"] == 0


@pytest.mark.django_db
def test_l_exercice_d_un_autre_apprenant_ne_compte_pas(
        apprenant, referentiel, django_user_model):
    """
    La progression est celle du compte, pas celle de l'exercice.

    Compétence visée : C17 (épreuve E4), C13 (E3)
    """
    autre = django_user_model.objects.create_user(
        username="quelqu_un_d_autre", email="autre2@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )
    exercice = _exercice(autre, referentiel, "réussi par une autre personne")
    _reussir(autre, exercice)

    assert _entree(apprenant)["niveau_atteint"] == 0
    assert _entree(autre)["niveau_atteint"] == 1


@pytest.mark.django_db
def test_le_resume_par_module_compte_les_niveaux_de_facon_cumulative(
        apprenant, referentiel):
    """
    Une compétence au niveau 2 compte aussi dans le niveau 1.

    Compétence visée : C17 (épreuve E4)

    Des paliers exclusifs feraient « disparaître » une compétence du niveau 1
    le jour où elle progresse, ce qu'un apprenant lirait comme une régression.
    """
    for numero in range(SEUIL_NIVEAU_ADAPTER):
        _reussir(apprenant, _exercice(apprenant, referentiel, f"listes {numero}"))
    autre_competence = Competence.objects.get(code="fonctions")
    _reussir(apprenant, _exercice(apprenant, autre_competence, "une fonction"))

    python = next(ligne for ligne in resume_par_module(apprenant)
                  if ligne["module"].code == "python")

    assert python["au_niveau_1"] == 2
    assert python["au_niveau_2"] == 1
    assert python["competences"] == 7


@pytest.mark.django_db
def test_sans_referentiel_actif_la_progression_est_vide_et_ne_leve_pas(apprenant):
    """
    Aucun référentiel actif ne fait pas tomber la page.

    Compétence visée : C17 (épreuve E4)

    Une application dont l'accueil échoue parce qu'un exploitant a oublié
    `--activer` serait fragile pour une raison administrative.
    """
    assert progression_par_competence(apprenant) == []
    assert resume_par_module(apprenant) == []
