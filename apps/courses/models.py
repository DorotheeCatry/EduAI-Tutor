from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Course(models.Model):
    """Model for saving generated courses"""
    
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=200)
    module = models.CharField(max_length=100, default='general')
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_favorite = models.BooleanField(default=False)
    
    # Statistics
    view_count = models.PositiveIntegerField(default=0)
    completion_rate = models.FloatField(default=0.0)  # Reading percentage
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Course"
        verbose_name_plural = "Courses"
    
    def __str__(self):
        return f"{self.title}"
    
    def increment_view_count(self):
        """Increments view counter"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

class CourseSection(models.Model):
    """Course sections for better tracking"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField()
    section_type = models.CharField(max_length=50, choices=[
        ('introduction', 'Introduction'),
        ('explanation', 'Explanation'),
        ('examples', 'Examples'),
        ('summary', 'Summary'),
        ('advanced', 'Advanced'),
    ])
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']


# ===========================================================================
# Les trois couches du cours : référence, fiche, ajouts
# ===========================================================================
#
# Compétence visée : C17 (épreuve E4) — application web
# Compétence concernée : C10 (E3) — intégration du modèle
#
# **Les trois se rattachent à la compétence, jamais au cours.** C'est ce qui
# permet de remplacer un cours de référence sans perdre le travail de
# l'apprenant : sa fiche pointe la compétence, pas le document qu'il lisait le
# jour où il l'a écrite.
#
# Le modèle `Course` ci-dessus n'est pas remplacé : il reste la génération sur
# sujet libre, hors référentiel, et l'accueil comme la page Référentiel
# comptent déjà ses lignes.


class CoursDeReference(models.Model):
    """
    Le cours d'une compétence, publié par l'organisme ou engendré en attendant.

    Compétence visée : C17 (épreuve E4)

    Choix : deux statuts distincts, et non un drapeau « engendré ». Motivation :
    le statut décide du comportement, pas seulement de l'affichage. Un cours
    publié engage la responsabilité pédagogique d'un formateur qui l'a relu ;
    un cours provisoire n'engage rien. Les confondre à l'écran ferait réviser
    une production automatique en croyant réviser un contenu validé.

    Choix : le provisoire n'est pas supprimé quand le publié arrive. Motivation :
    il cède la place — `remplace_le` est daté et il sort de l'affichage — mais
    l'historique reste. Un apprenant doit pouvoir comprendre d'où venait ce
    qu'il a lu la semaine précédente.
    """

    PUBLIE = "publie"
    PROVISOIRE = "provisoire"
    STATUTS = [
        (PUBLIE, _("Publié par l'organisme")),
        (PROVISOIRE, _("Provisoire, engendré par le modèle")),
    ]

    competence = models.ForeignKey(
        "referentiel.Competence", on_delete=models.CASCADE,
        related_name="cours_de_reference", verbose_name=_("Compétence"),
    )
    statut = models.CharField(
        max_length=12, choices=STATUTS, verbose_name=_("Statut"),
    )
    titre = models.CharField(max_length=200, verbose_name=_("Titre"))
    contenu = models.TextField(verbose_name=_("Contenu"))

    # Renseigné pour un cours publié, nul pour un cours engendré. Ce champ dit
    # qui répond du contenu — c'est la différence entre les deux statuts.
    redige_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cours_rediges", verbose_name=_("Rédigé par"),
    )
    sources = models.JSONField(
        default=list, blank=True, verbose_name=_("Sources"),
        help_text=_("Fragments du corpus employés, avec leur licence."),
    )

    cree_le = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    remplace_le = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Remplacé le"),
        help_text=_("Daté quand un cours publié prend la place d'un provisoire."),
    )

    class Meta:
        verbose_name = _("Cours de référence")
        verbose_name_plural = _("Cours de référence")
        ordering = ["competence__code", "-cree_le"]
        constraints = [
            # Au plus un cours ACTIF par compétence et par statut. Un cours
            # remplacé porte une date et sort de la contrainte : c'est ce qui
            # permet de conserver l'historique sans autoriser deux cours
            # courants pour la même compétence.
            models.UniqueConstraint(
                fields=["competence", "statut"],
                condition=models.Q(remplace_le__isnull=True),
                name="un_seul_cours_actif_par_competence_et_statut",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titre} ({self.get_statut_display()})"

    @property
    def est_provisoire(self) -> bool:
        return self.statut == self.PROVISOIRE


class FicheDApprenant(models.Model):
    """
    La version personnelle d'une compétence, pour un apprenant.

    Compétence visée : C17 (épreuve E4)

    Choix : la fiche ne référence AUCUN cours. Motivation : c'est ce qui la
    fait survivre au remplacement du cours de référence. Une clé étrangère vers
    le cours ferait disparaître le travail de l'apprenant le jour où le
    formateur publie le sien — exactement l'inverse de ce que ce dispositif
    cherche.
    """

    apprenant = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="fiches",
        verbose_name=_("Apprenant"),
    )
    competence = models.ForeignKey(
        "referentiel.Competence", on_delete=models.CASCADE,
        related_name="fiches", verbose_name=_("Compétence"),
    )
    cree_le = models.DateTimeField(auto_now_add=True, verbose_name=_("Créée le"))
    modifie_le = models.DateTimeField(auto_now=True, verbose_name=_("Modifiée le"))

    class Meta:
        verbose_name = _("Fiche d'apprenant")
        verbose_name_plural = _("Fiches d'apprenant")
        ordering = ["-modifie_le"]
        unique_together = ["apprenant", "competence"]

    def __str__(self) -> str:
        return f"Fiche de {self.apprenant} — {self.competence}"


class AjoutDeFiche(models.Model):
    """
    Un enrichissement ajouté à une fiche.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C4 (E1) — l'attribution voyage avec le contenu

    Choix : chaque ajout porte **la question qui l'a produit**, et non seulement
    sa réponse. Motivation : un ajout né de « développe cette partie » sur une
    section qui n'existe plus dans le cours suivant devient incompréhensible
    sans elle. La question survit au cours ; la section, non.

    Choix : `section_visee` est un texte, pas une clé étrangère. Motivation :
    elle désigne une section d'un cours qui peut être remplacé. Une clé
    étrangère la ferait disparaître avec lui.
    """

    A_LA_DEMANDE = "a_la_demande"
    PARCOURS = "parcours"
    MONTEE_DE_NIVEAU = "montee_de_niveau"
    ORIGINES = [
        (A_LA_DEMANDE, _("Demandé par l'apprenant")),
        (PARCOURS, _("Proposé par le parcours")),
        (MONTEE_DE_NIVEAU, _("Montée de niveau")),
    ]

    fiche = models.ForeignKey(
        FicheDApprenant, on_delete=models.CASCADE, related_name="ajouts",
        verbose_name=_("Fiche"),
    )
    question = models.CharField(
        max_length=300, verbose_name=_("Question d'origine"),
        help_text=_("La question ou l'action qui a produit cet ajout."),
    )
    origine = models.CharField(
        max_length=20, choices=ORIGINES, default=A_LA_DEMANDE,
        verbose_name=_("Origine"),
    )
    section_visee = models.CharField(
        max_length=200, blank=True, verbose_name=_("Section visée"),
        help_text=_("Titre de la section du cours à laquelle l'ajout répondait."),
    )
    niveau_vise = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Niveau visé"),
        help_text=_("Renseigné pour une montée de niveau, nul sinon."),
    )
    contenu = models.TextField(verbose_name=_("Contenu"))
    sources = models.JSONField(
        default=list, blank=True, verbose_name=_("Sources"),
        help_text=_("url_source, code_licence et attribution_requise par fragment."),
    )
    cree_le = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))

    class Meta:
        verbose_name = _("Ajout de fiche")
        verbose_name_plural = _("Ajouts de fiche")
        ordering = ["cree_le"]

    def __str__(self) -> str:
        return f"{self.question[:60]} ({self.get_origine_display()})"

    @property
    def attribution_requise(self) -> bool:
        """Indique si au moins une source impose de nommer son auteur."""
        return any(s.get("attribution_requise") for s in self.sources or [])
