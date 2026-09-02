"""
Publie les supports de l'organisme comme cours de référence.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C10 (E3) ; C21 (E5)

Les supports markdown de `data/contents/courses/` servaient de contexte au RAG
et remplissaient une liste déroulante de sujets. **Aucune page n'affichait leur
contenu** : `CoursDeReference` comptait zéro ligne, la couche existait sans que
rien ne l'alimente.

Deux règles gouvernent cet import.

**1. L'index et le disque doivent concorder, sans quoi l'import échoue.**
Un fichier présent sur le disque et absent de l'index disparaîtrait en silence
— c'est ce qui serait arrivé à `dictionaries.md`, du contenu central. Un fichier
d'index absent du disque échoue aussi. Et l'échec **nomme tous les écarts d'un
coup** : les corriger un par un demanderait autant de lancements que d'erreurs.

**2. Le rattachement est choisi, jamais déduit** (décision 027). Il vit dans
`apps/courses/donnees/rattachement-cours.json`, au niveau du sous-module, avec
des exceptions au fichier — chacune motivée par écrit. Une exception couvre un
cas où le sous-module ne décide pas ; une erreur de classement se corrige dans
l'index.

Idempotente : relancer remplace le cours actif de chaque compétence touchée.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import CoursDeReference
from apps.courses.services import publier_le_cours
from apps.referentiel.models import Competence

RATTACHEMENT = Path("apps/courses/donnees/rattachement-cours.json")


class EcartDeCorpus(Exception):
    """L'index et le disque ne décrivent pas le même corpus."""


class Command(BaseCommand):
    help = "Publie les supports markdown de l'organisme comme cours de référence."

    def add_arguments(self, parseur):
        parseur.add_argument("--rattachement", default=str(RATTACHEMENT))
        parseur.add_argument("--a-blanc", action="store_true")

    def handle(self, *args, **options):
        carte = json.loads(Path(options["rattachement"]).read_text(encoding="utf-8"))
        index = json.loads(Path(carte["index"]).read_text(encoding="utf-8"))
        repertoire = Path(carte["repertoire"])

        try:
            self._verifier_la_concordance(index, repertoire, carte)
        except EcartDeCorpus as ecart:
            raise SystemExit(str(ecart)) from ecart

        parties_par_competence = self._repartir(index, repertoire, carte)
        self._publier(parties_par_competence, carte, options["a_blanc"])

    # --- 1. La concordance, avant toute chose ------------------------------

    def _verifier_la_concordance(self, index, repertoire: Path, carte) -> None:
        """
        Exige que l'index et le disque décrivent le même corpus.

        Compétence visée : C21 (épreuve E5)

        Choix : rassembler tous les écarts avant de lever. Motivation : lever au
        premier obligerait à relancer autant de fois qu'il y a d'écarts, en n'en
        voyant qu'un à chaque tour. Un rapport complet se corrige en une passe.
        """
        if not repertoire.is_dir():
            raise EcartDeCorpus(f"Répertoire des supports introuvable : {repertoire}")

        indexes = {f for fichiers in index.values() for f in fichiers}
        # Tous les fichiers, pas seulement les markdown : la concordance porte
        # sur le corpus tel que l'index le décrit, non sur ce que l'import sait
        # lire. `1-introduction.ipynb` est déclaré et présent ; le compter
        # absent parce qu'il n'est pas importable serait un faux écart.
        sur_disque = {p.name for p in repertoire.iterdir() if p.is_file()}

        absents_du_disque = sorted(indexes - sur_disque)
        absents_de_l_index = sorted(sur_disque - indexes)
        exceptions_orphelines = sorted(
            set(carte.get("exceptions", {})) - indexes)

        if not (absents_du_disque or absents_de_l_index or exceptions_orphelines):
            return

        lignes = ["L'index du corpus et le disque ne concordent pas. "
                  "Aucun cours n'a été publié.", ""]
        if absents_du_disque:
            lignes.append("  Déclarés dans l'index, absents du disque :")
            lignes += [f"    - {f}" for f in absents_du_disque]
        if absents_de_l_index:
            lignes.append("  Présents sur le disque, absents de l'index "
                          "— ils disparaîtraient en silence :")
            lignes += [f"    - {f}" for f in absents_de_l_index]
        if exceptions_orphelines:
            lignes.append("  Exceptions de rattachement visant un fichier "
                          "inconnu de l'index :")
            lignes += [f"    - {f}" for f in exceptions_orphelines]
        lignes += ["", f"  Index      : {carte['index']}",
                   f"  Répertoire : {repertoire}"]
        raise EcartDeCorpus("\n".join(lignes))

    # --- 2. Répartition des fichiers par compétence ------------------------

    def _repartir(self, index, repertoire: Path, carte) -> dict:
        """
        Range chaque fichier sous la compétence que la carte lui désigne.

        Compétence visée : C17 (épreuve E4)
        """
        exceptions = carte.get("exceptions", {})
        hors_parcours = carte.get("hors_parcours", {})
        par_competence: dict[str, list[dict]] = {}

        for sous_module, fichiers in sorted(index.items()):
            if sous_module in hors_parcours:
                continue
            entree = carte["sous_modules"].get(sous_module)
            for nom in fichiers:
                exception = exceptions.get(nom)
                code = exception["competence"] if exception else (
                    entree["competence"] if entree else None)
                if code is None:
                    self.stdout.write(self.style.WARNING(
                        f"  sous-module « {sous_module} » sans rattachement "
                        f"ni exception — {nom} ignoré"))
                    continue
                titre, contenu = self._lire(repertoire / nom)
                par_competence.setdefault(code, []).append({
                    "titre": titre, "contenu": contenu,
                    "fichier_source": nom, "sous_module": sous_module,
                })
        return par_competence

    @staticmethod
    def _lire(chemin: Path) -> tuple[str, str]:
        """
        Rend le titre et le corps d'un support.

        Compétence visée : C17 (épreuve E4)
        Choix : le titre est le premier `# ` du fichier, retiré du corps.
        Motivation : il devient le titre de la partie, donc une entrée du
        sommaire ; le laisser dans le contenu le ferait apparaître deux fois.
        """
        texte = chemin.read_text(encoding="utf-8").strip()
        lignes = texte.split("\n")
        titre = chemin.stem.replace("-", " ").capitalize()
        for rang, ligne in enumerate(lignes):
            if ligne.startswith("# "):
                titre = ligne[2:].strip()
                lignes = lignes[:rang] + lignes[rang + 1:]
                break
        return titre, "\n".join(lignes).strip()

    # --- 3. Publication ----------------------------------------------------

    def _publier(self, par_competence: dict, carte, a_blanc: bool) -> None:
        """Publie un cours par compétence, avec ses parties dans l'ordre."""
        titres = {e["competence"]: e["titre"] for e in carte["sous_modules"].values()}
        publies = 0

        for code, parties in sorted(par_competence.items()):
            try:
                competence = Competence.objects.get(code=code)
            except Competence.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"compétence « {code} » absente du référentiel — ignorée"))
                continue

            titre = titres.get(code, competence.intitule)
            caracteres = sum(len(p["contenu"]) for p in parties)
            if a_blanc:
                self.stdout.write(
                    f"[à blanc] {code:24} {len(parties):2} parties, {caracteres:7} caractères")
                continue

            with transaction.atomic():
                publier_le_cours(competence, parties, titre, redige_par=None)
            publies += 1
            self.stdout.write(self.style.SUCCESS(
                f"publié   {code:24} {len(parties):2} parties, {caracteres:7} caractères"))

        if not a_blanc:
            actifs = CoursDeReference.objects.filter(remplace_le__isnull=True).count()
            self.stdout.write(f"\n{publies} cours publiés — {actifs} cours actifs.")
