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


FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    from io import StringIO

    from django.core.management import call_command

    from apps.referentiel.models import Competence

    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer",
                 stdout=StringIO())
    return Competence.objects.get(code="collections")


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

    # Ce qui compte est le nombre de requêtes, pas le nombre de balises : deux
    # Koda à l'écran — celui de la poignée et celui du panneau — désignent la
    # même image, et le navigateur ne la télécharge qu'une fois.
    citees = set(re.findall(r"img/koda/planches/[\w.-]+", panneau))
    assert len(citees) == 1, (
        "le panneau ne doit charger qu'une planche, il en cite %s" % sorted(citees)
    )
    poids = Path("static", planches["gros_plan"]["fichier"]).stat().st_size
    assert poids < 80 * 1024, (
        "la planche du panneau est servie sur toutes les pages : %d Kio"
        % (poids // 1024)
    )


# --- Ce que Koda a le droit de dire ---------------------------------------


SALUTATION = Path("apps/chat/salutation.py")


@pytest.mark.django_db
def test_koda_appelle_l_apprenant_par_son_pseudonyme(apprenante):
    """
    Le pseudonyme figure dans la salutation.

    Compétence visée : C17 (épreuve E4)
    """
    from apps.chat.salutation import saluer

    assert "apprenante" in saluer(apprenante)["phrase"]


@pytest.mark.django_db
def test_koda_n_invente_aucune_seance_a_qui_n_a_rien_fait(apprenante):
    """
    Un compte sans activité reçoit une salutation qui n'affirme rien.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    C'est ici que le faux s'introduit le plus facilement : une mascotte
    chaleureuse appelle des phrases qui « sonnent bien » — « content de te
    revoir », « tu progresses ». Adressées à quelqu'un qui vient de s'inscrire,
    ce sont des affirmations fausses. Le projet a retiré sept foyers de données
    fabriquées ; celui-ci n'en sera pas le huitième.
    """
    from apps.chat.salutation import saluer

    salutation = saluer(apprenante)

    assert "revoir" not in salutation["phrase"].lower(), (
        "on ne revoit pas quelqu'un qu'on n'a jamais vu"
    )
    for interdit in ("jours", "série", "progress", "bravo"):
        assert interdit not in salutation["detail"].lower(), (
            "« %s » affirme quelque chose que la base ne dit pas" % interdit
        )


@pytest.mark.django_db
def test_koda_nomme_la_notion_que_la_base_connait(apprenante, referentiel):
    """
    Le détail de la salutation vient d'une erreur réellement enregistrée.

    Compétence visée : C17 (épreuve E4), C20 (E5)
    """
    from apps.agents.agent_watcher import UserMistake
    from apps.chat.salutation import saluer

    UserMistake.objects.create(
        user=apprenante, topic="Manipuler les listes", mistake_type="quiz",
        question="?", user_answer="faux", correct_answer="vrai",
        competence=referentiel,
    )

    assert referentiel.intitule in saluer(apprenante)["detail"]


def test_koda_n_emploie_pas_un_compteur_que_personne_ne_tient():
    """
    `current_streak` est interdit à la salutation.

    Compétence visée : C21 (épreuve E5)

    Le champ existe et il est lu ailleurs pour calculer un bonus d'expérience,
    mais **rien ne l'écrit jamais** : il vaut zéro pour tout le monde
    (réserve 19). Une phrase du genre « trois jours d'affilée ! » serait donc
    fausse pour chaque apprenant, tout en paraissant la chose la plus naturelle
    à dire.
    """
    source = SALUTATION.read_text(encoding="utf-8")
    code = "\n".join(ligne for ligne in source.split("\n")
                     if not ligne.strip().startswith("#"))
    corps = code.split('"""', 2)[-1]

    assert "current_streak" not in corps, (
        "un compteur que rien ne met à jour ne peut pas être annoncé"
    )


def test_la_salutation_ne_depense_aucune_generation():
    """
    Dire bonjour ne consomme pas le quota du jour.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Quinze générations par jour et par apprenant (décision 030). En dépenser
    une pour une phrase d'accueil serait absurde — et rendrait l'accueil
    dépendant d'un service distant.
    """
    source = SALUTATION.read_text(encoding="utf-8")

    for interdit in ("orchestrator", "get_orchestrator", "consommer", "generate"):
        assert interdit not in source, (
            "la salutation doit être assemblée localement, pas engendrée"
        )
