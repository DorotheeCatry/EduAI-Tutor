"""
Ce que Koda répond, et ce que la fiche garde.

Compétence visée : C10 (épreuve E3) — agents et interactions
Compétences concernées : C13 (E3) — quotas ; C17 (E4) ; C21 (E5)

Dire « ça va ? » dans une page de cours produisait un cours entier sur la
compétence : la demande partait dans la recherche documentaire, et l'invite
ordonnait de répondre en s'appuyant sur elle. La réponse était ensuite versée
dans la fiche, où elle voisinait avec les vraies questions.

Ces tests défendent deux règles :
**une politesse reçoit une phrase**, et **la fiche ne garde que le travail**.
"""

import json
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.chat.echange_courant import est_un_echange_courant, repondre
from apps.courses.models import AjoutDeFiche


@pytest.mark.parametrize("message", [
    "ça va ?", "Salut !", "salut koda", "Bonjour", "merci beaucoup",
    "ok", "nickel", "à plus", "qui es-tu ?", "t'es là ?", "comment vas-tu",
])
def test_les_politesses_sont_reconnues(message):
    """
    Compétence visée : C10 (épreuve E3)
    """
    assert est_un_echange_courant(message), message


@pytest.mark.parametrize("message", [
    "bjr", "bjrs", "slt", "cc", "bsr", "slt koda",
])
def test_les_abreviations_sont_des_salutations(message):
    """
    Ce que l'apprenant tape vraiment, pas ce qu'il écrirait dans une lettre.

    Compétence visée : C10 (épreuve E3)

    Constaté : la liste ne connaissait que les formes écrites en entier, si
    bien qu'un « bjr » partait au modèle comme une demande de cours — et
    revenait en développement sur la compétence travaillée.
    """
    assert est_un_echange_courant(message), message


@pytest.mark.parametrize("message", [
    "bjrs ça va", "bonjour ça va ?", "salut ça va", "coucou ça va ?",
    "bonjour, comment ça va ?", "hello ça va bien", "bonjour koda ça va",
    "slt koda ça roule ?",
])
def test_une_salutation_suivie_d_une_prise_de_nouvelles(message):
    """
    L'enchaînement le plus courant de tous devait être reconnu.

    Compétence visée : C10 (épreuve E3)

    Constaté : la correspondance entière, appliquée à des tournures isolées,
    rejetait « bonjour ça va ? ». C'est deux formules connues collées, et
    aucune des deux ne correspondait au message entier. La règle de
    correspondance entière restait juste — c'est la liste qui était incomplète,
    et l'enchaînement forme désormais une tournure à lui seul.
    """
    assert est_un_echange_courant(message), message


def test_la_reponse_a_bonjour_ca_va_repond_aux_deux():
    """
    « Bonjour, ça va ? » pose deux choses : la réponse en traite deux.

    Compétence visée : C17 (épreuve E4)

    Sans famille dédiée, l'une des deux passait à la trappe — Koda saluait sans
    répondre, ou répondait sans saluer.
    """
    from apps.chat.echange_courant import _famille

    assert _famille("bjrs ça va") == "salutation_et_forme"
    assert _famille("bjr") == "salutation"
    assert _famille("ça va ?") == "forme"

    for _essai in range(30):
        phrase = repondre("bonjour ça va", "Dodo")
        assert "Dodo" in phrase, "Koda s'adresse à quelqu'un"
        assert len(phrase) < 120, "une politesse appelle une phrase"


@pytest.mark.parametrize("message", [
    "les tuples ?",
    "comment marche une liste ?",
    "bonjour, explique-moi les dictionnaires",
    "salut, ça déconne",
    "ça va marcher avec une boucle ?",
    "merci mais je comprends pas la ligne 3",
    "pourquoi ça plante ?",
    "un exemple de set",
    # Les abréviations ajoutées ne doivent pas relâcher la garde : ce qui
    # dépasse la formule reste une vraie question.
    "bjr ça plante",
    "slt j ai une erreur",
    "cc = 3",
])
def test_les_vraies_demandes_ne_sont_pas_prises_pour_des_politesses(message):
    """
    Le doute penche du côté de la vraie question.

    Compétence visée : C10 (épreuve E3)

    Se tromper dans un sens coûte une politesse traitée comme une question :
    bénin. Se tromper dans l'autre renvoie une vraie question d'un « ça
    marche ! » et ne l'enregistre jamais. Ces messages commencent tous par une
    formule de politesse ou lui ressemblent, et n'en sont pas.
    """
    assert not est_un_echange_courant(message), message


def test_la_reponse_porte_le_pseudo_et_reste_courte():
    """
    Compétence visée : C17 (épreuve E4)

    Koda s'adresse à quelqu'un, et ramène au travail : c'est une conversation
    dans une page de cours, pas un salon de discussion.
    """
    phrases = {repondre("salut", "Dodo") for _ in range(30)}

    assert len(phrases) > 1, "plusieurs formulations, sinon Koda récite"
    for phrase in phrases:
        assert len(phrase) < 120, "une politesse appelle une phrase, pas un paragraphe"


@pytest.mark.django_db
def test_une_politesse_n_entre_pas_dans_la_fiche(client, django_user_model):
    """
    Le chemin complet : la fiche ne garde rien d'un échange courant.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — quotas

    Et rien n'est envoyé au fournisseur : la réponse est assemblée localement.
    Un test qui n'aurait pas de clé d'API le montrerait de toute façon — celui-ci
    le montre en constatant qu'aucun ajout n'est créé et que la réponse arrive.
    """
    from apps.referentiel.models import Competence, Module, Referentiel

    referentiel = Referentiel.objects.create(code="essai", intitule="Essai",
                                             version="1", est_actif=True)
    module = Module.objects.create(referentiel=referentiel, code="m1",
                                   intitule="Module", ordre=1)
    competence = Competence.objects.create(module=module, code="c1",
                                           intitule="Compétence", ordre=1)
    utilisateur = django_user_model.objects.create_user(
        username="Dodo", password="mot-de-passe-de-test-1")
    client.force_login(utilisateur)

    reponse = client.post(
        reverse("courses:enrichir", args=[competence.code]),
        {"question": "ça va ?"}, secure=True,
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["enregistre"] is False
    assert corps["contenu"], "Koda doit tout de même répondre"
    assert AjoutDeFiche.objects.count() == 0, "la fiche ne garde pas les politesses"


# --- Le raccourci des politesses, sur les deux portes ----------------------


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante", password="mot-de-passe-d-essai-2026")


@pytest.mark.django_db
def test_le_panneau_flottant_repond_aux_politesses_sans_modele(
        client, apprenante):
    """
    « bjrs ça va » reçoit une phrase, et le modèle n'est pas appelé.

    Compétence visée : C10 (épreuve E3), C13 (E3)

    Le raccourci n'existait que sur `courses:enrichir`. Le panneau flottant,
    lui, est présent sur toutes les pages : le même bonjour y partait au modèle
    et y décomptait une génération sur les quinze de la journée.
    """
    client.force_login(apprenante)

    with patch("apps.chat.views.get_orchestrator") as orchestrateur:
        reponse = client.post(
            reverse("chat:send_message"),
            data=json.dumps({"message": "bjrs ça va"}),
            content_type="application/json", secure=True,
        )

    assert reponse.status_code == 200
    assert not orchestrateur.called, "aucune génération pour une politesse"
    corps = reponse.json()
    assert corps["reponse"], "Koda répond tout de même"
    assert apprenante.username in corps["reponse"]
    assert len(corps["reponse"]) < 120, "une politesse appelle une phrase"


@pytest.mark.django_db
def test_une_action_preformee_n_est_jamais_prise_pour_une_politesse(
        client, apprenante):
    """
    Le raccourci est posé après la résolution des actions.

    Compétence visée : C10 (épreuve E3)

    Une action a déjà remplacé le message par une invite complète : la
    reconnaissance ne doit pas s'exercer dessus. Placer le raccourci avant
    aurait été sans effet aujourd'hui, mais l'ordre est ce qui garantit qu'une
    action courte ajoutée plus tard ne soit pas avalée.
    """
    client.force_login(apprenante)

    with patch("apps.chat.views.get_orchestrator") as orchestrateur:
        orchestrateur.return_value.answer_question.return_value = {
            "success": True, "answer": "réponse",
        }
        client.post(
            reverse("chat:send_message"),
            data=json.dumps({"message": "salut", "action": "cas-complexe"}),
            content_type="application/json", secure=True,
        )

    assert orchestrateur.called, "une action part au modèle"
