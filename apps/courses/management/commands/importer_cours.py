"""
Importe les supports de cours de l'organisme comme cours de référence publiés.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C10 (E3) ; C21 (E5)

Les 41 fichiers markdown de `data/contents/courses/` étaient employés de deux
façons, et **aucune ne les rendait lisibles** :

  1. `prepare_chroma.py` les découpait en 387 fragments dans
     `eduai_knowledge_base` — du contexte pour les agents, pas un cours.
  2. `module_loader` lisait les fichiers d'index JSON, pas les markdown, pour
     remplir une liste déroulante de sujets sur la page de génération.

Aucune page n'affichait leur contenu. La couche `CoursDeReference` existait
depuis la décision 040 et comptait zéro ligne, parce que rien ne l'alimentait.

Cette commande comble ce trou. Elle lit un rattachement **explicite**
(`apps/courses/donnees/rattachement-cours.json`) : un support n'est jamais
rattaché à une compétence par déduction sur son nom de fichier (décision 027).

Idempotente : relancer remplace le cours publié de chaque compétence touchée.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import CoursDeReference
from apps.courses.services import publier_le_cours
from apps.referentiel.models import Competence

RATTACHEMENT = Path("apps/courses/donnees/rattachement-cours.json")


class Command(BaseCommand):
    help = "Publie les supports markdown de l'organisme comme cours de référence."

    def add_arguments(self, parseur):
        parseur.add_argument("--rattachement", default=str(RATTACHEMENT))
        parseur.add_argument("--a-blanc", action="store_true")

    def handle(self, *args, **options):
        carte = json.loads(Path(options["rattachement"]).read_text(encoding="utf-8"))
        repertoire = Path(carte["repertoire"])
        if not repertoire.is_dir():
            raise SystemExit(f"Répertoire des supports introuvable : {repertoire}")

        publies = 0
        for code, entree in carte["rattachements"].items():
            try:
                competence = Competence.objects.get(code=code)
            except Competence.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"compétence « {code} » absente du référentiel — ignorée"))
                continue

            contenu, manquants = self._assembler(repertoire, entree["fichiers"])
            for absent in manquants:
                self.stdout.write(self.style.WARNING(
                    f"  support absent, ignoré : {absent}"))
            if not contenu:
                self.stdout.write(self.style.WARNING(
                    f"  aucun contenu pour « {code} » — non publié"))
                continue

            sections = contenu.count("\n## ")
            if options["a_blanc"]:
                self.stdout.write(
                    f"[à blanc] {code:24} {sections:3} sections, {len(contenu):7} caractères")
                continue

            with transaction.atomic():
                publier_le_cours(competence, contenu, entree["titre"], redige_par=None)
            publies += 1
            self.stdout.write(self.style.SUCCESS(
                f"publié   {code:24} {sections:3} sections, {len(contenu):7} caractères"))

        if not options["a_blanc"]:
            actifs = CoursDeReference.objects.filter(remplace_le__isnull=True).count()
            self.stdout.write(f"\n{publies} cours publiés — {actifs} cours actifs.")

    @staticmethod
    def _assembler(repertoire: Path, fichiers: list[str]) -> tuple[str, list[str]]:
        """
        Assemble plusieurs supports en un cours, chacun devenant une section.

        Compétence visée : C17 (épreuve E4)

        Choix : un seul cours par compétence, dont chaque support devient une
        section de niveau 2. Motivation : le modèle n'admet qu'un cours publié
        actif par compétence, et c'est voulu — l'apprenant lit *le* cours de la
        compétence, pas une liste de quinze documents entre lesquels choisir.

        Choix : le titre de premier niveau de chaque support est ramené au
        niveau 2. Motivation : une page ne porte qu'un `h1`, et c'est le titre
        du cours. Empiler quinze `h1` casserait la hiérarchie des titres, dont
        les technologies d'assistance se servent pour naviguer.
        """
        morceaux: list[str] = []
        manquants: list[str] = []
        for nom in fichiers:
            chemin = repertoire / nom
            if not chemin.is_file():
                manquants.append(nom)
                continue
            texte = chemin.read_text(encoding="utf-8").strip()
            lignes = [("#" + ligne) if ligne.startswith("# ") else ligne
                      for ligne in texte.split("\n")]
            morceaux.append("\n".join(lignes))
        return "\n\n".join(morceaux), manquants
