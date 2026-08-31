"""
Règle de progression : ce qu'un apprenant a acquis, et comment on le sait.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — requêtes ; C13 (E3) — accessibilité ; C20 (E5)

La règle tient en trois phrases, une par niveau, et chacune est vérifiable par
une requête. C'est la contrainte que le chantier imposait, et elle a écarté
d'elle-même les scores composites pondérés : un indicateur dont on ne peut pas
dire ce qu'il mesure ne mesure rien.

    Niveau 1 — imiter     : un exercice rattaché à la compétence a été réussi.
    Niveau 2 — adapter    : trois exercices distincts rattachés à la compétence
                            ont été réussis.
    Niveau 3 — transposer : NON MESURÉ en l'état. Voir plus bas.

Ce que la règle ne prend PAS en compte, et pourquoi :

- **Les quiz.** Ils ne font progresser aucun niveau. Les trois niveaux nomment
  des actes de production — imiter, adapter, transposer — quand un questionnaire
  mesure la reconnaissance. Faire attester une production par une reconnaissance
  n'aurait pas de sens. Les quiz alimentent le bloc « à revoir », dont ils sont
  la seule source ; ils révèlent une lacune, ils ne certifient pas une
  acquisition.

- **Le nombre de tentatives.** Un exercice réussi à la douzième tentative
  compte comme un autre. Ce que les niveaux mesurent est « sait produire », pas
  « sait produire vite » : exiger la réussite immédiate punirait l'apprentissage
  par essais, qui est la façon dont on apprend à programmer. Le nombre de
  tentatives sert ailleurs — au bloc « à revoir », qui pose une autre question.

- **La difficulté choisie.** L'apprenant la choisit lui-même ; en faire un
  critère allongerait la règle sans la rendre plus juste.
"""

from django.db.models import Count, OuterRef, Subquery

from apps.exercises.models import ExerciseSubmission, UserExerciseProgress
from apps.referentiel.models import Competence
from apps.referentiel.services import referentiel_actif

#: Nombre d'exercices distincts réussis qui fait passer au niveau 2.
#:
#: Trois plutôt que deux : deux réussites peuvent tenir au hasard d'un énoncé
#: proche du premier. Trois plutôt que cinq : au-delà, on mesure l'assiduité
#: plus que la compétence, et une démonstration devrait produire cinq exercices
#: réussis par compétence pour montrer un seul niveau 2.
SEUIL_NIVEAU_ADAPTER = 3

#: États possibles d'un niveau, pour l'affichage.
#:
#: « Non mesuré » est distinct de « non atteint », et l'interface doit les
#: distinguer autrement que par la couleur : le premier dit que le dispositif
#: ne sait pas conclure, le second que l'apprenant n'y est pas encore. Les
#: confondre ferait porter à l'apprenant une limite qui est la nôtre.
ATTEINT = "atteint"
NON_ATTEINT = "non_atteint"
NON_MESURE = "non_mesure"


def _exercices_reussis_par_competence(utilisateur):
    """
    Compte, par compétence, les exercices distincts réussis par l'apprenant.

    Compétence visée : C4 (épreuve E1) — requêtes

    Choix : `UserExerciseProgress.is_completed`, et non les soumissions.
    Motivation : cette table porte une ligne par couple apprenant/exercice, ce
    qui rend le décompte des exercices DISTINCTS immédiat. Compter les
    soumissions réussies compterait plusieurs fois le même exercice résolu puis
    resoumis.

    Piège écarté : `UserExerciseProgress` est créé à l'OUVERTURE d'un exercice,
    pas à la première soumission. Le filtre `is_completed=True` est donc ce qui
    sépare l'activité réelle de la simple consultation — compter les
    progressions dirait combien d'exercices ont été regardés.
    """
    lignes = (
        UserExerciseProgress.objects
        .filter(user=utilisateur,
                is_completed=True,
                exercise__competence__isnull=False)
        .values("exercise__competence_id")
        .annotate(reussis=Count("exercise_id", distinct=True))
    )
    return {ligne["exercise__competence_id"]: ligne["reussis"] for ligne in lignes}


def _reussis_du_premier_coup_par_competence(utilisateur):
    """
    Compte, par compétence, les exercices réussis à la première soumission.

    Compétence visée : C4 (épreuve E1)

    Cet indicateur est AFFICHÉ mais ne donne aucun niveau. Il dit que
    l'apprenant a produit une solution correcte sans tâtonner, ce qui est une
    information réelle — mais pas une transposition, puisque rien n'établit que
    l'énoncé constituait un contexte nouveau.

    Choix : la première soumission relue dans `ExerciseSubmission`, et non
    `UserExerciseProgress.attempts_count`. Motivation : ce compteur s'incrémente
    à CHAQUE soumission, y compris après la réussite. Un apprenant qui réussit
    du premier coup puis retravaille son code par curiosité y afficherait trois
    tentatives. Le compteur dit le nombre total de soumissions, jamais le nombre
    de tentatives avant réussite — la distinction a été constatée le 31/08/2026,
    après avoir été supposée dans l'autre sens.
    """
    statut_de_la_premiere = (
        ExerciseSubmission.objects
        .filter(user=OuterRef("user"), exercise=OuterRef("exercise"))
        .order_by("submitted_at")
        .values("status")[:1]
    )
    lignes = (
        UserExerciseProgress.objects
        .filter(user=utilisateur,
                is_completed=True,
                exercise__competence__isnull=False)
        .annotate(statut_premiere=Subquery(statut_de_la_premiere))
        .filter(statut_premiere="success")
        .values("exercise__competence_id")
        .annotate(reussis=Count("exercise_id", distinct=True))
    )
    return {ligne["exercise__competence_id"]: ligne["reussis"] for ligne in lignes}


def niveau_atteint(exercices_reussis):
    """
    Rend le niveau atteint — 0, 1 ou 2 — pour un nombre d'exercices réussis.

    Compétence visée : C17 (épreuve E4)

    Le niveau 3 n'est jamais rendu ici : il n'est pas mesuré, et le prétendre
    reviendrait à nommer « transposition » une accumulation.
    """
    if exercices_reussis >= SEUIL_NIVEAU_ADAPTER:
        return 2
    if exercices_reussis >= 1:
        return 1
    return 0


def progression_par_competence(utilisateur):
    """
    Rend l'état de chaque compétence du référentiel actif, pour un apprenant.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — accessibilité

    Deux requêtes au total, quel que soit le nombre de compétences : les
    décomptes sont ramenés en une fois puis rapprochés en mémoire. Une requête
    par compétence rendrait la page d'accueil coûteuse à mesure que le
    référentiel grandit.

    Chaque entrée porte l'état des trois niveaux, `non_mesure` compris, pour
    que l'affichage n'ait pas à décider — et pour qu'il puisse distinguer
    « pas encore atteint » de « nous ne savons pas mesurer ».
    """
    referentiel = referentiel_actif()
    if referentiel is None:
        return []

    reussis = _exercices_reussis_par_competence(utilisateur)
    premier_coup = _reussis_du_premier_coup_par_competence(utilisateur)

    competences = (
        Competence.objects
        .filter(module__referentiel=referentiel)
        .select_related("module")
        .order_by("module__ordre", "module__code", "ordre", "code")
    )

    progression = []
    for competence in competences:
        nombre = reussis.get(competence.id, 0)
        atteint = niveau_atteint(nombre)
        progression.append({
            "competence": competence,
            "module": competence.module,
            "exercices_reussis": nombre,
            "reussis_du_premier_coup": premier_coup.get(competence.id, 0),
            "niveau_atteint": atteint,
            "restant_avant_niveau_2": max(0, SEUIL_NIVEAU_ADAPTER - nombre),
            "etats": {
                1: ATTEINT if atteint >= 1 else NON_ATTEINT,
                2: ATTEINT if atteint >= 2 else NON_ATTEINT,
                # Jamais ATTEINT, jamais NON_ATTEINT : le dispositif ne sait
                # pas conclure, et l'écrire est plus honnête que de trancher.
                3: NON_MESURE,
            },
        })
    return progression


def resume_par_module(utilisateur):
    """
    Résume la progression module par module, pour la page d'accueil.

    Compétence visée : C17 (épreuve E4)

    Rend de quoi écrire une ligne du genre :

        Python — 4 compétences sur 7 au niveau 1, 2 au niveau 2

    Le détail complet vit sur la page Performance ; l'accueil résume.
    """
    resume = {}
    for entree in progression_par_competence(utilisateur):
        module = entree["module"]
        ligne = resume.setdefault(module.id, {
            "module": module,
            "competences": 0,
            "au_niveau_1": 0,
            "au_niveau_2": 0,
            "reussis_du_premier_coup": 0,
        })
        ligne["competences"] += 1
        # Un apprenant au niveau 2 est aussi au niveau 1 : les paliers sont
        # cumulatifs, et un décompte qui les rendrait exclusifs ferait
        # « disparaître » une compétence du niveau 1 le jour où elle progresse.
        if entree["niveau_atteint"] >= 1:
            ligne["au_niveau_1"] += 1
        if entree["niveau_atteint"] >= 2:
            ligne["au_niveau_2"] += 1
        ligne["reussis_du_premier_coup"] += entree["reussis_du_premier_coup"]

    return list(resume.values())
