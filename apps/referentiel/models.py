"""
Référentiel de compétences : données, jamais code.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — modélisation ; C13 (E3) — accessibilité

Ces trois modèles portent la structure exigée par le chantier : un référentiel
contient des modules, un module contient des compétences, et une compétence
s'atteint à trois niveaux.

Choix : aucun libellé de compétence n'existe dans le code. Motivation : c'est
la condition de l'argument de généricité. Un organisme qui charge son propre
référentiel ne doit toucher ni un gabarit, ni une constante, ni une migration —
seulement un fichier. Un libellé écrit en dur, même « provisoirement », rendrait
cet argument invérifiable, et ce projet vient de payer ce que coûte un
provisoire dans du code (incident 010).

Choix : trois niveaux, dont les libellés sont modifiables mais dont le nombre
ne l'est pas. Motivation : la règle de progression et l'affichage sont bâtis
sur exactement trois paliers. Rendre le nombre variable supposerait de rendre
variables la règle et l'interface, ce qui n'est pas ouvrable à quatre jours du
rendu. Un organisme dont l'échelle compte quatre paliers devra donc modifier le
code : c'est une limite, elle est écrite ici et dans la décision 026 plutôt que
découverte.

À ne pas confondre avec les « modules » de `apps/rag/module_loader.py`, qui
indexent le contenu pédagogique du corpus (`data/contents/index/*.json`). Les
deux notions se recouvrent volontairement dans le référentiel livré par défaut
— Python, analyse de données, SQL, apprentissage automatique — mais elles ne
sont pas couplées : l'une décrit ce qu'on sait chercher, l'autre ce qu'on
cherche à savoir.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

#: Nombre de paliers d'une compétence. Voir la docstring du module.
NOMBRE_DE_NIVEAUX = 3

#: Libellés par défaut des trois paliers, employés quand un référentiel importé
#: n'en propose pas. « Imiter, adapter, transposer » est l'échelle retenue par
#: le chantier ; un référentiel peut la renommer, pas la rallonger.
NIVEAUX_PAR_DEFAUT = [_("Imiter"), _("Adapter"), _("Transposer")]


def valider_libelles_de_niveaux(valeur):
    """
    Refuse une échelle qui ne compte pas exactement trois paliers.

    Compétence visée : C17 (épreuve E4)

    Choix : une validation plutôt qu'une troncature silencieuse. Motivation :
    un référentiel à quatre paliers importé sans erreur donnerait une
    progression amputée du quatrième, sans que personne ne s'en aperçoive avant
    de chercher pourquoi une compétence ne s'achève jamais.
    """
    if not isinstance(valeur, list):
        raise ValidationError(_("Les libellés de niveaux doivent former une liste."))
    if len(valeur) != NOMBRE_DE_NIVEAUX:
        raise ValidationError(
            _("Un référentiel compte exactement %(attendu)s niveaux, "
              "%(recu)s fournis.")
            % {"attendu": NOMBRE_DE_NIVEAUX, "recu": len(valeur)}
        )
    if any(not isinstance(libelle, str) or not libelle.strip() for libelle in valeur):
        raise ValidationError(_("Chaque libellé de niveau doit être un texte non vide."))


class Referentiel(models.Model):
    """
    Un cadre de compétences, tel qu'un organisme le publie.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C4 (E1)

    Choix : plusieurs référentiels peuvent coexister, un seul est actif.
    Motivation : remplacer un référentiel en supprimant l'ancien effacerait la
    progression qui s'y rattache. Les garder côte à côte permet d'en changer,
    et de revenir en arrière si le nouveau se révèle mal découpé.
    """

    code = models.SlugField(
        max_length=80, unique=True,
        verbose_name=_("Code"),
        help_text=_("Identifiant stable, repris à l'import pour mettre à jour "
                    "plutôt que dupliquer."),
    )
    intitule = models.CharField(max_length=200, verbose_name=_("Intitulé"))
    version = models.CharField(
        max_length=40, blank=True, verbose_name=_("Version"),
        help_text=_("Version du référentiel chez son auteur, telle qu'il la nomme."),
    )
    source = models.CharField(
        max_length=300, blank=True, verbose_name=_("Source"),
        help_text=_("D'où vient ce référentiel : organisme, document, URL."),
    )
    libelles_de_niveaux = models.JSONField(
        default=list, blank=True,
        validators=[valider_libelles_de_niveaux],
        verbose_name=_("Libellés des trois niveaux"),
    )
    est_actif = models.BooleanField(
        default=False, verbose_name=_("Actif"),
        help_text=_("Un seul référentiel actif à la fois : c'est celui que "
                    "l'interface affiche."),
    )
    importe_le = models.DateTimeField(auto_now=True, verbose_name=_("Importé le"))

    class Meta:
        verbose_name = _("Référentiel")
        verbose_name_plural = _("Référentiels")
        ordering = ["intitule"]
        constraints = [
            # Un seul référentiel actif, garanti par la base et non par une
            # convention de code. Une convention se contourne par l'admin, un
            # import concurrent ou un shell ; une contrainte, non.
            models.UniqueConstraint(
                fields=["est_actif"],
                condition=models.Q(est_actif=True),
                name="un_seul_referentiel_actif",
            ),
        ]

    def __str__(self):
        return self.intitule

    @property
    def niveaux(self):
        """
        Rend les trois libellés de niveaux, les valeurs par défaut à défaut.

        Compétence visée : C17 (épreuve E4)
        """
        return self.libelles_de_niveaux or [str(n) for n in NIVEAUX_PAR_DEFAUT]

    def libelle_de_niveau(self, niveau):
        """
        Rend le libellé d'un niveau, de 1 à 3.

        Compétence visée : C13 (épreuve E3) — accessibilité

        Ce libellé est ce qui permet de ne pas distinguer les niveaux par la
        seule couleur : un apprenant daltonien doit lire son niveau, pas le
        deviner à une nuance.
        """
        if not 1 <= niveau <= NOMBRE_DE_NIVEAUX:
            raise ValueError(f"niveau hors échelle : {niveau}")
        return self.niveaux[niveau - 1]


class Module(models.Model):
    """
    Un regroupement de compétences au sein d'un référentiel.

    Compétence visée : C17 (épreuve E4)
    """

    referentiel = models.ForeignKey(
        Referentiel, on_delete=models.CASCADE, related_name="modules",
        verbose_name=_("Référentiel"),
    )
    code = models.SlugField(max_length=80, verbose_name=_("Code"))
    intitule = models.CharField(max_length=200, verbose_name=_("Intitulé"))
    ordre = models.PositiveIntegerField(
        default=0, verbose_name=_("Ordre"),
        help_text=_("Ordre d'affichage ; à défaut, l'ordre alphabétique du code."),
    )

    class Meta:
        verbose_name = _("Module")
        verbose_name_plural = _("Modules")
        ordering = ["ordre", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["referentiel", "code"], name="code_de_module_unique_par_referentiel",
            ),
        ]

    def __str__(self):
        return self.intitule


class Competence(models.Model):
    """
    Une compétence, atteignable à trois niveaux.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C4 (E1)

    Le rattachement d'un exercice ou d'un quiz à une compétence n'est pas ici :
    il fait l'objet de l'étape suivante du chantier. Ce modèle décrit ce qu'il
    y a à acquérir, pas ce qui a été acquis.
    """

    module = models.ForeignKey(
        Module, on_delete=models.CASCADE, related_name="competences",
        verbose_name=_("Module"),
    )
    code = models.SlugField(max_length=80, verbose_name=_("Code"))
    intitule = models.CharField(max_length=300, verbose_name=_("Intitulé"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    ordre = models.PositiveIntegerField(default=0, verbose_name=_("Ordre"))

    class Meta:
        verbose_name = _("Compétence")
        verbose_name_plural = _("Compétences")
        ordering = ["ordre", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "code"], name="code_de_competence_unique_par_module",
            ),
        ]

    def __str__(self):
        return self.intitule
