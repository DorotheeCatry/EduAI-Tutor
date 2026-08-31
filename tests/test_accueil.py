"""
Tests de la page d'accueil et de ses états vides.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C13 (E3) — accessibilité

Les états vides sont testés au même titre que les états pleins : ce sont eux
qu'un nouvel apprenant voit, eux qu'une démonstration sur une base neuve
affiche, et eux qui disparaîtraient sans bruit si quelqu'un les retirait.

Un test vérifie aussi qu'aucune des valeurs autrefois inventées ne réapparaît.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.agents.agent_watcher import LearningSession, UserMistake
from apps.exercises.models import Exercise, ExerciseSubmission, UserExerciseProgress
from apps.referentiel.models import Competence

FICHIER_LIVRE = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    call_command("importer_referentiel", FICHIER_LIVRE, "--activer", stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenant(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante_accueil", email="accueil@exemple.test",
        password="mot-de-passe-d-essai-2026",
    )


def _reussir(apprenant, competence, titre, tentatives_avant=0):
    exercice = Exercise.objects.create(
        title=titre, description="…", difficulty="beginner", topic=titre,
        starter_code="", solution="", tests=[], created_by=apprenant,
        competence=competence,
    )
    for _ in range(tentatives_avant):
        ExerciseSubmission.objects.create(
            exercise=exercice, user=apprenant, submitted_code="", status="failed")
    reussie = ExerciseSubmission.objects.create(
        exercise=exercice, user=apprenant, submitted_code="", status="success")
    UserExerciseProgress.objects.update_or_create(
        user=apprenant, exercise=exercice,
        defaults={"is_completed": True, "completed_at": timezone.now(),
                  "best_submission": reussie, "attempts_count": tentatives_avant + 1})
    return exercice


def _page(client, apprenant):
    client.force_login(apprenant)
    reponse = client.get(reverse("accueil:accueil"), secure=True)
    assert reponse.status_code == 200
    return reponse.content.decode("utf-8")


@pytest.mark.django_db
def test_la_racine_mene_a_l_accueil_et_non_au_generateur(client, apprenant):
    """
    L'accueil remplace le générateur de cours comme porte d'entrée.

    Compétence visée : C17 (épreuve E4)
    """
    client.force_login(apprenant)

    reponse = client.get("/", secure=True)

    assert reponse.status_code == 302
    assert reverse("accueil:accueil") in reponse.url


@pytest.mark.django_db
def test_les_quatre_blocs_ont_un_etat_vide_sur_une_base_neuve(
        client, apprenant, referentiel):
    """
    Une base sans activité affiche quatre états vides, pas une page blanche.

    Compétence visée : C17 (épreuve E4)

    C'est le premier écran d'un nouvel apprenant, et celui d'une démonstration
    sur une base neuve.
    """
    contenu = _page(client, apprenant)

    assert "Où j'en suis" in contenu
    assert "Aucune compétence entamée sur 21" in contenu, (
        "l'état vide tient en une phrase, et non en quatre lignes identiques"
    )
    assert "commencez par le module Python" in contenu
    assert "Ce que je fais maintenant" in contenu
    assert "Rien à revoir pour l'instant" in contenu
    assert "Aucune activité pour l'instant" in contenu


@pytest.mark.django_db
def test_chaque_etat_vide_oriente_vers_une_action(client, apprenant, referentiel):
    """
    Un état vide propose quelque chose à faire, il ne constate pas une absence.

    Compétence visée : C17 (épreuve E4)
    """
    contenu = _page(client, apprenant)

    assert "S'exercer sur cette compétence" in contenu
    assert "Faire un quiz pour repérer mes lacunes" in contenu


@pytest.mark.django_db
def test_sans_referentiel_actif_la_page_repond_et_l_explique(client, apprenant):
    """
    Aucun référentiel actif ne fait pas tomber l'accueil.

    Compétence visée : C17 (épreuve E4)

    Et le message ne suggère pas à l'apprenant qu'il n'a rien fait : c'est une
    absence de configuration, pas une absence de travail.
    """
    contenu = _page(client, apprenant)

    assert "Aucun référentiel de compétences n'est actif" in contenu
    assert "Votre travail est enregistré" in contenu


@pytest.mark.django_db
def test_non_mesure_se_distingue_de_non_atteint(client, apprenant, referentiel):
    """
    Les deux états portent deux libellés différents, visibles.

    Compétence visée : C13 (épreuve E3) — accessibilité
    Compétence visée : C17 (épreuve E4)

    « Non mesuré » dit que le dispositif ne sait pas conclure, « non atteint »
    que l'apprenant n'y est pas encore. Les confondre ferait porter à
    l'apprenant une limite qui est la nôtre — et la distinction ne doit pas
    reposer sur une nuance de couleur.
    """
    contenu = _page(client, apprenant)

    assert "non mesuré" in contenu
    assert "ne veut pas dire" in contenu, (
        "la page doit expliquer la différence, pas seulement l'afficher"
    )


@pytest.mark.django_db
def test_le_bloc_ou_j_en_suis_compte_les_niveaux_reels(
        client, apprenant, referentiel):
    """
    Le résumé par module reflète les exercices réellement réussis.

    Compétence visée : C17 (épreuve E4)
    """
    for numero in range(3):
        _reussir(apprenant, referentiel, f"listes {numero}")

    contenu = _page(client, apprenant)

    assert "1 sur 7 au niveau 1, 1 au niveau 2" in contenu
    assert "3 modules non entamés" in contenu, (
        "les modules non entamés sont repliés, non développés"
    )


@pytest.mark.django_db
def test_le_bloc_a_revoir_classe_par_tentatives_et_affiche_son_critere(
        client, apprenant, referentiel):
    """
    Le plus résistant est en tête, et le critère est écrit sur la page.

    Compétence visée : C17 (épreuve E4)

    Sans le critère affiché, la liste paraîtrait arbitraire et personne ne
    pourrait la contester.
    """
    _reussir(apprenant, referentiel, "facile", tentatives_avant=1)
    _reussir(apprenant, referentiel, "coriace", tentatives_avant=6)

    contenu = _page(client, apprenant)

    assert "nombre de tentatives avant réussite" in contenu
    assert contenu.index("coriace") < contenu.index("facile"), (
        "le plus résistant doit venir en premier"
    )


@pytest.mark.django_db
def test_un_exercice_reussi_du_premier_coup_n_est_pas_a_revoir(
        client, apprenant, referentiel):
    """
    Une réussite immédiate ne figure pas dans « à revoir ».

    Compétence visée : C17 (épreuve E4)
    """
    _reussir(apprenant, referentiel, "immediat")

    contenu = _page(client, apprenant)

    assert "Rien à revoir pour l'instant" in contenu
    assert "immediat" not in contenu.split("À revoir")[1].split("Dernière activité")[0]


@pytest.mark.django_db
def test_les_erreurs_de_quiz_alimentent_le_bloc_a_revoir(
        client, apprenant, referentiel):
    """
    Un quiz manqué apparaît, nommé par sa compétence.

    Compétence visée : C17 (épreuve E4)

    Les quiz sont la seule source du bloc tant qu'aucun exercice n'a résisté.
    """
    UserMistake.objects.create(
        user=apprenant, topic=referentiel.intitule, competence=referentiel,
        mistake_type="quiz_wrong_answer", question="?", user_answer="a",
        correct_answer="b",
    )

    contenu = _page(client, apprenant)

    assert referentiel.intitule in contenu
    assert "réponse manquée" in contenu


@pytest.mark.django_db
def test_un_quiz_non_termine_n_est_pas_une_activite(client, apprenant, referentiel):
    """
    Une session ouverte n'est pas un quiz fait.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    La base déployée portait quatre sessions ouvertes et aucune close au
    31/08 : les compter comme de l'activité afficherait un travail qui n'a pas
    eu lieu (incident 010).
    """
    LearningSession.objects.create(
        user=apprenant, topic="quiz engendré, jamais terminé",
        activity_type="quiz", metadata={"questions": []},
    )

    contenu = _page(client, apprenant)

    assert "Aucune activité pour l'instant" in contenu
    assert "jamais terminé" not in contenu


@pytest.mark.django_db
def test_aucune_valeur_factice_ne_subsiste_sur_les_pages_de_suivi(
        client, apprenant, referentiel):
    """
    Les chiffres inventés ne reviennent sur aucune des pages nettoyées.

    Compétence visée : C21 (épreuve E5) — non-régression de l'incident 011

    « Python Basics 85 % » s'affichait sur un compte à zéro cours, la page de
    révision annonçait 24 cartes maîtrisées et 92 % de réussite, et le salon de
    quiz 127 quiz terminés. Ce test échoue si l'un d'eux réapparaît.
    """
    client.force_login(apprenant)
    pages = [reverse("accueil:accueil"), reverse("tracker:dashboard"),
             reverse("revision:flashcards"), reverse("quiz:lobby")]

    inventes = ["Python Basics", "Web Development", "Data Structures",
                "Python Decorators", "85%", "92%", "127", "3h 42m", "1h 23m"]

    for page in pages:
        contenu = client.get(page, secure=True).content.decode("utf-8")
        for valeur in inventes:
            assert valeur not in contenu, f"valeur inventée « {valeur} » sur {page}"


@pytest.mark.django_db
def test_le_temps_d_etude_est_annonce_comme_non_mesure(client, apprenant):
    """
    La page Performance ne simule plus le temps d'étude.

    Compétence visée : C21 (épreuve E5)

    Il était déduit du nombre de cours — « ~25 min par cours » — et le champ
    qui devait le porter n'est écrit par aucun code du projet.
    """
    client.force_login(apprenant)

    contenu = client.get(reverse("tracker:dashboard"),
                         secure=True).content.decode("utf-8")

    assert "Temps d'étude" in contenu
    assert "non mesuré" in contenu


def test_aucun_gabarit_ne_porte_de_commentaire_multiligne():
    """
    Un commentaire `{# … #}` ne doit jamais s'étendre sur plusieurs lignes.

    Compétence visée : C18 (épreuve E4)
    Compétence concernée : C17 (E4)

    Django n'interprète `{# … #}` que sur UNE ligne. Sur plusieurs, la syntaxe
    n'est pas reconnue et le commentaire **s'affiche en clair sur la page** —
    quatre s'affichaient ainsi sur la page d'accueil, dont deux au-dessus du
    contenu, le 31/08/2026.

    Ce test est statique plutôt que fondé sur un rendu : il couvre aussi les
    gabarits qu'aucun test de page n'atteint, et il nomme le fichier et la
    ligne au lieu de faire chercher.

    La forme correcte sur plusieurs lignes est `{% comment %}…{% endcomment %}`.
    """
    from pathlib import Path

    fautifs = []
    gabarits = list(Path("apps").rglob("*.html")) + list(Path("templates").rglob("*.html"))

    for chemin in gabarits:
        contenu = chemin.read_text(encoding="utf-8")
        position = 0
        while True:
            debut = contenu.find("{#", position)
            if debut == -1:
                break
            fin = contenu.find("#}", debut)
            if fin == -1 or "\n" in contenu[debut:fin]:
                ligne = contenu[:debut].count("\n") + 1
                fautifs.append(f"{chemin}:{ligne}")
                position = debut + 2
            else:
                position = fin + 2

    assert not fautifs, (
        "commentaires {# … #} sur plusieurs lignes, qui s'afficheront sur la "
        "page — employer {% comment %} : " + ", ".join(fautifs)
    )


@pytest.mark.django_db
def test_aucune_page_rendue_n_affiche_de_syntaxe_de_gabarit(
        client, apprenant, referentiel):
    """
    Aucune page servie ne contient `{#`, `{%` ou `{{` non interprétés.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le contrôle statique dit qu'aucun gabarit n'en porte ; celui-ci dit
    qu'aucune page n'en affiche. Les deux se complètent : le premier prévient,
    le second constate.
    """
    from django.urls import reverse

    client.force_login(apprenant)
    for page in [reverse("accueil:accueil"), reverse("tracker:dashboard"),
                 reverse("revision:flashcards"), reverse("quiz:lobby"),
                 reverse("exercises:list")]:
        contenu = client.get(page, secure=True).content.decode("utf-8")
        assert "{#" not in contenu, f"syntaxe de commentaire visible sur {page}"
        assert "{% " not in contenu, f"balise de gabarit visible sur {page}"


@pytest.mark.django_db
def test_l_action_vient_avant_la_progression(client, apprenant, referentiel):
    """
    « Ce que je fais maintenant » est le premier bloc de la page.

    Compétence visée : C17 (épreuve E4)

    L'action était enterrée au milieu de la page, sous quatre lignes de
    progression vide. Un apprenant qui arrive doit voir en premier ce qu'il a à
    faire — c'est la raison d'être de cette page.
    """
    contenu = _page(client, apprenant)

    assert contenu.index("Ce que je fais maintenant") < contenu.index("Où j'en suis")
    assert contenu.index("Où j'en suis") < contenu.index("À revoir")
    assert contenu.index("À revoir") < contenu.index("Dernière activité")


@pytest.mark.django_db
def test_les_notes_de_methode_sont_repliees(client, apprenant, referentiel):
    """
    Les explications pédagogiques sont dans un `<details>`, pas en tête de page.

    Compétence visée : C13 (épreuve E3) — accessibilité
    Compétence visée : C17 (épreuve E4)

    Elles doivent rester atteignables — un `<details>` l'est au clavier et se
    lit par un lecteur d'écran, contrairement à une infobulle — mais elles ne
    sont pas du contenu de page : ce sont des notes de méthode.
    """
    contenu = _page(client, apprenant)

    assert "Comment se lisent les trois niveaux" in contenu
    assert "Comment cette liste est construite" in contenu

    avant_details = contenu.split("Comment se lisent les trois niveaux")[0]
    assert "« Non mesuré » ne veut pas dire" not in avant_details, (
        "l'explication du niveau 3 ne doit plus précéder le contenu"
    )
    assert contenu.count("<details") >= 2
