"""
Import d'un référentiel de compétences depuis un fichier.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — chargement de données ; C19 (E5)

C'est ce qui rend vérifiable l'argument de généricité : un autre organisme
charge son référentiel sans toucher au code.

Choix : le format JSON seul, pas YAML. Motivation : YAML supposerait de
déclarer une dépendance de plus à quatre jours du rendu — `pyyaml` n'est
présent dans l'environnement que par transitivité, et s'appuyer sur une
dépendance non déclarée est le genre de couplage invisible que ce projet
documente. Un fichier YAML se convertit en une commande, et le format d'entrée
n'est pas ce que le référentiel démontre.

Usage :
    uv run python manage.py importer_referentiel <fichier.json>
    uv run python manage.py importer_referentiel <fichier.json> --activer
    uv run python manage.py importer_referentiel <fichier.json> --controler
"""

import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.referentiel.models import (
    NOMBRE_DE_NIVEAUX,
    Competence,
    Module,
    Referentiel,
    valider_libelles_de_niveaux,
)


class Command(BaseCommand):
    """
    Charge un référentiel, ses modules et ses compétences.

    Compétence visée : C17 (épreuve E4)
    """

    help = "Importe un référentiel de compétences depuis un fichier JSON."

    def add_arguments(self, analyseur):
        analyseur.add_argument("fichier", type=str, help="Chemin du fichier JSON.")
        analyseur.add_argument(
            "--activer", action="store_true",
            help="Rend ce référentiel actif — c'est celui que l'interface affiche.",
        )
        analyseur.add_argument(
            "--controler", action="store_true",
            help="Lit et valide le fichier sans rien écrire en base.",
        )

    # --- 1. Lecture et validation ---

    def _lire(self, chemin):
        """
        Lit le fichier et en vérifie la forme, avant toute écriture.

        Compétence visée : C17 (épreuve E4)

        Choix : tout valider d'abord, écrire ensuite. Motivation : un import
        qui échoue au milieu laisse un référentiel amputé, dont personne ne
        sait qu'il l'est. C'est le motif de l'incident 001 — un chargement
        annoncé réussi sur une base qui ne portait pas ce qu'il annonçait.
        """
        fichier = Path(chemin)
        if not fichier.is_file():
            raise CommandError(f"fichier introuvable : {chemin}")

        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erreur:
            raise CommandError(f"JSON illisible : {erreur}") from erreur

        for champ in ("code", "intitule", "modules"):
            if champ not in donnees:
                raise CommandError(f"champ obligatoire absent : « {champ} »")

        niveaux = donnees.get("niveaux", [])
        if niveaux:
            try:
                valider_libelles_de_niveaux(niveaux)
            except ValidationError as erreur:
                raise CommandError("; ".join(erreur.messages)) from erreur

        if not isinstance(donnees["modules"], list) or not donnees["modules"]:
            raise CommandError("« modules » doit être une liste non vide")

        codes_de_modules = set()
        for rang, module in enumerate(donnees["modules"], start=1):
            for champ in ("code", "intitule", "competences"):
                if champ not in module:
                    raise CommandError(
                        f"module n°{rang} : champ obligatoire absent « {champ} »"
                    )
            if module["code"] in codes_de_modules:
                raise CommandError(f"code de module en double : {module['code']}")
            codes_de_modules.add(module["code"])

            if not isinstance(module["competences"], list) or not module["competences"]:
                raise CommandError(
                    f"module {module['code']} : « competences » doit être une "
                    f"liste non vide"
                )

            codes_de_competences = set()
            for competence in module["competences"]:
                for champ in ("code", "intitule"):
                    if champ not in competence:
                        raise CommandError(
                            f"module {module['code']} : compétence sans « {champ} »"
                        )
                if competence["code"] in codes_de_competences:
                    raise CommandError(
                        f"module {module['code']} : code de compétence en double "
                        f"« {competence['code']} »"
                    )
                codes_de_competences.add(competence["code"])

        return donnees

    # --- 2. Écriture ---

    @transaction.atomic
    def _ecrire(self, donnees, activer):
        """
        Crée ou met à jour le référentiel, ses modules et ses compétences.

        Compétence visée : C17 (épreuve E4), C4 (E1)

        Choix : l'identité est le `code`, jamais la clé primaire. Motivation :
        relancer l'import du même fichier ne doit rien dupliquer. Le référentiel
        se corrige et se recharge, comme le pipeline de données du bloc 1.

        Choix : les compétences absentes du fichier sont SUPPRIMÉES. Motivation :
        un référentiel est un tout. Les conserver ferait cohabiter des
        compétences retirées par l'organisme avec celles qu'il maintient, sans
        qu'on puisse distinguer les unes des autres.
        """
        referentiel, cree = Referentiel.objects.update_or_create(
            code=donnees["code"],
            defaults={
                "intitule": donnees["intitule"],
                "version": donnees.get("version", ""),
                "source": donnees.get("source", ""),
                "libelles_de_niveaux": donnees.get("niveaux", []),
            },
        )

        if activer:
            # L'unicité est garantie par une contrainte de base : il faut
            # désactiver l'ancien avant d'activer le nouveau, dans la même
            # transaction.
            Referentiel.objects.exclude(pk=referentiel.pk).update(est_actif=False)
            referentiel.est_actif = True
            referentiel.save(update_fields=["est_actif"])

        codes_de_modules = []
        compte = {"modules": 0, "competences": 0, "retirees": 0}

        for rang, donnees_module in enumerate(donnees["modules"], start=1):
            module, _ = Module.objects.update_or_create(
                referentiel=referentiel,
                code=donnees_module["code"],
                defaults={
                    "intitule": donnees_module["intitule"],
                    "ordre": donnees_module.get("ordre", rang),
                },
            )
            codes_de_modules.append(module.code)
            compte["modules"] += 1

            codes_de_competences = []
            for rang_c, donnees_competence in enumerate(donnees_module["competences"], 1):
                Competence.objects.update_or_create(
                    module=module,
                    code=donnees_competence["code"],
                    defaults={
                        "intitule": donnees_competence["intitule"],
                        "description": donnees_competence.get("description", ""),
                        "ordre": donnees_competence.get("ordre", rang_c),
                    },
                )
                codes_de_competences.append(donnees_competence["code"])
                compte["competences"] += 1

            retirees, _details = module.competences.exclude(
                code__in=codes_de_competences
            ).delete()
            compte["retirees"] += retirees

        retires, _details = referentiel.modules.exclude(
            code__in=codes_de_modules
        ).delete()
        compte["retirees"] += retires

        return referentiel, cree, compte

    # --- 3. Point de lancement ---

    def handle(self, *args, **options):
        """
        Lit, valide, puis écrit — et rend compte de ce qui est en base.

        Compétence visée : C17 (épreuve E4), C19 (E5)
        """
        donnees = self._lire(options["fichier"])

        modules = len(donnees["modules"])
        competences = sum(len(m["competences"]) for m in donnees["modules"])
        self.stdout.write(
            f"lu : {donnees['code']} — {modules} modules, {competences} compétences"
        )

        if options["controler"]:
            self.stdout.write(self.style.SUCCESS(
                "fichier valide, rien écrit (--controler)"
            ))
            return

        referentiel, cree, compte = self._ecrire(donnees, options["activer"])

        # Le compte rendu porte sur ce que la base contient APRÈS écriture, et
        # non sur ce que le fichier annonçait. Compter ce qu'on a envoyé plutôt
        # que ce qui est arrivé est le premier incident de ce projet.
        en_base = Competence.objects.filter(module__referentiel=referentiel).count()
        modules_en_base = referentiel.modules.count()

        self.stdout.write(
            f"{'créé' if cree else 'mis à jour'} : {referentiel.intitule}"
        )
        self.stdout.write(
            f"en base : {modules_en_base} modules, {en_base} compétences, "
            f"{NOMBRE_DE_NIVEAUX} niveaux ({', '.join(referentiel.niveaux)})"
        )
        if compte["retirees"]:
            self.stdout.write(
                f"retirés car absents du fichier : {compte['retirees']} enregistrements"
            )
        if referentiel.est_actif:
            self.stdout.write(self.style.SUCCESS("référentiel actif"))
        else:
            self.stdout.write(
                "référentiel inactif — l'interface ne l'affichera pas. "
                "Relancer avec --activer."
            )

        if en_base != competences:
            raise CommandError(
                f"écart entre le fichier ({competences}) et la base ({en_base}) : "
                f"l'import n'a pas produit ce qu'il annonçait"
            )
