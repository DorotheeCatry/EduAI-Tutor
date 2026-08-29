"""
Compteur de générations par personne et par jour.

Compétence visée : C4 (épreuve E1) — modélisation et minimisation des données
Compétence visée : C13 (épreuve E3) — maîtrise du coût en production

Chaque génération de cours, de réponse ou de quiz déclenche un appel facturé
au fournisseur de modèles. Sans compteur, un service ouvert dépense sans borne :
c'est le risque que ce module couvre, et le seul.
"""

from django.conf import settings
from django.db import models


class ConsommationJournaliere(models.Model):
    """
    Nombre de générations consommées par une personne un jour donné.

    Compétence visée : C4 (épreuve E1)

    Choix : un compteur agrégé par jour, et non un enregistrement par
    génération. Motivation : un enregistrement par génération constituerait un
    journal horodaté de l'activité de chaque apprenant — une donnée personnelle
    nouvelle, avec sa durée de conservation, son droit d'accès et son droit à
    l'effacement à tenir. Le compteur répond à la même question (« combien
    aujourd'hui ? ») sans conserver ni l'heure, ni le sujet, ni l'ordre des
    demandes. La minimisation n'est pas ici une précaution de style : c'est le
    critère C4.

    Choix : le plafond global du service se calcule en sommant ces lignes,
    plutôt que dans une table dédiée. Motivation : deux compteurs distincts
    peuvent diverger — l'un incrémenté, l'autre non, et plus rien ne dit lequel
    a raison. Une somme ne peut pas diverger de ses termes.

    Choix : `utilisateur` est facultatif. Motivation : l'API du service IA (C9)
    est consommée par des programmes porteurs d'une clé de service, pas par des
    apprenants inscrits — il n'y a personne à qui imputer la génération. Ces
    appels alimentent néanmoins une ligne, sans quoi ils échapperaient au
    plafond global et le budget ne serait plus borné que d'un côté. Ils ne se
    voient pas appliquer de quota individuel, qui n'aurait rien à décompter :
    leur limitation propre est le débit par clé, à l'entrée de l'API.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consommations_journalieres",
        verbose_name="apprenant",
        null=True,
        blank=True,
        help_text=(
            "Vide pour les générations demandées par l'API du service IA (C9), "
            "dont les consommateurs sont des programmes porteurs d'une clé de "
            "service et non des apprenants inscrits."
        ),
    )
    jour = models.DateField(
        verbose_name="jour de consommation",
        help_text="Date locale du serveur ; le compteur repart à zéro à minuit.",
    )
    generations = models.PositiveIntegerField(
        default=0,
        verbose_name="générations consommées",
    )

    class Meta:
        verbose_name = "consommation journalière"
        verbose_name_plural = "consommations journalières"
        # Une seule ligne par personne et par jour : la contrainte est tenue par
        # le moteur et non par le code appelant. Deux requêtes simultanées ne
        # peuvent donc pas créer deux compteurs pour la même journée, chacun
        # comptant la moitié des générations.
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "jour"],
                name="une_consommation_par_personne_et_par_jour",
            ),
            # PostgreSQL considère deux NULL comme distincts : la contrainte
            # ci-dessus ne dirait donc rien des lignes du service IA, et il s'en
            # créerait une par appel. Une contrainte partielle couvre ce cas.
            models.UniqueConstraint(
                fields=["jour"],
                condition=models.Q(utilisateur__isnull=True),
                name="une_consommation_service_ia_par_jour",
            ),
        ]
        # Le plafond global somme toutes les lignes d'une journée : c'est la
        # requête la plus fréquente après la lecture du compteur individuel.
        indexes = [
            models.Index(fields=["jour"], name="idx_consommation_jour"),
        ]
        ordering = ["-jour", "utilisateur"]

    def __str__(self):
        return f"{self.utilisateur} — {self.jour} : {self.generations} génération(s)"
