"""
Effacement d'un compte apprenant et vérification de son effet.

Compétence visée : C4 (épreuve E1) — droit à l'effacement, article 17 du RGPD
Compétence visée : C17 (épreuve E4) — fonction de l'application

--- Pourquoi ce module existe séparément d'une vue ---

Un effacement partiel est **pire qu'un effacement absent**, parce qu'il donne
l'illusion d'être conforme. Une vue qui appellerait `user.delete()` et
afficherait « votre compte a été supprimé » serait exactement cela : la
suppression en cascade de Django efface les lignes qui référencent
l'utilisateur, et **rien d'autre**. Elle laisse derrière elle :

  - le fichier d'avatar sur le disque, qu'aucune cascade ne touche ;
  - les sessions ouvertes, stockées dans une table sans clé étrangère vers
    l'utilisateur ;
  - éventuellement des lignes rattachées par un identifiant non contraint.

Ce module fait donc trois choses distinctes, et la troisième est la seule qui
compte : il inventorie avant, il efface, puis il **relit la base et le disque**
pour établir ce qui subsiste. Le rapport qu'il rend est un constat, pas une
intention — c'est la règle que ce projet applique depuis ses quatre incidents.

--- Ce qu'il ne fait pas, et pourquoi c'est dit ---

La suppression d'un utilisateur qui a hébergé une salle de quiz emporte la
salle, donc les réponses des AUTRES participants. C'est une conséquence de la
cascade déclarée sur `GameRoom.host`, et elle n'est pas corrigée ici : la
rendre nullable modifierait le comportement du quiz à dix jours du rendu. Le
rapport la mesure et l'annonce plutôt que de la laisser se produire en silence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Avatars livrés avec l'application, communs à tous les comptes.
#:
#: Choix : ne jamais supprimer ces fichiers. Motivation : ils ne sont pas la
#: donnée d'un utilisateur mais une ressource de l'application. Les effacer
#: casserait l'affichage de tous les autres comptes.
AVATARS_PARTAGES = {"koda_base.png"}


@dataclass
class RapportEffacement:
    """
    Ce qui a été trouvé, ce qui a été supprimé, ce qui subsiste.

    Compétence visée : C4 (épreuve E1)

    `subsiste` est le champ décisif : s'il n'est pas vide, l'effacement n'est
    pas conforme, quoi qu'aient fait les étapes précédentes.
    """

    identifiant: int
    inventaire_avant: dict[str, int] = field(default_factory=dict)
    supprime: dict[str, int] = field(default_factory=dict)
    subsiste: dict[str, int] = field(default_factory=dict)
    fichiers_supprimes: list[str] = field(default_factory=list)
    fichiers_subsistants: list[str] = field(default_factory=list)
    effets_collateraux: dict[str, int] = field(default_factory=dict)

    @property
    def conforme(self) -> bool:
        """Vrai si rien ne subsiste, ni en base ni sur le disque."""
        return not self.subsiste and not self.fichiers_subsistants


# --- Inventaire ------------------------------------------------------------

def inventorier(identifiant: int) -> dict[str, int]:
    """
    Rend le décompte de tout ce qui est rattaché à un utilisateur.

    Compétence visée : C4 (épreuve E1)

    Exposé publiquement pour que l'écran de confirmation puisse annoncer à
    l'utilisateur ce qu'il perdra. L'article 12.1 impose une information
    claire : « votre compte sera supprimé » n'est pas claire si les cours, les
    soumissions et la progression le sont aussi sans être nommés.
    """
    return _compteurs(identifiant)


def _compteurs(identifiant: int) -> dict[str, int]:
    """
    Compte tout ce qui est rattaché à un identifiant d'utilisateur.

    Compétence visée : C4 (épreuve E1)

    Choix : des requêtes explicites, modèle par modèle, plutôt qu'un parcours
    générique des relations inverses. Motivation : un parcours générique
    donnerait l'illusion de l'exhaustivité tout en manquant ce qui n'est pas
    déclaré comme relation — les sessions et les fichiers, précisément les deux
    choses qu'une cascade oublie. Une liste explicite se relit et se complète.
    """
    from apps.courses.models import Course
    from apps.exercises.models import (
        Exercise,
        ExerciseSubmission,
        UserExerciseProgress,
    )
    from apps.quiz.models import GameParticipant, GameRoom
    from apps.users.models import KodaUser, UserProgress

    return {
        "compte": KodaUser.objects.filter(pk=identifiant).count(),
        "progression": UserProgress.objects.filter(user_id=identifiant).count(),
        "cours_crees": Course.objects.filter(created_by_id=identifiant).count(),
        "exercices_crees": Exercise.objects.filter(created_by_id=identifiant).count(),
        "soumissions": ExerciseSubmission.objects.filter(user_id=identifiant).count(),
        "progression_exercices": UserExerciseProgress.objects.filter(
            user_id=identifiant).count(),
        "salles_hebergees": GameRoom.objects.filter(host_id=identifiant).count(),
        "participations_quiz": GameParticipant.objects.filter(
            user_id=identifiant).count(),
        "sessions": _compter_sessions(identifiant),
    }


def _compter_sessions(identifiant: int) -> int:
    """
    Compte les sessions ouvertes appartenant à un utilisateur.

    Compétence visée : C4 (épreuve E1)

    La table des sessions ne porte **aucune clé étrangère** vers l'utilisateur :
    l'identifiant est enfoui dans une charge sérialisée. Aucune cascade ne peut
    donc l'atteindre, et c'est la raison pour laquelle une session survit à la
    suppression du compte — en laissant, jusqu'à son expiration, une trace
    rattachable à une personne dont on a par ailleurs effacé le dossier.
    """
    return len(_sessions_de(identifiant))


def _sessions_de(identifiant: int) -> list[Session]:
    """
    Rend les sessions non expirées appartenant à un utilisateur.

    Compétence visée : C4 (épreuve E1)
    """
    trouvees = []
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            donnees = session.get_decoded()
        except Exception:  # noqa: BLE001 — session corrompue : elle n'est à personne
            continue
        if str(donnees.get("_auth_user_id")) == str(identifiant):
            trouvees.append(session)
    return trouvees


def _chemin_avatar(utilisateur) -> Path | None:
    """
    Rend le chemin du fichier d'avatar propre à l'utilisateur, s'il en a un.

    Compétence visée : C4 (épreuve E1)

    Rend None pour un avatar partagé : celui-ci appartient à l'application, non
    à la personne, et le supprimer casserait l'affichage des autres comptes.
    """
    champ = getattr(utilisateur, "avatar", None)
    if not champ or not getattr(champ, "name", ""):
        return None
    if Path(champ.name).name in AVATARS_PARTAGES:
        return None
    chemin = Path(settings.MEDIA_ROOT) / champ.name
    return chemin if chemin.is_file() else None


# --- Effacement ------------------------------------------------------------

def supprimer_compte(utilisateur) -> RapportEffacement:
    """
    Efface un compte et tout ce qui s'y rattache, puis constate le résultat.

    Compétence visée : C4 (épreuve E1) — article 17 du RGPD

    L'ordre des opérations n'est pas indifférent : le chemin de l'avatar et les
    sessions doivent être relevés **avant** la suppression de l'utilisateur, qui
    rend l'objet inutilisable et efface le champ où le chemin était inscrit.

    Rend un rapport dont `conforme` vaut vrai seulement si plus rien ne subsiste
    — ni en base, ni sur le disque. L'appelant doit le vérifier : ce module ne
    lève pas d'exception sur un effacement incomplet, il le rapporte.
    """
    identifiant = utilisateur.pk
    rapport = RapportEffacement(identifiant=identifiant)
    rapport.inventaire_avant = _compteurs(identifiant)

    # 1. Le fichier d'avatar. Aucune cascade ne l'atteint : Django supprime la
    #    ligne, pas le fichier qu'elle désigne.
    avatar = _chemin_avatar(utilisateur)

    # 2. Les sessions. Relevées avant, supprimées avant : une session encore
    #    ouverte après la suppression du compte laisserait un utilisateur
    #    authentifié sans compte, état que rien ne gère.
    sessions = _sessions_de(identifiant)
    for session in sessions:
        session.delete()
    rapport.supprime["sessions"] = len(sessions)

    # 3. Les effets sur les données d'AUTRUI, mesurés avant qu'ils ne se
    #    produisent. La cascade sur GameRoom.host emporte les salles hébergées,
    #    donc les participations et réponses des autres joueurs.
    rapport.effets_collateraux = _mesurer_effets_collateraux(identifiant)

    # 4. Le compte, et tout ce que la cascade emporte.
    utilisateur.delete()

    # 5. Le fichier, une fois la ligne partie.
    if avatar is not None:
        try:
            avatar.unlink()
            rapport.fichiers_supprimes.append(str(avatar))
        except OSError as exception:
            # Un fichier qu'on ne peut pas supprimer est un échec d'effacement,
            # pas un détail : il est consigné comme subsistant.
            rapport.fichiers_subsistants.append(str(avatar))
            logger.error("avatar non supprimé (%s) : %s", avatar, exception)

    # 6. Le constat. On relit la base et le disque : c'est la seule étape dont
    #    le résultat vaille quelque chose.
    apres = _compteurs(identifiant)
    rapport.subsiste = {cle: valeur for cle, valeur in apres.items() if valeur}
    rapport.supprime.update({
        cle: rapport.inventaire_avant[cle] - apres[cle]
        for cle in apres
        if cle != "sessions"
    })
    if avatar is not None and avatar.exists():
        if str(avatar) not in rapport.fichiers_subsistants:
            rapport.fichiers_subsistants.append(str(avatar))

    if rapport.conforme:
        logger.info("compte %s effacé, aucun reliquat constaté", identifiant)
    else:
        logger.error(
            "compte %s : effacement INCOMPLET — subsiste %s, fichiers %s",
            identifiant, rapport.subsiste, rapport.fichiers_subsistants,
        )
    return rapport


def _mesurer_effets_collateraux(identifiant: int) -> dict[str, int]:
    """
    Compte ce que l'effacement retirera aux AUTRES utilisateurs.

    Compétence visée : C4 (épreuve E1)

    L'article 17 donne un droit à l'effacement de SES données. Il ne donne pas
    le droit d'emporter celles d'autrui. Ici, la cascade déclarée sur l'hôte
    d'une salle de quiz supprime la salle, donc les participations et les
    réponses des autres joueurs.

    Ce n'est pas corrigé — rendre l'hôte nullable modifierait le comportement du
    quiz à dix jours du rendu — mais c'est mesuré et annoncé. Une conséquence
    connue et documentée n'est pas du même ordre qu'une conséquence subie.
    """
    from apps.quiz.models import GameAnswer, GameParticipant, GameRoom

    salles = GameRoom.objects.filter(host_id=identifiant)
    participants_autres = GameParticipant.objects.filter(
        room__in=salles).exclude(user_id=identifiant)
    return {
        "salles_supprimees": salles.count(),
        "participations_d_autrui_perdues": participants_autres.count(),
        "reponses_d_autrui_perdues": GameAnswer.objects.filter(
            participant__in=participants_autres).count(),
    }
