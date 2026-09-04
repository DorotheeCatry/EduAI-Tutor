"""
La mention d'interaction avec une intelligence artificielle.

Compétence visée : C6 (épreuve E2) — impact concret de la veille réglementaire
Compétences concernées : C17 (E4) — application web ; C13 (E3) — accessibilité

L'article 50 du règlement (UE) 2024/1689 impose d'informer une personne qu'elle
interagit avec un système d'intelligence artificielle, au plus tard lors de la
première interaction. La veille réglementaire du 28/08/2026 établit que le
tuteur relève du risque limité et que cette obligation s'applique depuis le
2 août 2026 ; la décision 046 en tire l'implémentation.

Ces tests existent parce qu'une obligation réglementaire tenue par une seule
ligne de gabarit est une obligation qu'un remaniement d'interface peut faire
disparaître sans que rien ne le signale. Le premier rapport E2 décrivait cette
mention comme un impact de la veille alors qu'elle n'était nulle part : c'est
exactement l'écart que ces tests interdisent de reproduire.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

FRAGMENT = Path("templates/components/mention_ia.html")
PANNEAU = Path("templates/components/tuteur.html")
PAGE_DE_COURS = Path("apps/courses/templates/courses/page_de_cours.html")

# Les deux surfaces où l'apprenant converse avec le modèle. Toute nouvelle
# surface de conversation doit être ajoutée ici en même temps qu'elle est créée.
SURFACES = (PANNEAU, PAGE_DE_COURS)

DEBUT_DE_LA_MENTION = "Koda est une intelligence artificielle"


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante_mention", email="mention@exemple.test",
        password="mot-de-passe-d-essai-2026")


@pytest.mark.django_db
def test_la_page_servie_annonce_qu_on_parle_a_une_intelligence_artificielle(
        client, apprenante):
    """
    La mention est dans le HTML rendu, pas seulement dans le gabarit.

    Compétence visée : C6 (épreuve E2)

    Un gabarit qui porte la phrase mais qui n'est jamais inclus ne tient
    aucune obligation. C'est la page effectivement servie qui est vérifiée.
    """
    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()

    assert DEBUT_DE_LA_MENTION in page, (
        "Le panneau du tuteur ne dit pas à l'apprenant qu'il s'adresse à une "
        "intelligence artificielle — article 50 du règlement (UE) 2024/1689."
    )


@pytest.mark.django_db
def test_la_mention_est_traduite_pour_un_compte_anglophone(
        client, django_user_model):
    """
    L'obligation ne s'arrête pas à la frontière de la langue d'interface.

    Compétence visée : C6 (épreuve E2), C17 (E4)

    Une mention servie en français à qui a choisi l'anglais informe moins bien
    qu'elle ne le prétend. Le catalogue doit donc porter la traduction, et non
    se contenter du repli sur la chaîne source.
    """
    anglophone = django_user_model.objects.create_user(
        username="apprenante_mention_en", email="mention_en@exemple.test",
        password="mot-de-passe-d-essai-2026", language_preference="en")
    client.force_login(anglophone)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()

    assert "Koda is an artificial intelligence" in page
    assert DEBUT_DE_LA_MENTION not in page, (
        "La version française subsiste : la traduction n'est pas prise."
    )


@pytest.mark.django_db
def test_la_mention_survit_a_la_coupure_des_animations(client, apprenante):
    """
    Aucun réglage de compte ne fait disparaître la mention.

    Compétence visée : C6 (épreuve E2), C13 (E3)

    Le personnage animé est désactivable ; l'information réglementaire ne
    l'est pas. Ce test fixe la différence, qu'un gabarit pourrait effacer en
    plaçant la mention dans le même bloc conditionnel que l'animation.
    """
    apprenante.animation_koda = False
    apprenante.save(update_fields=["animation_koda"])

    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()

    assert DEBUT_DE_LA_MENTION in page


def test_les_deux_surfaces_de_conversation_portent_la_mention():
    """
    Le panneau flottant et la colonne de la page de cours, toutes les deux.

    Compétence visée : C6 (épreuve E2)

    Le tuteur a deux points d'entrée : la poignée flottante et la colonne
    « Demander à Koda » de la page de cours, qui s'excluent l'une l'autre.
    Couvrir la première seulement laisserait sans mention la page où
    l'apprenant passe le plus de temps.
    """
    for gabarit in SURFACES:
        contenu = gabarit.read_text(encoding="utf-8")
        assert "components/mention_ia.html" in contenu, (
            f"{gabarit} ouvre une conversation sans inclure la mention."
        )


def test_la_mention_n_est_enfermee_dans_aucune_condition():
    """
    Aucun `{% if %}` n'entoure l'inclusion, sur aucune des deux surfaces.

    Compétence visée : C6 (épreuve E2)

    Une mention conditionnelle est une mention qu'un contexte de vue peut
    éteindre sans que personne s'en aperçoive. Ce test compte les balises de
    condition ouvertes avant l'inclusion : elles doivent toutes être refermées.
    """
    for gabarit in SURFACES:
        contenu = gabarit.read_text(encoding="utf-8")
        # Les blocs de commentaire sont retirés : ils décrivent le code sans
        # l'exécuter, et l'un d'eux pourrait contenir le mot « if ».
        sans_commentaires = re.sub(
            r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "",
            contenu, flags=re.DOTALL)
        avant = sans_commentaires.split("components/mention_ia.html")[0]

        ouvertes = len(re.findall(r"\{%\s*if\b", avant))
        fermees = len(re.findall(r"\{%\s*endif\s*%\}", avant))

        assert ouvertes == fermees, (
            f"{gabarit} place la mention à l'intérieur de "
            f"{ouvertes - fermees} condition(s) : elle peut disparaître."
        )


def test_la_mention_porte_un_texte_et_pas_seulement_un_pictogramme():
    """
    L'icône ne porte aucune information à elle seule.

    Compétence visée : C13 (épreuve E3) — accessibilité

    Le pictogramme est `aria-hidden` et la phrase est du texte : un lecteur
    d'écran restitue l'information, et quelqu'un qui ne connaît pas l'icône la
    lit aussi.
    """
    fragment = FRAGMENT.read_text(encoding="utf-8")

    assert 'aria-hidden="true"' in fragment
    assert DEBUT_DE_LA_MENTION in fragment
