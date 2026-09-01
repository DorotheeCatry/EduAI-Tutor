"""
Enregistre les sessions d'apprentissage des parties déjà terminées.

Compétence visée : C20 (épreuve E5) — données du suivi
Compétences concernées : C17 (E4) ; C21 (E5)

Les parties multijoueur achevées avant la correction de l'incident 012 n'ont
laissé aucune session close : la page Référentiel les comptait pour zéro. Cette
commande rattrape ces parties à partir de ce que la base contient déjà —
bonnes réponses, points, horodatages. Elle ne fabrique aucune donnée : elle
tire les conséquences d'un événement réellement enregistré.

Idempotente : une partie déjà clôturée est ignorée.
"""

from django.core.management.base import BaseCommand

from apps.quiz.models import GameRoom
from apps.quiz.views import cloturer_les_sessions_de_la_partie


class Command(BaseCommand):
    help = "Crée les sessions d'apprentissage manquantes des parties terminées."

    def add_arguments(self, parseur):
        parseur.add_argument(
            "--a-blanc", action="store_true",
            help="Montre les parties concernées sans rien écrire.",
        )

    def handle(self, *args, **options):
        parties = GameRoom.objects.filter(status="finished").order_by("created_at")
        if not parties:
            self.stdout.write("Aucune partie terminée.")
            return

        for partie in parties:
            joueurs = partie.participants.count()
            ligne = f"{partie.code} — {partie.topic} — {joueurs} joueur(s)"
            if options["a_blanc"]:
                self.stdout.write(f"[à blanc] {ligne}")
                continue
            cloturer_les_sessions_de_la_partie(partie)
            self.stdout.write(self.style.SUCCESS(f"clôturée : {ligne}"))
