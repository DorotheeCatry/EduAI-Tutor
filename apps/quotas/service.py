"""
Contrôle des quotas de génération.

Compétence visée : C13 (épreuve E3) — maîtrise du coût et de l'exposition
Compétence visée : C17 (épreuve E4) — application web
Compétence visée : C9 (épreuve E2) — le service IA emprunte le même chemin

Deux plafonds, qui ne protègent pas de la même chose :

- le **quota individuel** empêche une personne de consommer tout le budget ;
- le **plafond global** empêche que cinquante inscriptions le fassent à sa
  place. C'est lui la protection réelle : le quota individuel ne borne rien
  tant que le nombre de comptes n'est pas borné.

Les deux sont lus depuis l'environnement, avec des valeurs par défaut
prudentes : une variable oubliée doit restreindre, jamais ouvrir.
"""

from __future__ import annotations

import logging
import os

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import ConsommationJournaliere

logger = logging.getLogger(__name__)

#: Valeurs de repli. Choix : des valeurs basses. Motivation : la règle des
#: défauts asymétriques déjà appliquée aux secrets vaut pour les plafonds — un
#: réglage absent doit produire un service restreint et visible, pas un service
#: ouvert et silencieux.
QUOTA_INDIVIDUEL_DEFAUT = 5
PLAFOND_GLOBAL_DEFAUT = 200


class QuotaDepasse(Exception):
    """
    Une génération est refusée parce qu'un plafond est atteint.

    Compétence visée : C13 (épreuve E3)

    Choix : une exception plutôt qu'une valeur de retour. Motivation : les
    méthodes de l'orchestrateur renvoient toutes un dictionnaire dont le champ
    `success` peut valoir `False` pour une panne du fournisseur. Confondre
    « refusé » et « en panne » dans ce même champ conduirait à afficher un
    message d'erreur technique là où il faut une explication — et à réessayer
    là où il faut attendre.

    Attribut `portee` : « individuel » ou « global ». L'appelant n'a pas à
    l'analyser pour afficher le message, mais le monitorage distingue ainsi un
    apprenant assidu d'un service saturé.
    """

    def __init__(self, message: str, portee: str):
        super().__init__(message)
        self.message = message
        self.portee = portee


def _entier_positif(nom_variable: str, defaut: int) -> int:
    """
    Lit un plafond entier dans l'environnement.

    Compétence visée : C13 (épreuve E3)

    Choix : une valeur illisible ou négative retombe sur le défaut, avec une
    entrée au journal. Motivation : interrompre le démarrage serait justifié
    pour un secret manquant — l'absence de secret ouvre une faille. Ici,
    l'absence de réglage ne fait que rendre le service plus restrictif : refuser
    de démarrer coûterait plus que ce que cela protège. Le journal garde la
    trace pour qu'un réglage fautif ne passe pas inaperçu.
    """
    brut = os.environ.get(nom_variable, "").strip()
    if not brut:
        return defaut

    try:
        valeur = int(brut)
    except ValueError:
        logger.error(
            "%s vaut « %s », qui n'est pas un entier. Valeur par défaut retenue : %s.",
            nom_variable, brut, defaut,
        )
        return defaut

    if valeur < 0:
        logger.error(
            "%s vaut %s, une valeur négative n'a pas de sens pour un plafond. "
            "Valeur par défaut retenue : %s.",
            nom_variable, valeur, defaut,
        )
        return defaut

    return valeur


def quota_individuel() -> int:
    """Nombre de générations autorisées par personne et par jour."""
    return _entier_positif("EDUAI_QUOTA_GENERATIONS_PAR_JOUR", QUOTA_INDIVIDUEL_DEFAUT)


def plafond_global() -> int:
    """Nombre de générations autorisées par jour, toutes personnes confondues."""
    return _entier_positif("EDUAI_PLAFOND_GENERATIONS_PAR_JOUR", PLAFOND_GLOBAL_DEFAUT)


def _jour_courant():
    """
    Jour de référence du compteur.

    Compétence visée : C13 (épreuve E3)

    Choix : la date locale du serveur, donc une remise à zéro à minuit, plutôt
    qu'une fenêtre glissante de 24 heures. Motivation : une fenêtre glissante
    exige de conserver l'horodatage de chaque génération, c'est-à-dire un
    journal d'activité nominatif — une donnée personnelle que le service n'a
    aucune raison de détenir (minimisation, C4).

    Limite assumée, et il faut la dire : une personne peut consommer son quota
    à 23 h 50 puis le suivant à 00 h 10, soit le double en une heure. Le plafond
    global reste, lui, borné par jour, et c'est lui qui protège le budget.
    """
    return timezone.localdate()


def etat(utilisateur) -> dict:
    """
    Décrit la consommation du jour sans rien consommer.

    Compétence visée : C17 (épreuve E4)

    Sert à afficher « il vous reste N générations » sans passer par un refus.
    """
    jour = _jour_courant()
    consommees = (
        ConsommationJournaliere.objects
        .filter(utilisateur=utilisateur, jour=jour)
        .values_list("generations", flat=True)
        .first()
        or 0
    )
    total_global = _total_global(jour)

    quota = quota_individuel()
    return {
        "jour": jour,
        "consommees": consommees,
        "quota": quota,
        "restantes": max(quota - consommees, 0),
        "total_global": total_global,
        "plafond_global": plafond_global(),
    }


def _total_global(jour) -> int:
    """
    Somme des générations de la journée, tous consommateurs confondus.

    Compétence visée : C13 (épreuve E3)

    Inclut la ligne du service IA (`utilisateur` vide) : c'est le budget du
    projet qui est borné, pas celui des seuls apprenants inscrits.
    """
    return (
        ConsommationJournaliere.objects
        .filter(jour=jour)
        .aggregate(total=Sum("generations"))["total"]
        or 0
    )


def consommer_pour_le_service_ia() -> int:
    """
    Décompte une génération demandée par l'API du service IA (C9).

    Compétence visée : C13 (épreuve E3)
    Compétence visée : C9 (épreuve E2)

    Renvoie le nombre de générations du service pour la journée.
    Lève `QuotaDepasse` si le plafond global est atteint.

    Choix : une fonction distincte de `consommer`, et non un cas particulier à
    l'intérieur. Motivation : les deux chemins n'appliquent pas les mêmes
    règles, et une fonction qui applique des règles différentes selon que son
    argument est vide ou non finit par les appliquer au mauvais moment. Deux
    noms, deux contrats, deux appels explicites.

    Choix : **aucun quota individuel** ici. Motivation : les consommateurs de
    cette API sont des programmes porteurs d'une clé de service, pas des
    apprenants — il n'y a personne à qui imputer un quota de cinq générations.
    Leur limitation propre existe et vit à l'entrée de l'API : un débit par clé
    de service (`SERVICE_IA_QUOTA_GENERATION`), qui borne la cadence quand ce
    plafond-ci borne le volume du jour.

    Choix : le plafond global s'applique quand même. Motivation : sans lui,
    l'API deviendrait le trou par lequel le budget se vide, et le plafond
    n'aurait plus de sens — il ne bornerait qu'une moitié des dépenses.
    """
    jour = _jour_courant()
    plafond = plafond_global()

    with transaction.atomic():
        ligne, _cree = (
            ConsommationJournaliere.objects
            .select_for_update()
            .get_or_create(utilisateur=None, jour=jour)
        )

        if _total_global(jour) >= plafond:
            logger.warning(
                "Plafond global atteint : %s générations le %s. "
                "L'API du service IA refuse les générations jusqu'à minuit.",
                plafond, jour,
            )
            raise QuotaDepasse(
                "Le service a atteint son plafond de générations pour aujourd'hui. "
                "La recherche documentaire reste disponible ; la génération "
                "reprendra demain.",
                portee="global",
            )

        ligne.generations = F("generations") + 1
        ligne.save(update_fields=["generations"])
        ligne.refresh_from_db(fields=["generations"])

    return ligne.generations


def consommer(utilisateur) -> int:
    """
    Décompte une génération, ou refuse.

    Compétence visée : C13 (épreuve E3)
    Compétence visée : C4 (épreuve E1) — compteur en base

    Renvoie le nombre de générations consommées après incrément.
    Lève `QuotaDepasse` si un plafond est atteint — rien n'est alors décompté.

    Choix : le compteur vit en base, pas en mémoire de processus. Motivation :
    un compteur en mémoire ne survit pas à un redémarrage et ne vaut rien
    derrière plusieurs travailleurs, chacun ayant le sien. Le monitorage du
    projet a déjà montré ce que valent les mesures propres à un processus.

    Choix : `select_for_update` dans une transaction. Motivation : lire le
    compteur puis l'incrémenter en deux temps laisse deux requêtes simultanées
    lire la même valeur et dépasser le plafond d'une unité — un défaut invisible
    en test et systématique sous charge. Le verrou de ligne sérialise les deux.

    Choix : le refus est prononcé avant l'appel au modèle, jamais après.
    Motivation : refuser après coup laisserait la dépense déjà engagée, ce qui
    ôte au quota sa raison d'être.
    """
    if utilisateur is None or not getattr(utilisateur, "is_authenticated", False):
        # Aucun chemin de dépense anonyme. Le quota n'a de sens que rattaché à
        # quelqu'un : sans compte, il n'y a rien à décompter et rien à limiter.
        raise QuotaDepasse(
            "La génération par intelligence artificielle demande un compte. "
            "Connectez-vous pour l'utiliser.",
            portee="anonyme",
        )

    jour = _jour_courant()
    quota = quota_individuel()
    plafond = plafond_global()

    with transaction.atomic():
        ligne, _cree = (
            ConsommationJournaliere.objects
            .select_for_update()
            .get_or_create(utilisateur=utilisateur, jour=jour)
        )

        if ligne.generations >= quota:
            logger.info(
                "Quota individuel atteint : utilisateur %s, %s/%s générations le %s.",
                utilisateur.pk, ligne.generations, quota, jour,
            )
            raise QuotaDepasse(
                f"Vous avez utilisé vos {quota} générations du jour. "
                "Le compteur repart à zéro à minuit — les cours, exercices et "
                "quiz déjà enregistrés restent consultables.",
                portee="individuel",
            )

        total_global = _total_global(jour)
        if total_global >= plafond:
            logger.warning(
                "Plafond global atteint : %s/%s générations le %s. "
                "Le service passe en consultation seule jusqu'à minuit.",
                total_global, plafond, jour,
            )
            raise QuotaDepasse(
                "Le service a atteint son plafond de générations pour aujourd'hui. "
                "La consultation reste ouverte ; la génération reprendra demain.",
                portee="global",
            )

        ligne.generations = F("generations") + 1
        ligne.save(update_fields=["generations"])
        ligne.refresh_from_db(fields=["generations"])

    return ligne.generations
