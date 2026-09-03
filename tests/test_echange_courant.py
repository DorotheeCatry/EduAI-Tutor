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
    "les tuples ?",
    "comment marche une liste ?",
    "bonjour, explique-moi les dictionnaires",
    "salut, ça déconne",
    "ça va marcher avec une boucle ?",
    "merci mais je comprends pas la ligne 3",
    "pourquoi ça plante ?",
    "un exemple de set",
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
