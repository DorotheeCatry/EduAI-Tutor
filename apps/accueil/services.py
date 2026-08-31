"""
Ce que la page d'accueil a besoin de savoir, et rien de plus.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — requêtes ; C20 (E5)

Chaque fonction répond à un bloc de la page, et rend une structure vide plutôt
que `None` quand il n'y a rien à montrer : c'est l'affichage qui décide de
l'état vide, pas la donnée qui décide de tomber.

**Aucune valeur n'est fabriquée ici.** Ce module ne calcule que ce qui est
mesuré. Si une information n'existe pas, il rend zéro ou rien, et la page
l'affiche comme telle — c'est ce qui distingue ce chantier du tableau de bord
qu'il remplace, où un taux de réussite était déduit de l'expérience gagnée
(incident 011).
"""

from django.db.models import Count, Max, OuterRef, Q, Subquery

from apps.agents.agent_watcher import LearningSession, UserMistake
from apps.courses.models import Course
from apps.exercises.models import ExerciseSubmission, UserExerciseProgress
from apps.referentiel.progression import (
    SEUIL_NIVEAU_ADAPTER,
    progression_par_competence,
)

#: Nombre de notions proposées dans le bloc « à revoir ».
#:
#: Cinq : au-delà, le bloc cesse d'orienter et devient une liste à trier, ce
#: qui est le travail qu'on prétend épargner à l'apprenant.
NOTIONS_A_REVOIR = 5


def prochaine_competence(utilisateur):
    """
    Rend la compétence à travailler ensuite, ou `None` si tout est au niveau 2.

    Compétence visée : C17 (épreuve E4)

    Choix : la première compétence jamais travaillée, dans l'ordre du
    référentiel ; à défaut, la première qui n'est pas au niveau 2. Motivation :
    une seule action proposée, donc une seule règle pour la choisir. Proposer
    « la plus proche du niveau suivant » supposerait une notion de proximité que
    la règle de progression n'a pas, et qu'il faudrait inventer.

    Rend aussi le nombre d'exercices restants avant le palier suivant, pour que
    le bouton puisse dire ce qu'il fera plutôt que d'inviter dans le vide.
    """
    progression = progression_par_competence(utilisateur)
    if not progression:
        return None

    jamais_travaillee = next(
        (entree for entree in progression if entree["niveau_atteint"] == 0), None)
    if jamais_travaillee:
        return jamais_travaillee

    en_cours = next(
        (entree for entree in progression if entree["niveau_atteint"] < 2), None)
    return en_cours


def notions_a_revoir(utilisateur, limite=NOTIONS_A_REVOIR):
    """
    Rend les notions qui ont résisté, la plus résistante en tête.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C4 (E1)

    **Critère : le nombre de tentatives avant la réussite.** C'est un signal de
    difficulté réelle, là où l'ancienneté n'est qu'une hypothèse sur l'oubli :
    un exercice réussi du premier coup il y a un mois est probablement encore
    acquis ; un exercice réussi à la cinquième tentative la semaine dernière ne
    l'est pas.

    Choix : les tentatives sont comptées sur les SOUMISSIONS antérieures à la
    réussite, et non lues dans `UserExerciseProgress.attempts_count`.
    Motivation : ce compteur s'incrémente à chaque soumission, y compris après
    la réussite — il compte les soumissions, pas les tentatives avant réussite,
    et son nom laisse croire l'inverse (incident 011). L'employer classerait
    comme difficile un exercice réussi immédiatement puis retravaillé par
    curiosité.
    """
    tentatives = (
        ExerciseSubmission.objects
        .filter(user=OuterRef("user"), exercise=OuterRef("exercise"),
                submitted_at__lte=OuterRef("completed_at"))
        .values("exercise")
        .annotate(nombre=Count("id"))
        .values("nombre")[:1]
    )

    resistants = (
        UserExerciseProgress.objects
        .filter(user=utilisateur, is_completed=True, completed_at__isnull=False)
        .select_related("exercise", "exercise__competence",
                        "exercise__competence__module")
        .annotate(tentatives_avant_reussite=Subquery(tentatives))
        .filter(tentatives_avant_reussite__gt=1)
        .order_by("-tentatives_avant_reussite", "-completed_at")[:limite]
    )

    return [
        {
            "exercice": progression.exercise,
            "competence": progression.exercise.competence,
            "tentatives": progression.tentatives_avant_reussite,
            "dernier_passage": progression.completed_at,
        }
        for progression in resistants
    ]


def erreurs_de_quiz(utilisateur, limite=NOTIONS_A_REVOIR):
    """
    Rend les notions sur lesquelles des questions de quiz ont été manquées.

    Compétence visée : C17 (épreuve E4)

    Seconde source du bloc « à revoir », et la seule dont il dispose tant
    qu'aucun exercice n'a été réussi laborieusement. Un quiz ne fait progresser
    aucun niveau (décision 028) : il signale, il ne certifie pas.

    Le regroupement se fait par compétence quand elle est renseignée, par sujet
    sinon — un quiz lancé sur un sujet libre reste exploitable, il nomme
    simplement sa notion autrement.
    """
    lignes = (
        UserMistake.objects
        .filter(user=utilisateur)
        .values("competence_id", "competence__intitule", "topic")
        .annotate(erreurs=Count("id"), derniere=Max("timestamp"))
        .order_by("-erreurs", "-derniere")[:limite]
    )

    return [
        {
            "intitule": ligne["competence__intitule"] or ligne["topic"],
            "rattachee": bool(ligne["competence_id"]),
            "erreurs": ligne["erreurs"],
            "dernier_passage": ligne["derniere"],
        }
        for ligne in lignes
    ]


def derniere_activite(utilisateur):
    """
    Rend le dernier exercice et le dernier quiz, avec leur résultat.

    Compétence visée : C17 (épreuve E4)

    Choix : le dernier quiz TERMINÉ, c'est-à-dire dont la session est close.
    Motivation : une session ouverte est un quiz engendré, pas un quiz fait —
    la base déployée en portait quatre au 31/08, et les compter comme de
    l'activité aurait affiché un travail qui n'a pas eu lieu (incident 010).
    """
    dernier_exercice = (
        UserExerciseProgress.objects
        .filter(user=utilisateur)
        .filter(Q(is_completed=True) | Q(attempts_count__gt=0))
        .select_related("exercise", "exercise__competence")
        .order_by("-completed_at", "-first_attempt_at")
        .first()
    )

    dernier_quiz = (
        LearningSession.objects
        .filter(user=utilisateur, activity_type="quiz",
                end_time__isnull=False, score__isnull=False)
        .select_related("competence")
        .order_by("-end_time")
        .first()
    )

    cours_en_cours = (
        Course.objects
        .filter(created_by=utilisateur)
        .order_by("-created_at")
        .first()
    )

    return {
        "exercice": dernier_exercice,
        "quiz": dernier_quiz,
        "cours": cours_en_cours,
    }


def resume_de_l_accueil(utilisateur):
    """
    Rassemble ce que les quatre blocs affichent.

    Compétence visée : C17 (épreuve E4)

    Une seule fonction appelée par la vue, pour que l'ordre des blocs de la
    page et l'ordre des données ne puissent pas diverger.
    """
    from apps.referentiel.progression import resume_par_module
    from apps.referentiel.services import referentiel_actif

    modules = resume_par_module(utilisateur)
    entames = [ligne for ligne in modules if ligne["au_niveau_1"]]

    return {
        "referentiel": referentiel_actif(),
        "modules": modules,
        # De quoi replier l'affichage quand rien n'est entamé : le bloc
        # occupait la moitié de l'écran pour dire qu'il n'y avait rien.
        "competences_entamees": bool(entames),
        "modules_non_entames": len(modules) - len(entames),
        "total_competences": sum(ligne["competences"] for ligne in modules),
        "premier_module": modules[0]["module"] if modules else None,
        "prochaine": prochaine_competence(utilisateur),
        "seuil_niveau_2": SEUIL_NIVEAU_ADAPTER,
        "a_revoir": notions_a_revoir(utilisateur),
        "erreurs_de_quiz": erreurs_de_quiz(utilisateur),
        "activite": derniere_activite(utilisateur),
    }
