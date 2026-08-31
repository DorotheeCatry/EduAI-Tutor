from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.agents.agent_orchestrator import get_orchestrator
from apps.agents.agent_watcher import get_watcher_agent
from apps.courses.models import Course
from django.db.models import Avg, Count
from datetime import datetime, timedelta

@login_required
def dashboard(request):
    """
    Page Performance : le rétrospectif, et rien d'inventé.

    Compétence visée : C17 (épreuve E4) — application web
    Compétences concernées : C20 (E5) ; C21 (E5)

    Cette vue fabriquait ses chiffres. Le temps d'étude était déduit du nombre
    de cours — « ~25 min par cours » —, le taux de réussite calculé sur
    l'expérience gagnée (`60 + xp // 50`), la semaine d'activité dérivée de ce
    temps simulé, et la liste des sujets complétée par trois exemples inventés
    quand l'apprenant n'en avait pas assez : « Python Basics 85 % » s'affichait
    sur un compte à zéro cours (incident 011).

    Ce qui reste ici est mesuré, et ce qui ne l'est pas est **annoncé comme non
    mesuré** plutôt que simulé. C'est le même traitement que le niveau 3 du
    référentiel : une donnée absente qui se dit vaut mieux qu'une donnée
    plausible qui ment.
    """
    from apps.agents.agent_watcher import LearningSession
    from apps.exercises.models import UserExerciseProgress
    from apps.referentiel.progression import progression_par_competence

    utilisateur = request.user

    quiz_termines = LearningSession.objects.filter(
        user=utilisateur, activity_type="quiz",
        end_time__isnull=False, score__isnull=False,
    )
    score_moyen = quiz_termines.aggregate(moyenne=Avg("score"))["moyenne"]

    context = {
        "user": utilisateur,
        # Mesuré : ce que la base contient.
        "cours_crees": Course.objects.filter(created_by=utilisateur).count(),
        "exercices_reussis": UserExerciseProgress.objects.filter(
            user=utilisateur, is_completed=True).count(),
        "quiz_termines": quiz_termines.count(),
        "score_moyen": score_moyen,
        "progression": progression_par_competence(utilisateur),
        # Non mesuré : le champ `total_study_time_minutes` existe et n'est
        # écrit par aucun code du projet. L'afficher reviendrait à montrer un
        # zéro permanent ; le simuler, à mentir. Il est donc annoncé comme non
        # mesuré, et la raison tient en une phrase à l'écran.
        "temps_d_etude_mesure": False,
    }

    return render(request, 'tracker/dashboard.html', context)
