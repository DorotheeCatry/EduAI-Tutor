"""
Les trois couches du cours : référence, fiche, enrichissements.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — attribution ; C13 (E3) — quotas ; C21 (E5)

Ce que ces tests défendent tient en une phrase : **le travail de l'apprenant
survit au remplacement du cours de référence**, et chaque enrichissement reste
compréhensible et attribuable après ce remplacement.
"""

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.courses.models import AjoutDeFiche, CoursDeReference, FicheDApprenant
from apps.courses.services import (
    attribution_des_fragments,
    cours_actif,
    fiche_de,
    publier_le_cours,
)
from apps.referentiel.models import Competence

FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def competence():
    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer",
                 stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante", email="apprenante@exemple.test",
        password="mot-de-passe-d-essai-2026")


# --- Le double statut ------------------------------------------------------


@pytest.mark.django_db
def test_un_cours_publie_prend_la_place_du_provisoire(competence, apprenante):
    """
    Publier met le provisoire de côté sans le supprimer.

    Compétence visée : C17 (épreuve E4)

    Le provisoire cède la place : il est daté, il sort de l'affichage, et il
    reste consultable. Un apprenant doit pouvoir comprendre d'où venait ce
    qu'il lisait la semaine précédente.
    """
    provisoire = CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="Provisoire", contenu="…")
    assert cours_actif(competence) == provisoire

    publie = publier_le_cours(competence, "contenu relu", "Publié", apprenante)

    provisoire.refresh_from_db()
    assert provisoire.remplace_le is not None, "le provisoire doit être daté"
    assert CoursDeReference.objects.filter(pk=provisoire.pk).exists(), (
        "le provisoire est mis de côté, jamais supprimé"
    )
    assert cours_actif(competence) == publie


@pytest.mark.django_db
def test_deux_cours_actifs_du_meme_statut_sont_refuses(competence):
    """
    Une compétence n'a qu'un cours courant par statut.

    Compétence visée : C4 (épreuve E1) — intégrité
    """
    CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="Un", contenu="…")

    with pytest.raises(IntegrityError), transaction.atomic():
        CoursDeReference.objects.create(
            competence=competence, statut=CoursDeReference.PROVISOIRE,
            titre="Deux", contenu="…")


@pytest.mark.django_db
def test_un_cours_remplace_laisse_la_place_a_un_suivant(competence):
    """
    La contrainte porte sur les cours actifs, pas sur l'historique.

    Compétence visée : C4 (épreuve E1)
    """
    premier = CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="Un", contenu="…")
    premier.remplace_le = timezone.now()
    premier.save()

    second = CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="Deux", contenu="…")
    assert cours_actif(competence) == second


# --- La fiche survit au cours ----------------------------------------------


@pytest.mark.django_db
def test_la_fiche_survit_au_remplacement_du_cours(competence, apprenante):
    """
    Le travail de l'apprenant n'est pas perdu quand le cours change.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    C'est la raison d'être du découpage : la fiche est rattachée à la
    compétence, pas au cours. Une clé étrangère vers le cours ferait disparaître
    le travail de l'apprenant le jour où le formateur publie le sien — l'inverse
    exact de ce que ce dispositif cherche.
    """
    CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="Provisoire", contenu="…")
    fiche = fiche_de(apprenante, competence)
    AjoutDeFiche.objects.create(fiche=fiche, question="Développe cette partie",
                                contenu="mon ajout")

    publier_le_cours(competence, "contenu relu", "Publié", apprenante)

    fiche.refresh_from_db()
    assert fiche.ajouts.count() == 1
    assert fiche.ajouts.first().contenu == "mon ajout"


@pytest.mark.django_db
def test_chaque_ajout_porte_la_question_qui_l_a_produit(competence, apprenante):
    """
    Un ajout sans sa question devient incompréhensible.

    Compétence visée : C17 (épreuve E4)

    Un ajout né de « développe cette partie » sur une section qui n'existe plus
    dans le cours suivant n'a plus de sens si l'on n'a gardé que sa réponse.
    """
    champs = {f.name for f in AjoutDeFiche._meta.get_fields()}
    assert "question" in champs
    assert "section_visee" in champs

    ajout = AjoutDeFiche.objects.create(
        fiche=fiche_de(apprenante, competence),
        question="Un cas plus complexe", contenu="…",
        section_visee="Les compréhensions de liste")
    assert ajout.question and ajout.section_visee


# --- L'attribution ---------------------------------------------------------


def test_l_attribution_conserve_la_licence_et_pas_seulement_l_url():
    """
    Une URL sans sa licence ne dit pas s'il faut nommer l'auteur.

    Compétence visée : C4 (épreuve E1)
    """
    class Fragment:
        def __init__(self, meta):
            self.metadata = meta

    sources = attribution_des_fragments([
        Fragment({"url_source": "https://exemple.test/a", "titre": "A",
                  "code_licence": "CC-BY-SA-4.0", "attribution_requise": True}),
        Fragment({"url_source": "https://exemple.test/a", "titre": "A",
                  "code_licence": "CC-BY-SA-4.0", "attribution_requise": True}),
        Fragment({"url_source": "", "titre": "sans url"}),
    ])

    assert len(sources) == 1, "une même source n'est citée qu'une fois"
    assert sources[0]["code_licence"] == "CC-BY-SA-4.0"
    assert sources[0]["attribution_requise"] is True


def test_l_enrichissement_interroge_le_corpus_qui_porte_les_licences():
    """
    Les enrichissements puisent dans le corpus documentaire, jamais ailleurs.

    Compétence visée : C4 (épreuve E1), C10 (E3)

    Les deux collections n'ont pas les mêmes métadonnées :
    `eduai_knowledge_base` porte `source`, `section`, `type` ;
    `eduai_corpus_documentaire` porte `url_source`, `code_licence` et
    `attribution_requise`. Un enrichissement puisé dans la première serait
    **inattribuable** — non par oubli d'affichage, mais parce que l'information
    n'existe pas.
    """
    source = Path("apps/courses/services.py").read_text(encoding="utf-8")

    assert "COLLECTION_DOCUMENTAIRE" in source
    assert "COLLECTION_PEDAGOGIQUE" not in source
    assert "eduai_knowledge_base" not in source.split('"""', 2)[-1], (
        "la collection pédagogique ne doit pas être interrogée par le code"
    )


# --- Le quota --------------------------------------------------------------


def test_le_parcours_ne_decompte_pas_le_quota_de_l_apprenant():
    """
    Un enrichissement que l'apprenant n'a pas demandé ne lui est pas facturé.

    Compétence visée : C13 (épreuve E3), C17 (E4)

    Et le défaut reste le décompte : une dépense non imputée doit être un cas
    déclaré, jamais un oubli.
    """
    orchestrateur = Path("apps/agents/agent_orchestrator.py").read_text(encoding="utf-8")
    services = Path("apps/courses/services.py").read_text(encoding="utf-8")

    assert "def answer_question(self, question, sans_quota=False)" in orchestrateur, (
        "le défaut doit être le décompte"
    )
    assert "if not sans_quota:" in orchestrateur
    assert "origine != AjoutDeFiche.PARCOURS" in services, (
        "seul le parcours échappe au décompte"
    )


# --- Les pages -------------------------------------------------------------


@pytest.mark.django_db
def test_le_catalogue_distingue_les_trois_etats(client, competence, apprenante):
    """
    Publié, provisoire et aucun cours se lisent en toutes lettres.

    Compétence visée : C17 (épreuve E4), C13 (E3) — accessibilité

    La distinction ne peut pas reposer sur une nuance de couleur : elle décide
    de la confiance que l'apprenant accorde à ce qu'il lit.
    """
    client.force_login(apprenante)
    page = client.get(reverse("courses:catalogue"), secure=True).content.decode()

    assert "Aucun cours" in page
    CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="P", contenu="…")
    page = client.get(reverse("courses:catalogue"), secure=True).content.decode()
    assert "Cours provisoire" in page


@pytest.mark.django_db
def test_la_page_de_cours_annonce_le_statut_avant_la_lecture(
        client, competence, apprenante):
    """
    Un cours provisoire porte un bandeau, pas une note en pied de page.

    Compétence visée : C17 (épreuve E4), C13 (E3)
    """
    CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PROVISOIRE,
        titre="P", contenu="le contenu")
    client.force_login(apprenante)

    page = client.get(reverse("courses:page_de_cours", args=[competence.code]),
                      secure=True).content.decode()

    assert "Cours provisoire" in page
    assert "n'a été relu par personne" in page
    assert page.index("Cours provisoire") < page.index("le contenu"), (
        "le statut doit être annoncé avant le contenu"
    )


@pytest.mark.django_db
def test_la_fiche_vide_dit_ce_qui_la_remplira(client, competence, apprenante):
    """
    L'état vide propose une suite, il ne constate pas un manque.

    Compétence visée : C17 (épreuve E4)
    """
    client.force_login(apprenante)
    page = client.get(reverse("courses:ma_fiche", args=[competence.code]),
                      secure=True).content.decode()

    assert "Votre fiche est encore vide" in page
    assert "Ouvrir le cours" in page


@pytest.mark.django_db
def test_l_arrivee_d_un_ajout_est_annoncee_aux_lecteurs_d_ecran(
        client, competence, apprenante):
    """
    Un contenu inséré après le chargement doit être annoncé.

    Compétence visée : C13 (épreuve E3) — accessibilité
    """
    client.force_login(apprenante)
    page = client.get(reverse("courses:page_de_cours", args=[competence.code]),
                      secure=True).content.decode()

    assert 'aria-live="polite"' in page
    assert 'role="status"' in page


@pytest.mark.django_db
def test_la_fiche_est_unique_par_apprenant_et_par_competence(competence, apprenante):
    """
    Une seule fiche par compétence : pas une collection d'ajouts séparés.

    Compétence visée : C17 (épreuve E4)
    """
    premiere = fiche_de(apprenante, competence)
    seconde = fiche_de(apprenante, competence)
    assert premiere.pk == seconde.pk
    assert FicheDApprenant.objects.filter(apprenant=apprenante).count() == 1


# --- L'import des supports de l'organisme ---------------------------------


@pytest.mark.django_db
def test_les_supports_de_l_organisme_deviennent_des_cours_publies(competence):
    """
    Les fichiers markdown du répertoire deviennent lisibles dans l'application.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Les 41 supports de `data/contents/courses/` servaient de contexte au RAG et
    remplissaient une liste déroulante de sujets. **Aucune page n'affichait leur
    contenu**, et `CoursDeReference` comptait zéro ligne : la couche existait,
    rien ne l'alimentait.
    """
    call_command("importer_cours", stdout=StringIO())

    cours = CoursDeReference.objects.filter(
        competence=competence, remplace_le__isnull=True).first()
    assert cours is not None, "la compétence doit porter un cours"
    assert cours.statut == CoursDeReference.PUBLIE, (
        "un support écrit par l'organisme est publié, pas provisoire"
    )
    assert len(cours.contenu) > 1000
    assert "\n## " in cours.contenu, "les supports deviennent des sections"


@pytest.mark.django_db
def test_l_import_est_idempotent(competence):
    """
    Relancer l'import ne laisse qu'un cours actif par compétence.

    Compétence visée : C4 (épreuve E1) — intégrité
    """
    call_command("importer_cours", stdout=StringIO())
    call_command("importer_cours", stdout=StringIO())

    actifs = CoursDeReference.objects.filter(
        competence=competence, remplace_le__isnull=True)
    assert actifs.count() == 1
    assert CoursDeReference.objects.filter(competence=competence).count() == 2, (
        "le cours remplacé est conservé, jamais supprimé"
    )


def test_le_rattachement_des_supports_est_une_donnee_pas_du_code():
    """
    Aucun nom de fichier n'est écrit dans le code de l'import.

    Compétence visée : C17 (épreuve E4)

    Le rattachement d'un support à une compétence est choisi, jamais déduit
    (décision 027). Il vit dans un fichier de données qu'on corrige sans
    toucher au code, et l'import est idempotent.
    """
    source = Path("apps/courses/management/commands/importer_cours.py").read_text(
        encoding="utf-8")
    corps = source.split('"""', 2)[-1]

    assert ".md" not in corps, "aucun nom de support dans le code"
    assert "rattachement-cours.json" in source

    carte = json.loads(
        Path("apps/courses/donnees/rattachement-cours.json").read_text(encoding="utf-8"))
    assert carte["rattachements"], "le fichier de rattachement doit être renseigné"
    assert "_non_rattaches" in carte, (
        "les supports écartés sont nommés, avec leur motif : un fichier absent "
        "de la liste ne doit pas ressembler à un oubli"
    )


@pytest.mark.django_db
def test_le_cours_est_rendu_en_html_et_non_en_markdown_brut(
        client, competence, apprenante):
    """
    « Disponible » ne suffit pas : le cours doit être lisible.

    Compétence visée : C17 (épreuve E4), C13 (E3)
    """
    call_command("importer_cours", stdout=StringIO())
    client.force_login(apprenante)

    page = client.get(reverse("courses:page_de_cours", args=[competence.code]),
                      secure=True).content.decode()

    assert "<h2" in page, "les titres doivent être rendus"
    assert "cours-rendu" in page, "le conteneur qui porte les styles du rendu"
