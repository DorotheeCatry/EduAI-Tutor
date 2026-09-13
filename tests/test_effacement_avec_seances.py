"""
L'effacement d'un compte emporte ses séances d'apprentissage.

Compétence visée : C4 (épreuve E1) — droit à l'effacement
Compétences concernées : C21 (E5) ; C18 (E4) ; C13 (E3)

La suppression de compte échouait pour **tout compte ayant utilisé
l'application**, sur une violation de clé étrangère :

    IntegrityError: update or delete on table "users_kodauser" violates
    foreign key constraint "agents_learningsession_user_id_..."

`apps/agents/` n'a pas de `models.py` : ses deux modèles vivent dans
`agent_watcher.py`, et Django n'importe automatiquement que
`<application>/models.py`. Ils n'étaient donc pas enregistrés au moment où
Django calcule et met en cache `User._meta.related_objects` — la cascade était
inconnue, et PostgreSQL refusait.

Voir l'incident 024.

**Pourquoi les neuf tests d'effacement existants ne l'ont jamais vu** : ils ne
créent aucune séance d'apprentissage. La clé étrangère qui casse n'était jamais
éprouvée.
"""

import subprocess
import sys
import textwrap

import pytest
from django.contrib.auth import get_user_model

from apps.agents.agent_watcher import LearningSession, UserMistake


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante-effacement",
        email="apprenante-effacement@exemple.test",
        password="mot-de-passe-d-essai-2026")


# --- Le cas réel ------------------------------------------------------------


@pytest.mark.django_db
def test_un_compte_ayant_travaille_peut_etre_efface(apprenante):
    """
    Un compte avec séances et erreurs s'efface, et n'en laisse aucune.

    Compétence visée : C4 (épreuve E1), C21 (E5)

    C'est le cas de **tout apprenant réel** : ouvrir un quiz, poser une question
    à Koda ou lancer une génération crée une `LearningSession`. Les tests
    d'effacement existants créaient un avatar, des exercices et des sessions
    Django — jamais cela.
    """
    from apps.users.effacement import supprimer_compte

    seance = LearningSession.objects.create(
        user=apprenante, topic="les listes", activity_type="quiz")
    UserMistake.objects.create(
        user=apprenante, topic="les listes", mistake_type="quiz_wrong_answer",
        question="Quelle est la sortie ?", user_answer="A", correct_answer="B")

    identifiant = apprenante.id
    rapport = supprimer_compte(apprenante)

    assert rapport.conforme, rapport.subsiste
    assert not LearningSession.objects.filter(user_id=identifiant).exists(), (
        "les séances d'apprentissage doivent partir avec le compte"
    )
    assert not UserMistake.objects.filter(user_id=identifiant).exists()
    assert not get_user_model().objects.filter(id=identifiant).exists()
    # La séance a bien été créée avant, sans quoi le test ne prouverait rien.
    assert seance.pk is not None


@pytest.mark.django_db
def test_l_inventaire_annonce_les_seances_avant_de_les_effacer(apprenante):
    """
    Ce que l'effacement va retirer est dit avant de le retirer.

    Compétence visée : C4 (épreuve E1)

    L'inventaire est ce que l'apprenant lit avant de confirmer. Une donnée
    supprimée sans avoir été annoncée n'est pas un effacement transparent.
    """
    from apps.users.effacement import inventorier

    LearningSession.objects.create(
        user=apprenante, topic="les boucles", activity_type="chat")

    UserMistake.objects.create(
        user=apprenante, topic="les boucles", mistake_type="quiz_wrong_answer",
        question="Combien de tours ?", user_answer="3", correct_answer="4")

    inventaire = inventorier(apprenante.id)

    assert inventaire.get("seances_apprentissage") == 1, (
        "l'inventaire doit compter les séances : %s" % inventaire
    )
    assert inventaire.get("erreurs_relevees") == 1, (
        "et les notions manquées, qui disent ce que l'apprenant a raté"
    )
    # Les fiches de compétence y figurent aussi : ce que l'apprenant a demandé
    # à Koda, et les réponses conservées.
    assert "fiches_de_competence" in inventaire
    assert "ajouts_de_fiche" in inventaire


# --- Le garde-fou structurel ------------------------------------------------


def test_les_modeles_des_agents_sont_enregistres_au_demarrage():
    """
    La cascade est connue de Django **sans import explicite préalable**.

    Compétence visée : C4 (épreuve E1), C18 (E4)

    **Ce test s'exécute dans un processus neuf, et c'est indispensable.** Dans
    la suite, d'autres modules importent `agent_watcher` avant celui-ci : la
    relation y est donc déjà enregistrée, et un contrôle fait ici passerait
    même si le défaut était de retour. C'est exactement ce qui s'est produit —
    neuf tests d'effacement au vert sur une route cassée en production.

    Le sous-processus reproduit la condition réelle : un `django.setup()`
    frais, sans rien d'autre d'importé.
    """
    programme = textwrap.dedent("""
        import os, django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eduai_project.settings")
        django.setup()
        from django.contrib.auth import get_user_model
        relations = sorted(
            r.related_model.__name__
            for r in get_user_model()._meta.related_objects
            if r.related_model._meta.app_label == "agents"
        )
        print(",".join(relations))
    """)

    resultat = subprocess.run(
        [sys.executable, "-c", programme],
        capture_output=True, text=True, timeout=180,
    )

    assert resultat.returncode == 0, resultat.stderr[-800:]
    relations = resultat.stdout.strip().splitlines()[-1] if resultat.stdout.strip() else ""
    assert relations == "LearningSession,UserMistake", (
        "les modèles de `apps/agents/` doivent être enregistrés au démarrage — "
        "sans quoi la suppression d'un compte ne cascade pas vers eux. "
        "Relevé : %r" % relations
    )


def test_le_ready_de_l_application_importe_ses_modeles():
    """
    L'import est dans `ready()`, là où Django le prévoit.

    Compétence visée : C18 (épreuve E4)

    Contrôle de lisibilité doublant le précédent : celui-ci dit **où** regarder
    quand le sous-processus échoue, ce qu'un écart de relations ne dit pas.
    """
    from pathlib import Path

    source = Path("apps/agents/apps.py").read_text(encoding="utf-8")

    assert "from apps.agents import agent_watcher" in source
    assert "def ready" in source
    assert source.index("def ready") < source.index("from apps.agents import agent_watcher")
