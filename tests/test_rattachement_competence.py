"""
Tests du rattachement d'un exercice à une compétence du référentiel.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C4 (E1)

Ces tests partent du **formulaire réel**, par une requête sur l'URL de
génération, et vérifient ce que la base contient ensuite. C'est la parade à la
famille C des motifs du projet : une clé étrangère que rien ne renseigne est
un rattachement qui n'existe pas, et une couverture qui appellerait le modèle
directement ne le dirait pas.

La génération appelle un modèle de langage. Il est remplacé ici : ce qui est
éprouvé est le rattachement, pas la qualité de l'exercice engendré.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.exercises.models import Exercise
from apps.referentiel.models import Competence

FICHIER_LIVRE = "apps/referentiel/donnees/eduai-2026.json"

EXERCICE_ENGENDRE = {
    "success": True,
    "exercise": {
        "title": "Parcourir une liste",
        "description": "Écrire une fonction qui parcourt une liste.",
        "starter_code": "def parcourir(liste):\n    pass\n",
        "solution": "def parcourir(liste):\n    return list(liste)\n",
        "tests": [{"input": "parcourir([1])", "expected": "[1]"}],
    },
}


@pytest.fixture
def referentiel_charge():
    """Le référentiel livré, importé et actif, comme en exploitation."""
    call_command("importer_referentiel", FICHIER_LIVRE, "--activer", stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenant(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante_rattachement",
        email="rattachement@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )


def _generer(client, **champs):
    """Envoie le formulaire de génération, tel qu'un apprenant le remplit."""
    with patch("apps.exercises.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.generate_exercise.return_value = EXERCICE_ENGENDRE
        orchestrateur.return_value.answer_question.return_value = {
            "success": True, "answer": "```json\n{}\n```",
        }
        return client.post(reverse("exercises:generate"), champs, secure=True)


@pytest.mark.django_db
def test_le_choix_d_une_competence_rattache_l_exercice(
        client, apprenant, referentiel_charge):
    """
    Un exercice engendré après choix d'une compétence lui est rattaché.

    Compétence visée : C17 (épreuve E4)

    C'est le point où la famille C guette : une clé étrangère ajoutée et que
    personne ne renseigne. Ce test part du formulaire pour cette raison.
    """
    client.force_login(apprenant)

    _generer(client, competence="collections", difficulty="beginner")

    exercice = Exercise.objects.latest("created_at")
    assert exercice.competence == referentiel_charge
    assert exercice.topic == referentiel_charge.intitule, (
        "le sujet transmis au modèle doit être celui de la compétence choisie"
    )


@pytest.mark.django_db
def test_un_sujet_libre_laisse_l_exercice_hors_referentiel(
        client, apprenant, referentiel_charge):
    """
    Sans choix de compétence, l'exercice n'est rattaché à rien.

    Compétence visée : C17 (épreuve E4)

    Et surtout : il n'est pas rattaché « au plus proche ». Un rattachement
    approché produirait une progression fausse que rien ne signalerait.
    """
    client.force_login(apprenant)

    _generer(client, topic="les listes en python", difficulty="beginner")

    exercice = Exercise.objects.latest("created_at")
    assert exercice.competence is None
    assert exercice.topic == "les listes en python"


@pytest.mark.django_db
def test_un_code_de_competence_inconnu_ne_rattache_rien(
        client, apprenant, referentiel_charge):
    """
    Un code absent du référentiel actif laisse l'exercice hors référentiel.

    Compétence visée : C17 (épreuve E4)

    Le cas se produit quand le référentiel est rechargé entre l'affichage du
    formulaire et son envoi, ou quand le formulaire est modifié. Rattacher au
    plus proche serait pire que ne rien rattacher.
    """
    client.force_login(apprenant)

    _generer(client, competence="competence-qui-n-existe-pas",
             topic="un sujet libre", difficulty="beginner")

    exercice = Exercise.objects.latest("created_at")
    assert exercice.competence is None


@pytest.mark.django_db
def test_une_competence_d_un_referentiel_inactif_ne_rattache_rien(
        client, apprenant, referentiel_charge, tmp_path):
    """
    Seul le référentiel actif peut rattacher.

    Compétence visée : C17 (épreuve E4)

    Deux référentiels coexistent — c'est prévu. Rattacher à celui qui n'est pas
    affiché produirait une progression invisible.
    """
    import json
    autre = tmp_path / "autre.json"
    autre.write_text(json.dumps({
        "code": "autre-organisme", "intitule": "Autre",
        "modules": [{"code": "m", "intitule": "M", "competences": [
            {"code": "collections", "intitule": "Homonyme"}]}],
    }, ensure_ascii=False), encoding="utf-8")
    call_command("importer_referentiel", str(autre), "--activer", stdout=StringIO())

    client.force_login(apprenant)
    _generer(client, competence="collections", difficulty="beginner")

    exercice = Exercise.objects.latest("created_at")
    assert exercice.competence is not None
    assert exercice.competence.module.referentiel.code == "autre-organisme", (
        "le rattachement doit suivre le référentiel ACTIF"
    )


@pytest.mark.django_db
def test_ni_competence_ni_sujet_est_refuse(client, apprenant, referentiel_charge):
    """
    Un formulaire vide ne crée pas d'exercice.

    Compétence visée : C17 (épreuve E4)
    """
    client.force_login(apprenant)

    _generer(client, difficulty="beginner")

    assert Exercise.objects.count() == 0


@pytest.mark.django_db
def test_le_formulaire_propose_les_competences_du_referentiel_actif(
        client, apprenant, referentiel_charge):
    """
    La page de génération affiche les compétences, groupées par module.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Sans ce menu, la clé étrangère resterait vide sur tous les exercices : le
    chemin de remplissage passe par cette page et par elle seule.
    """
    client.force_login(apprenant)

    contenu = client.get(reverse("exercises:list"), secure=True).content.decode("utf-8")

    assert 'name="competence"' in contenu
    assert referentiel_charge.intitule in contenu
    assert referentiel_charge.module.intitule in contenu
    assert "hors référentiel" in contenu.lower(), (
        "l'option « aucune compétence » doit être proposée explicitement"
    )


@pytest.mark.django_db
def test_l_absence_de_rattachement_est_affichee(client, apprenant, referentiel_charge):
    """
    Un exercice hors référentiel le dit sur la page.

    Compétence visée : C13 (épreuve E3) — accessibilité
    Compétence visée : C17 (épreuve E4)

    Le taire ferait chercher longtemps pourquoi une compétence n'avance pas.
    L'information est portée par le texte, jamais par la seule couleur.
    """
    client.force_login(apprenant)
    _generer(client, topic="un sujet hors cadre", difficulty="beginner")

    contenu = client.get(reverse("exercises:list"), secure=True).content.decode("utf-8")

    assert "Hors référentiel" in contenu
    assert "ne compte pas dans la progression" in contenu


@pytest.mark.django_db
def test_retirer_une_competence_du_referentiel_ne_supprime_pas_l_exercice(
        client, apprenant, referentiel_charge, tmp_path):
    """
    Une compétence retirée laisse l'exercice, redevenu hors référentiel.

    Compétence visée : C4 (épreuve E1) — intégrité

    `SET_NULL` plutôt que `CASCADE` : retirer une compétence d'un référentiel
    ne doit pas effacer le travail qui s'y rattachait.
    """
    client.force_login(apprenant)
    _generer(client, competence="collections", difficulty="beginner")
    exercice = Exercise.objects.latest("created_at")

    referentiel_charge.delete()

    exercice.refresh_from_db()
    assert Exercise.objects.filter(pk=exercice.pk).exists()
    assert exercice.competence is None
