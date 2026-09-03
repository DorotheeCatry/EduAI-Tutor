"""
Le bloc « à revoir » doit faire recommencer, pas seulement constater.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C20 (E5) ; C21 (E5)

Le bloc nommait ce qui avait résisté — un exercice repris plusieurs fois, une
notion dont des questions de quiz ont été manquées — et n'offrait **aucun
moyen d'y revenir**. Sur la page d'accueil, ni les exercices ni les erreurs de
quiz ne portaient de lien ; sur la page de révision, seul le titre de
l'exercice en avait un.

Or c'est la raison d'être de ce bloc : constater une lacune sans proposer de la
combler laisse à l'apprenant un travail que l'application pouvait faire.
"""

import pytest
from django.urls import reverse

from apps.accueil.services import erreurs_de_quiz


@pytest.fixture
def apprenant_avec_erreurs(django_user_model, db):
    """Un compte, une compétence, et deux réponses manquées."""
    from apps.agents.agent_watcher import UserMistake
    from apps.referentiel.models import Competence, Module, Referentiel

    referentiel = Referentiel.objects.create(code="rev", intitule="Essai",
                                             version="1", est_actif=True)
    module = Module.objects.create(referentiel=referentiel, code="mrev",
                                   intitule="Module", ordre=1)
    competence = Competence.objects.create(module=module, code="les-boucles",
                                           intitule="Écrire des boucles", ordre=1)
    utilisateur = django_user_model.objects.create_user(
        username="apprenant_revoir", password="mot-de-passe-de-test-1")

    for numero in range(2):
        UserMistake.objects.create(
            user=utilisateur, competence=competence,
            topic="Écrire des boucles",
            question=f"Question {numero} ?", correct_answer="La bonne réponse",
        )
    return utilisateur, competence


def test_une_erreur_de_quiz_porte_de_quoi_la_rejouer(apprenant_avec_erreurs):
    """
    Le service rend le code de la compétence et le sujet.

    Compétence visée : C17 (épreuve E4)

    Sans l'un des deux, le gabarit ne peut pas construire de lien : une
    compétence se relance par son code, un quiz lancé sur un sujet libre par
    son intitulé.
    """
    utilisateur, competence = apprenant_avec_erreurs

    lignes = erreurs_de_quiz(utilisateur)

    assert len(lignes) == 1
    assert lignes[0]["code"] == competence.code
    assert lignes[0]["sujet"] == "Écrire des boucles"
    assert lignes[0]["erreurs"] == 2


def test_le_bloc_offre_un_seul_geste_pour_rejouer(client, apprenant_avec_erreurs):
    """
    Une case par notion, et un bouton : pas de lien par ligne.

    Compétence visée : C17 (épreuve E4)

    Choix : un geste unique — cocher, puis appuyer — plutôt qu'un lien sous
    chaque ligne. Motivation : les liens par ligne offraient le même geste une
    fois par notion, et rendaient impossible d'en revoir plusieurs d'un coup.
    Une case dit ce qu'elle sélectionne, un bouton dit ce qu'il fera.
    """
    utilisateur, competence = apprenant_avec_erreurs
    client.force_login(utilisateur)

    contenu = client.get(reverse("revision:flashcards"), secure=True).content.decode()

    assert 'name="notion"' in contenu, "chaque notion porte sa case"
    assert f'value="{competence.code}"' in contenu
    assert "Rejouer mes vraies erreurs" in contenu, "un bouton pour la sélection"
    assert "Refaire un quiz sur cette notion" not in contenu, (
        "le lien par ligne doublait le bouton"
    )


def test_une_notion_hors_referentiel_reste_cochable(client, django_user_model):
    """
    Une erreur non rattachée porte sa case, avec son sujet pour valeur.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    Un quiz lancé sur un sujet libre n'a pas de compétence (décision 027).
    Sans ce repli, ses erreurs s'afficheraient sans case — et le bloc agirait
    pour les unes, pas pour les autres.
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur = django_user_model.objects.create_user(
        username="apprenant_libre", password="mot-de-passe-de-test-1")
    UserMistake.objects.create(
        user=utilisateur, competence=None, topic="Les décorateurs",
        question="Une question ?", user_answer="Faux", correct_answer="Une réponse",
    )
    client.force_login(utilisateur)

    contenu = client.get(reverse("revision:flashcards"), secure=True).content.decode()

    assert 'name="notion"' in contenu
    assert 'value="Les décorateurs"' in contenu, "le sujet sert de valeur"


# --- Rejouer les vraies erreurs -------------------------------------------

@pytest.mark.django_db
def test_la_seance_repose_les_questions_reellement_manquees(client, apprenant_avec_erreurs):
    """
    Ce sont les questions posées, avec la réponse donnée comme distracteur.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — quotas

    Un quiz engendré sur la notion mesure la notion ; reposer la question
    mesure l'erreur. Et comme tout est déjà en base, la séance ne consomme
    aucune génération : elle reste disponible quand le quota est épuisé,
    c'est-à-dire quand l'apprenant a beaucoup travaillé.
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur, competence = apprenant_avec_erreurs
    UserMistake.objects.filter(user=utilisateur).update(user_answer="Ma réponse fausse")
    client.force_login(utilisateur)

    page = client.get(reverse("revision:mes_erreurs"), secure=True).content.decode()

    assert "Question 0 ?" in page and "Question 1 ?" in page
    assert "La bonne réponse" in page, "la bonne réponse est l'une des propositions"
    assert "Ma réponse fausse" in page, "la réponse donnée sert de distracteur"


@pytest.mark.django_db
def test_les_notions_cochees_filtrent_la_seance(client, apprenant_avec_erreurs):
    """
    Cocher une notion restreint la séance ; ne rien cocher les prend toutes.

    Compétence visée : C17 (épreuve E4)
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur, competence = apprenant_avec_erreurs
    UserMistake.objects.filter(user=utilisateur).update(user_answer="Ma réponse fausse")
    UserMistake.objects.create(
        user=utilisateur, competence=None, topic="Les décorateurs",
        question="Question hors référentiel ?",
        user_answer="Faux", correct_answer="Vrai",
    )
    client.force_login(utilisateur)
    adresse = reverse("revision:mes_erreurs")

    toutes = client.get(adresse, secure=True).content.decode()
    assert "Question 0 ?" in toutes and "Question hors référentiel ?" in toutes

    filtree = client.get(adresse, {"notion": competence.code}, secure=True).content.decode()
    assert "Question 0 ?" in filtree
    assert "Question hors référentiel ?" not in filtree, "la notion non cochée est écartée"


@pytest.mark.django_db
def test_une_erreur_corrigee_quitte_la_liste(client, apprenant_avec_erreurs):
    """
    `reviewed` n'est levé que sur une erreur effectivement corrigée.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    Le drapeau existait depuis l'origine et n'était écrit nulle part : les
    vingt-neuf erreurs de la base le portaient toutes à faux, et la méthode
    prévue pour le lever n'avait aucun appelant. Le lever au seul fait d'avoir
    affiché la question ne dirait rien de plus que la date de la question.
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur, _ = apprenant_avec_erreurs
    UserMistake.objects.filter(user=utilisateur).update(user_answer="Ma réponse fausse")
    juste, faux = UserMistake.objects.filter(user=utilisateur).order_by("id")
    client.force_login(utilisateur)

    page = client.post(reverse("revision:mes_erreurs"), {
        f"reponse-{juste.id}": "La bonne réponse",
        f"reponse-{faux.id}": "Ma réponse fausse",
    }, secure=True).content.decode()

    juste.refresh_from_db()
    faux.refresh_from_db()
    assert juste.reviewed is True, "corrigée, elle quitte la liste"
    assert faux.reviewed is False, "manquée, elle y reste"
    assert "Encore à revoir" in page


@pytest.mark.django_db
def test_le_camembert_dit_les_memes_nombres_que_son_tableau(client, apprenant_avec_erreurs):
    """
    Le graphique est doublé d'un tableau à en-têtes.

    Compétence visée : C20 (épreuve E5) — restitution
    Compétence concernée : C13 (E3) — accessibilité

    Un graphique qu'un lecteur d'écran ne restitue pas n'informe que ceux qui
    voient. Et la couleur seule ne distingue pas les parts : chacune est nommée
    dans le tableau.
    """
    from apps.revision.services import repartition_des_erreurs

    utilisateur, competence = apprenant_avec_erreurs
    client.force_login(utilisateur)

    repartition = repartition_des_erreurs(utilisateur)
    assert repartition["total"] == 2
    assert repartition["parts"][0]["notion"] == competence.intitule
    assert repartition["parts"][0]["pourcentage"] == 100
    assert repartition["parts"][0]["trace"].startswith("M "), "un tracé SVG calculé ici"

    page = client.get(reverse("revision:flashcards"), secure=True).content.decode()
    assert "<svg" in page and 'role="img"' in page
    assert "Où se concentrent vos erreurs" in page
    assert "<th scope=\"col\"" in page, "le tableau porte des en-têtes"
    assert competence.intitule in page


@pytest.mark.django_db
def test_la_question_n_est_jamais_enfermee_dans_un_paragraphe(client, apprenant_avec_erreurs):
    """
    Le Markdown rendu vit dans un `div`, jamais dans un `p`.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    Une question de quiz contient des paragraphes et des blocs de code. Placée
    dans un `<p>`, le navigateur ferme le paragraphe au premier bloc : le reste
    du contenu se retrouve HORS du conteneur et perd la classe qui le met en
    forme. Le rendu paraissait alors « toujours cassé » alors que le Markdown
    était correctement converti.
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur, _ = apprenant_avec_erreurs
    UserMistake.objects.filter(user=utilisateur).update(
        user_answer="Ma réponse fausse",
        question="## Titre\n\nUn paragraphe.\n\n```python\nprint('x')\n```",
    )
    client.force_login(utilisateur)

    page = client.get(reverse("revision:mes_erreurs"), secure=True).content.decode()

    assert '<p class="cours-rendu' not in page, (
        "un bloc de Markdown ne tient pas dans un paragraphe"
    )
    assert '<div class="cours-rendu' in page
    assert "<h2>Titre</h2>" in page and "language-python" in page


@pytest.mark.django_db
def test_une_proposition_s_affiche_mise_en_forme_et_s_envoie_brute(client, apprenant_avec_erreurs):
    """
    Ce qui s'affiche est mis en forme ; ce qui part est le texte d'origine.

    Compétence visée : C17 (épreuve E4)

    Les réponses d'un quiz portent souvent un nom de fonction entre accents
    graves. Affichées telles quelles, les accents restaient à l'écran. Mais la
    valeur envoyée doit rester le texte brut : c'est lui que la correction
    compare à la bonne réponse, et le mettre en forme ferait échouer toute
    réponse juste.
    """
    from apps.agents.agent_watcher import UserMistake

    utilisateur, _ = apprenant_avec_erreurs
    UserMistake.objects.filter(user=utilisateur).update(
        correct_answer="`type()`", user_answer="`print()`")
    client.force_login(utilisateur)

    page = client.get(reverse("revision:mes_erreurs"), secure=True).content.decode()

    assert 'value="`type()`"' in page, "la valeur envoyée reste brute"
    assert "<code>type()</code>" in page, "l'affichage est mis en forme"

    erreur = UserMistake.objects.filter(user=utilisateur).first()
    client.post(reverse("revision:mes_erreurs"),
                {f"reponse-{erreur.id}": "`type()`"}, secure=True)
    erreur.refresh_from_db()
    assert erreur.reviewed is True, "la réponse brute doit être reconnue comme juste"
