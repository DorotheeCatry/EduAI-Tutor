"""
Relevé de ce que la base contient réellement, après usage de l'application.

Compétence visée : C20 (épreuve E5) — monitorage et données du suivi
Compétences concernées : C17 (E4) ; C21 (E5) ; C13 (E3)

Pourquoi cette commande existe : au 31/08/2026, la base déployée portait quatre
sessions de quiz **ouvertes et aucune close**. Quatre quiz avaient été
engendrés, aucun n'avait été enregistré — le gabarit ne soumettait pas ses
résultats (incident 010). Vu de l'écran, les quiz avaient pourtant été faits.

**Un quiz fait n'est pas un quiz enregistré, et un exercice ouvert n'est pas un
exercice tenté.** Cette commande dit ce que la base contient, pour qu'on
n'ait pas à le supposer.

Usage :
    uv run python manage.py relever_usage
    uv run python manage.py relever_usage --compte <identifiant>

Sur le serveur, par le tunnel de l'hébergeur ou par `railway ssh`.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q

from apps.agents.agent_watcher import LearningSession, UserMistake
from apps.courses.models import Course
from apps.exercises.models import Exercise, ExerciseSubmission, UserExerciseProgress
from apps.referentiel.models import Competence
from apps.referentiel.progression import progression_par_competence
from apps.referentiel.services import referentiel_actif

Utilisateur = get_user_model()


class Command(BaseCommand):
    """
    Relève l'usage enregistré, globalement puis compte par compte.

    Compétence visée : C20 (épreuve E5)
    """

    help = "Relève ce que la base contient après usage : sessions, exercices, quiz."

    def add_arguments(self, analyseur):
        analyseur.add_argument(
            "--compte", type=str, default=None,
            help="Nom d'utilisateur : détaille la progression de ce seul compte.",
        )

    # --- 1. Ce que la base contient, toutes personnes confondues ---

    def _volumetrie(self):
        """
        Compte les enregistrements, en distinguant ce qui est ABOUTI.

        Compétence visée : C20 (épreuve E5)

        Chaque ligne oppose un total à ce qui compte vraiment. C'est là que se
        lit l'écart entre ce qui a été fait et ce qui a été enregistré : des
        sessions ouvertes sans clôture, des exercices ouverts sans soumission.
        """
        sessions = LearningSession.objects.filter(activity_type="quiz")
        closes = sessions.filter(end_time__isnull=False, score__isnull=False)

        progressions = UserExerciseProgress.objects.all()

        return [
            ("comptes", Utilisateur.objects.count(), None, None),
            ("cours créés", Course.objects.count(), None, None),
            ("exercices engendrés", Exercise.objects.count(),
             "dont rattachés à une compétence",
             Exercise.objects.filter(competence__isnull=False).count()),
            ("exercices ouverts", progressions.count(),
             "dont réussis",
             progressions.filter(is_completed=True).count()),
            ("soumissions de code", ExerciseSubmission.objects.count(),
             "dont réussies",
             ExerciseSubmission.objects.filter(status="success").count()),
            ("sessions de quiz", sessions.count(),
             "dont TERMINÉES", closes.count()),
            ("erreurs de quiz", UserMistake.objects.count(),
             "dont rattachées à une compétence",
             UserMistake.objects.filter(competence__isnull=False).count()),
        ]

    # --- 2. Les écarts qui doivent alerter ---

    def _ecarts(self):
        """
        Rend les constats qui demandent une vérification, ou une liste vide.

        Compétence visée : C21 (épreuve E5)

        Ce ne sont pas des erreurs : ce sont des états dont l'apparence et le
        fait ne coïncident pas nécessairement. La commande les nomme plutôt que
        de laisser lire un total rassurant.
        """
        ecarts = []

        sessions = LearningSession.objects.filter(activity_type="quiz")
        ouvertes = sessions.filter(Q(end_time__isnull=True) | Q(score__isnull=True))
        if ouvertes.exists():
            ecarts.append(
                f"{ouvertes.count()} session(s) de quiz ouverte(s) et jamais close(s) : "
                f"des quiz engendrés dont le résultat n'a pas été enregistré. "
                f"Un quiz qu'on abandonne avant le dernier écran laisse cette trace."
            )

        ouverts_sans_soumission = UserExerciseProgress.objects.filter(
            is_completed=False,
        ).exclude(
            exercise__submissions__user__isnull=False,
        )
        if ouverts_sans_soumission.exists():
            ecarts.append(
                f"{ouverts_sans_soumission.count()} exercice(s) ouvert(s) sans aucune "
                f"soumission : la progression est créée à l'ouverture, pas à la "
                f"première tentative. Ne pas les compter comme de l'activité."
            )

        sans_competence = Exercise.objects.filter(competence__isnull=True).count()
        if sans_competence:
            ecarts.append(
                f"{sans_competence} exercice(s) hors référentiel : ils ne comptent "
                f"dans aucune progression. Attendu pour les sujets libres, les "
                f"exercices issus d'un cours et les replis de génération."
            )

        if referentiel_actif() is None:
            ecarts.append(
                "aucun référentiel actif : la progression ne s'affichera pas. "
                "Charger avec `importer_referentiel … --activer`."
            )

        return ecarts

    # --- 3. Le détail d'un compte ---

    def _detail_du_compte(self, nom):
        utilisateur = Utilisateur.objects.filter(username=nom).first()
        if utilisateur is None:
            self.stdout.write(self.style.ERROR(f"compte introuvable : {nom}"))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Compte « {nom} »"))

        quiz = LearningSession.objects.filter(
            user=utilisateur, activity_type="quiz",
            end_time__isnull=False, score__isnull=False,
        )
        moyenne = quiz.aggregate(m=Avg("score"))["m"]
        self.stdout.write(
            f"  quiz terminés : {quiz.count()}"
            + (f", score moyen {moyenne:.0f} %" if moyenne is not None else "")
        )

        progression = progression_par_competence(utilisateur)
        entamees = [e for e in progression if e["niveau_atteint"] > 0]
        if not entamees:
            self.stdout.write("  aucune compétence entamée")
            return

        for entree in entamees:
            self.stdout.write(
                f"  niveau {entree['niveau_atteint']} — "
                f"{entree['competence'].intitule} "
                f"({entree['exercices_reussis']} réussis, "
                f"{entree['reussis_du_premier_coup']} du premier coup)"
            )

    # --- 4. Point de lancement ---

    def handle(self, *args, **options):
        """
        Affiche le relevé, puis les écarts.

        Compétence visée : C20 (épreuve E5)
        """
        self.stdout.write(self.style.MIGRATE_HEADING("Ce que la base contient"))
        for libelle, total, precision, sous_total in self._volumetrie():
            ligne = f"  {libelle:<28} {total:>5}"
            if precision is not None:
                ligne += f"   {precision} : {sous_total}"
            self.stdout.write(ligne)

        referentiel = referentiel_actif()
        if referentiel:
            competences = Competence.objects.filter(
                module__referentiel=referentiel).count()
            self.stdout.write(
                f"  {'référentiel actif':<28} {referentiel.code} "
                f"({referentiel.modules.count()} modules, {competences} compétences)"
            )

        ecarts = self._ecarts()
        self.stdout.write("")
        if ecarts:
            self.stdout.write(self.style.WARNING("À vérifier"))
            for ecart in ecarts:
                self.stdout.write(f"  · {ecart}")
        else:
            self.stdout.write(self.style.SUCCESS(
                "Aucun écart : tout ce qui a été ouvert a été mené à son terme."
            ))

        if options["compte"]:
            self._detail_du_compte(options["compte"])
        else:
            actifs = (
                Utilisateur.objects
                .annotate(reussis=Count("userexerciseprogress",
                                        filter=Q(userexerciseprogress__is_completed=True)))
                .filter(reussis__gt=0)
            )
            self.stdout.write("")
            if actifs.exists():
                self.stdout.write("Comptes ayant réussi au moins un exercice :")
                for compte in actifs:
                    self.stdout.write(f"  · {compte.username} ({compte.reussis})")
                self.stdout.write(
                    "  Détail : relever_usage --compte <identifiant>"
                )
            else:
                self.stdout.write("Aucun compte n'a encore réussi d'exercice.")
