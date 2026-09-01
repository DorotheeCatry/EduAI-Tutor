"""
Ce que Koda sait de l'apprenant, et ce qu'il a le droit d'en dire.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C20 (E5) — données du suivi ; C21 (E5)

Koda s'adresse à l'apprenant par son pseudonyme et se souvient de la dernière
séance. C'est ce qui fait la différence entre un bouton d'aide et quelqu'un
qu'on retrouve.

**Règle unique, et elle n'est pas négociable : Koda ne dit que ce que la base
contient.** Le projet a retiré sept foyers de données fabriquées en une
semaine ; une mascotte chaleureuse est précisément le genre d'endroit où l'on
réintroduit du faux sans y penser, parce que « ça sonne bien ». Un « trois
jours d'affilée, bravo ! » est un mensonge si personne ne compte les jours.

Ce que Koda peut employer, et pourquoi :

| Donnée | Source | Vérifiée |
|---|---|---|
| Pseudonyme | `user.username` | toujours vrai |
| Dernière séance | `LearningSession` close | incident 010 |
| Dernier exercice | `UserExerciseProgress` | réserve 13 |
| Notions à revoir | `UserMistake` | décision 028 |

Ce que Koda **ne peut pas** employer : `current_streak`. Le champ existe, il
est lu pour calculer un bonus d'expérience, et **rien ne l'écrit jamais** — il
vaut zéro pour tout le monde. Annoncer une série serait inventer (réserve 19).
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext as _

from apps.agents.agent_watcher import UserMistake
from apps.accueil.services import (
    derniere_activite,
    erreurs_de_quiz,
    notions_a_revoir,
)

logger = logging.getLogger(__name__)

# Au-delà de ce délai, Koda dit qu'il ne vous a pas vu depuis un moment.
ABSENCE_REMARQUABLE = timedelta(days=3)


def _derniere_venue(utilisateur):
    """
    Rend la date de la dernière activité enregistrée, ou None.

    Compétence visée : C20 (épreuve E5)
    Choix : la dernière SÉANCE close, pas la dernière connexion. Motivation :
    `last_login` dit qu'on est passé, pas qu'on a travaillé — et Koda parle de
    travail.
    """
    activite = derniere_activite(utilisateur)
    dates = []
    # Une erreur enregistrée EST une venue. Sans cette ligne, Koda pouvait
    # citer une notion tirée des erreurs à quelqu'un qu'il venait de déclarer
    # jamais vu : la branche qui nomme la notion était inatteignable pour un
    # apprenant qui n'a fait que des quiz. Trouvé par un test, pas à la
    # relecture.
    derniere_erreur = (
        UserMistake.objects.filter(user=utilisateur)
        .order_by("-timestamp").values_list("timestamp", flat=True).first()
    )
    if derniere_erreur is not None:
        dates.append(derniere_erreur)
    if activite["quiz"] is not None:
        dates.append(activite["quiz"].end_time)
    exercice = activite["exercice"]
    if exercice is not None:
        dates.append(exercice.completed_at or exercice.first_attempt_at)
    cours = activite["cours"]
    if cours is not None:
        dates.append(cours.created_at)
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def saluer(utilisateur):
    """
    Compose la phrase d'accueil de Koda.

    Compétence visée : C17 (épreuve E4)

    Choix : une phrase assemblée localement, jamais engendrée par le modèle.
    Motivation double. D'abord le quota : quinze générations par jour et par
    apprenant (décision 030) ; en dépenser une pour dire bonjour serait
    absurde. Ensuite la fiabilité : une phrase assemblée ne peut pas inventer
    une séance qui n'a pas eu lieu, un modèle si.

    Rend un dictionnaire : `phrase`, `detail` (peut être vide) et `humeur`,
    qui dit à l'interface quel état jouer.
    """
    pseudo = utilisateur.username
    venue = _derniere_venue(utilisateur)
    maintenant = timezone.now()

    if venue is None:
        return {
            "phrase": _("Salut %(pseudo)s !") % {"pseudo": pseudo},
            "detail": _("On commence quand tu veux."),
            "humeur": "clin",
        }

    absence = maintenant - venue
    if absence >= ABSENCE_REMARQUABLE:
        jours = absence.days
        return {
            "phrase": _("Te revoilà, %(pseudo)s !") % {"pseudo": pseudo},
            "detail": _("Ça faisait %(jours)s jours.") % {"jours": jours},
            "humeur": "clin",
        }

    a_revoir = notions_a_revoir(utilisateur, limite=1)
    if a_revoir:
        # La compétence si elle est rattachée, sinon le titre de l'exercice :
        # un exercice hors référentiel n'a pas de compétence (décision 027), et
        # Koda ne doit pas nommer une notion qui n'existe pas.
        entree = a_revoir[0]
        notion = (entree["competence"].intitule if entree["competence"]
                  else entree["exercice"].title)
        return {
            "phrase": _("Content de te revoir, %(pseudo)s !") % {"pseudo": pseudo},
            "detail": _("On avait laissé « %(notion)s » de côté.")
                      % {"notion": notion},
            "humeur": "parle",
        }

    # À défaut d'exercice résistant, les erreurs de quiz. Un apprenant qui n'a
    # fait que des quiz n'a aucune ligne dans `notions_a_revoir`, qui ne lit que
    # les exercices : sans ce recours, Koda n'aurait rien à lui dire alors que
    # la base sait quoi.
    du_quiz = erreurs_de_quiz(utilisateur, limite=1)
    if du_quiz:
        return {
            "phrase": _("Content de te revoir, %(pseudo)s !") % {"pseudo": pseudo},
            "detail": _("« %(notion)s », ça reste à consolider.")
                      % {"notion": du_quiz[0]["intitule"]},
            "humeur": "parle",
        }

    return {
        "phrase": _("Content de te revoir, %(pseudo)s !") % {"pseudo": pseudo},
        "detail": "",
        "humeur": "clin",
    }


def contexte_de_koda(requete):
    """
    Processeur de contexte : rend la salutation à tout gabarit qui l'affiche.

    Compétence visée : C17 (épreuve E4)

    Choix : `SimpleLazyObject`, comme le compteur de quota. Motivation : la
    salutation coûte trois requêtes ; sans paresse, toutes les pages les
    paieraient, y compris celles qui ne rendent pas le panneau du tuteur.

    Choix : `None` en cas d'échec, jamais d'exception. Motivation : Koda est
    un accompagnement. Une salutation qui ne se calcule pas ne doit pas faire
    tomber une page qui, sans elle, fonctionne.
    """
    def calculer():
        utilisateur = getattr(requete, "user", None)
        if utilisateur is None or not utilisateur.is_authenticated:
            return None
        try:
            return saluer(utilisateur)
        except Exception as exception:  # noqa: BLE001 — l'accueil n'est pas critique
            logger.warning(
                "Salutation de Koda non calculable (%s : %s).",
                type(exception).__name__, exception,
            )
            return None

    return {"salutation_koda": SimpleLazyObject(calculer)}
