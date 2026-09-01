"""
Koda, le tuteur incarné — ce que l'animation n'a pas le droit de faire.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — accessibilité ; C21 (E5)

Le personnage accompagne les messages du tuteur ; il ne les remplace jamais.
Ces tests fixent cette règle et les protections d'accessibilité, qu'aucune
relecture ne garantit durablement.
"""

import json
import re
from pathlib import Path

import pytest
from django.urls import reverse

SCRIPT = Path("static/js/koda.js")
FEUILLE = Path("static/css/tailwind.css")
DESCRIPTEUR = Path("static/img/koda/planches/planches.json")
PANNEAU = Path("templates/components/tuteur.html")


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante", email="apprenante@exemple.test",
        password="mot-de-passe-d-essai-2026")


@pytest.mark.django_db
def test_les_messages_du_tuteur_restent_dans_le_html_rendu(client, apprenante):
    """
    Aucune information n'est portée par la seule animation.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Un personnage qui s'agite ne dit rien à qui ne le voit pas — ni à un
    lecteur d'écran, ni à quelqu'un qui a coupé les animations, ni à qui
    regarde ailleurs. Le texte doit donc rester présent quoi qu'il arrive.
    """
    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()

    for message in ("Le tuteur réfléchit", "La réponse n'a pas pu être obtenue"):
        assert message in page, (
            "« %s » doit rester dans le HTML : Koda ne le porte pas à sa place"
            % message
        )


@pytest.mark.django_db
def test_le_reglage_du_profil_fige_le_personnage(client, apprenante):
    """
    Décocher l'animation dans le profil fige Koda, indépendamment du système.

    Compétence visée : C17 (épreuve E4), C13 (E3)
    """
    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()
    assert 'data-animation="desactivee"' not in page

    apprenante.animation_koda = False
    apprenante.save()
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()
    assert 'data-animation="desactivee"' in page, (
        "le réglage du profil doit atteindre le gabarit"
    )


def test_le_mouvement_reduit_est_respecte_par_la_feuille_et_par_le_script():
    """
    Les deux protections contre le mouvement sont en place.

    Compétence visée : C13 (épreuve E3) — accessibilité

    La feuille de style fige le personnage même si le script tarde ou échoue ;
    le script cesse en plus de parcourir la planche, pour ne pas consommer une
    batterie à afficher une image qui ne change pas. L'une des deux suffirait
    en régime normal — c'est bien pour cela qu'il en faut deux.
    """
    feuille = FEUILLE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    assert "prefers-reduced-motion:reduce" in feuille.replace(" ", ""), (
        "la feuille compilée doit contenir la règle de mouvement réduit"
    )
    assert "prefers-reduced-motion: reduce" in script
    assert "document.hidden" in script, (
        "une boucle ne doit pas tourner dans un onglet en arrière-plan"
    )
    assert "offsetParent === null" in script, (
        "une boucle ne doit pas tourner derrière un panneau replié"
    )


def test_la_boucle_de_repos_est_muette_pour_un_lecteur_d_ecran():
    """
    Le repos est décoratif ; seuls les états qui signifient quelque chose parlent.

    Compétence visée : C13 (épreuve E3) — accessibilité

    Un lecteur d'écran ne doit pas annoncer « Koda respire » toutes les deux
    secondes. L'alternative textuelle n'est posée que pour les états déclarés.
    """
    panneau = PANNEAU.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'data-etat-initial="repos"' in panneau
    assert 'aria-hidden="true"' in panneau
    assert "data-alt-parle" in panneau, "l'état « parle » doit être annoncé"
    assert 'setAttribute("aria-hidden", "true")' in script, (
        "un état sans alternative textuelle doit redevenir muet"
    )


def test_aucun_etat_ne_designe_une_image_absente_de_la_planche():
    """
    Les indices de la table d'états tiennent dans la planche.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Une coquille dans un indice n'échoue pas : elle affiche une case vide ou la
    mauvaise expression, et personne ne rapproche cela d'un chiffre. Ce test
    remplace cette relecture.
    """
    script = SCRIPT.read_text(encoding="utf-8")
    planches = json.loads(DESCRIPTEUR.read_text(encoding="utf-8"))
    disponibles = planches["gros_plan"]["images"]

    table = script[script.index("var ETATS = {"):script.index("var IMAGE_FIXE")]
    indices = [int(n) for n in re.findall(r"\b(\d+)\b", re.sub(
        r"(cadence|reposMin|reposMax)\s*:\s*\d+", "", table))]

    assert indices, "la table d'états doit être lisible"
    assert max(indices) < disponibles, (
        "l'état le plus haut désigne l'image %d, la planche en compte %d"
        % (max(indices), disponibles)
    )


def test_la_planche_est_servie_en_une_seule_requete():
    """
    Une image par famille de cadrage, pas une par frame.

    Compétence visée : C13 (épreuve E3) — poids des ressources
    """
    # Les commentaires du gabarit citent forcément le chemin de la planche :
    # un test qui les compte interdit d'expliquer ce que fait le code.
    panneau = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "",
                     PANNEAU.read_text(encoding="utf-8"), flags=re.S)
    planches = json.loads(DESCRIPTEUR.read_text(encoding="utf-8"))

    assert panneau.count("img/koda/planches/") == 1, (
        "le panneau ne doit charger qu'une planche"
    )
    poids = Path("static", planches["gros_plan"]["fichier"]).stat().st_size
    assert poids < 80 * 1024, (
        "la planche du panneau est servie sur toutes les pages : %d Kio"
        % (poids // 1024)
    )
