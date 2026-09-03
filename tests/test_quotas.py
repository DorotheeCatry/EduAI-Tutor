"""
Contrôles des quotas de génération.

Compétence visée : C13 (épreuve E3) — maîtrise du coût en production
Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C4 (épreuve E1) — compteur en base

Ces contrôles portent sur ce qui protège le budget avant la mise en ligne.
Aucun n'appelle le fournisseur de modèles : le décompte est éprouvé pour
lui-même, en amont de toute dépense, ce qui est exactement l'endroit où il doit
agir.

Le test le plus important du fichier n'est pas celui du plafond, c'est
`test_le_refus_remonte_a_l_appelant_sans_etre_avale` : les méthodes de
l'orchestrateur entourent leur corps d'un `except Exception` qui renvoie un
dictionnaire d'erreur. Un décompte placé à l'intérieur de ce bloc serait
silencieusement transformé en panne technique, et le refus n'atteindrait jamais
l'apprenant.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.quotas import service
from apps.quotas.models import ConsommationJournaliere
from apps.quotas.service import (
    QuotaDepasse,
    consommer,
    consommer_pour_le_service_ia,
    etat,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def apprenant(django_user_model):
    """Un compte apprenant sans consommation."""
    return django_user_model.objects.create_user(
        username="apprenant_quota",
        email="apprenant.quota@exemple.test",
        password="motdepasse-de-test-sans-valeur",
    )


@pytest.fixture
def autre_apprenant(django_user_model):
    """Un second compte, pour éprouver le plafond global."""
    return django_user_model.objects.create_user(
        username="apprenant_quota_bis",
        email="apprenant.quota.bis@exemple.test",
        password="motdepasse-de-test-sans-valeur",
    )


@pytest.fixture
def plafonds(monkeypatch):
    """
    Plafonds explicites pour la durée d'un test.

    Compétence visée : C18 (épreuve E4)

    Choix : passer par l'environnement plutôt que par un réglage Django.
    Motivation : c'est ainsi que le service lit ses plafonds en production. Un
    test qui contournerait cette lecture ne dirait rien de la configuration
    réelle — et c'est précisément la configuration qui sera fautive un jour.
    """
    def regler(individuel: int, global_: int) -> None:
        monkeypatch.setenv("EDUAI_QUOTA_GENERATIONS_PAR_JOUR", str(individuel))
        monkeypatch.setenv("EDUAI_PLAFOND_GENERATIONS_PAR_JOUR", str(global_))

    return regler


# --- Le quota non atteint laisse passer -----------------------------------

def test_sous_le_quota_la_generation_est_autorisee(apprenant, plafonds):
    """
    Trois générations sur un quota de cinq passent, et sont comptées.

    Compétence visée : C13 (épreuve E3)
    """
    plafonds(individuel=5, global_=100)

    for attendu in (1, 2, 3):
        assert consommer(apprenant) == attendu

    assert etat(apprenant)["restantes"] == 2


def test_le_compteur_vit_en_base_et_non_en_memoire(apprenant, plafonds):
    """
    La consommation est relue depuis la base, pas depuis un objet Python.

    Compétence visée : C4 (épreuve E1)

    Un compteur en mémoire de processus ne survit ni au redémarrage ni à la
    présence de plusieurs travailleurs — chacun ayant le sien, le plafond
    serait multiplié par leur nombre.
    """
    plafonds(individuel=5, global_=100)
    consommer(apprenant)
    consommer(apprenant)

    ligne = ConsommationJournaliere.objects.get(
        utilisateur=apprenant, jour=timezone.localdate(),
    )
    assert ligne.generations == 2


# --- Le quota atteint refuse ----------------------------------------------

def test_au_quota_la_generation_est_refusee(apprenant, plafonds):
    """
    La sixième génération d'un quota de cinq est refusée.

    Compétence visée : C13 (épreuve E3)
    """
    plafonds(individuel=5, global_=100)
    for _ in range(5):
        consommer(apprenant)

    with pytest.raises(QuotaDepasse) as refus:
        consommer(apprenant)

    assert refus.value.portee == "individuel"
    # Le message est destiné à un apprenant, pas à un journal : il dit ce qui
    # se passe et quand cela reprend.
    assert "minuit" in refus.value.message


def test_un_refus_ne_decompte_rien(apprenant, plafonds):
    """
    Une génération refusée ne consomme pas de quota.

    Compétence visée : C13 (épreuve E3)

    Sans ce contrôle, un compteur incrémenté avant le refus repousserait
    indéfiniment la réouverture : chaque tentative refusée creuserait la dette.
    """
    plafonds(individuel=2, global_=100)
    consommer(apprenant)
    consommer(apprenant)

    for _ in range(3):
        with pytest.raises(QuotaDepasse):
            consommer(apprenant)

    ligne = ConsommationJournaliere.objects.get(
        utilisateur=apprenant, jour=timezone.localdate(),
    )
    assert ligne.generations == 2


def test_le_quota_d_une_personne_n_entame_pas_celui_d_une_autre(
    apprenant, autre_apprenant, plafonds,
):
    """
    Les compteurs sont individuels.

    Compétence visée : C13 (épreuve E3)
    """
    plafonds(individuel=2, global_=100)
    consommer(apprenant)
    consommer(apprenant)

    with pytest.raises(QuotaDepasse):
        consommer(apprenant)

    assert consommer(autre_apprenant) == 1


# --- La remise à zéro -----------------------------------------------------

def test_le_compteur_repart_a_zero_le_lendemain(apprenant, plafonds, monkeypatch):
    """
    Un quota épuisé la veille n'empêche pas de générer aujourd'hui.

    Compétence visée : C13 (épreuve E3)

    Le jour de référence est déplacé plutôt que l'horloge système : ce que le
    test doit éprouver, c'est que le compteur est bien indexé sur le jour, pas
    la capacité de la suite à voyager dans le temps.
    """
    plafonds(individuel=3, global_=100)

    hier = timezone.localdate() - timedelta(days=1)
    monkeypatch.setattr(service, "_jour_courant", lambda: hier)
    for _ in range(3):
        consommer(apprenant)
    with pytest.raises(QuotaDepasse):
        consommer(apprenant)

    monkeypatch.undo()
    plafonds(individuel=3, global_=100)

    assert consommer(apprenant) == 1
    # La ligne de la veille est conservée : deux compteurs distincts, pas un
    # compteur réinitialisé. L'historique de consommation reste lisible.
    assert ConsommationJournaliere.objects.filter(utilisateur=apprenant).count() == 2


# --- Le plafond global ----------------------------------------------------

def test_le_plafond_global_arrete_le_service_meme_sous_le_quota_individuel(
    apprenant, autre_apprenant, plafonds,
):
    """
    Deux comptes sous leur quota sont malgré tout refusés au plafond global.

    Compétence visée : C13 (épreuve E3)

    C'est la protection réelle : le quota individuel ne borne rien tant que le
    nombre d'inscriptions n'est pas borné. Un service ouvert peut être vidé par
    cinquante comptes respectant chacun scrupuleusement ses cinq générations.
    """
    plafonds(individuel=10, global_=3)

    consommer(apprenant)
    consommer(apprenant)
    consommer(autre_apprenant)

    # Aucun des deux n'a atteint son quota de dix.
    assert etat(apprenant)["restantes"] == 8

    with pytest.raises(QuotaDepasse) as refus:
        consommer(autre_apprenant)

    assert refus.value.portee == "global"
    assert "consultation" in refus.value.message


# --- L'absence de compte --------------------------------------------------

def test_aucune_generation_anonyme(plafonds):
    """
    Sans compte identifié, la génération est refusée.

    Compétence visée : C13 (épreuve E3)

    Un appel anonyme dépense sans que rien ne soit décomptable. Le seul chemin
    du projet dans ce cas — la génération de quiz par WebSocket — impute
    désormais la dépense à l'hôte du salon.
    """
    plafonds(individuel=5, global_=100)

    with pytest.raises(QuotaDepasse) as refus:
        consommer(None)

    assert refus.value.portee == "anonyme"


# --- La lecture des plafonds ----------------------------------------------

def test_un_plafond_absent_retombe_sur_une_valeur_prudente(monkeypatch):
    """
    Une variable absente restreint, elle n'ouvre pas.

    Compétence visée : C13 (épreuve E3)
    """
    monkeypatch.delenv("EDUAI_QUOTA_GENERATIONS_PAR_JOUR", raising=False)
    monkeypatch.delenv("EDUAI_PLAFOND_GENERATIONS_PAR_JOUR", raising=False)

    assert service.quota_individuel() == service.QUOTA_INDIVIDUEL_DEFAUT
    assert service.plafond_global() == service.PLAFOND_GLOBAL_DEFAUT


@pytest.mark.parametrize("valeur_fautive", ["illimité", "-1", "", "5.5"])
def test_un_plafond_illisible_retombe_sur_le_defaut(monkeypatch, valeur_fautive):
    """
    Un réglage fautif ne devient pas un service sans limite.

    Compétence visée : C13 (épreuve E3)

    Le cas « -1 » est le plus dangereux des quatre : un entier négatif est
    lisible, et une comparaison naïve l'aurait accepté comme plafond — donc
    refusé toute génération, ou selon le sens de la comparaison, autorisé
    toutes. Ni l'un ni l'autre n'est ce qu'on veut d'un réglage mal saisi.
    """
    monkeypatch.setenv("EDUAI_QUOTA_GENERATIONS_PAR_JOUR", valeur_fautive)

    assert service.quota_individuel() == service.QUOTA_INDIVIDUEL_DEFAUT


# --- Le refus atteint-il l'appelant ? -------------------------------------

def test_le_refus_remonte_a_l_appelant_sans_etre_avale(apprenant, plafonds):
    """
    `QuotaDepasse` traverse l'orchestrateur au lieu de devenir une erreur.

    Compétence visée : C13 (épreuve E3)
    Compétence visée : C18 (épreuve E4)

    Les trois méthodes génératrices de l'orchestrateur entourent leur corps
    d'un `except Exception` qui renvoie `{'success': False, 'error': ...}`.
    Un décompte placé à l'intérieur de ce bloc serait transformé en panne
    technique : l'apprenant lirait « une erreur est survenue » au lieu de
    « vous avez utilisé vos générations du jour », et l'interface l'inviterait
    à réessayer sans fin.

    Le test appelle la méthode sur un objet minimal plutôt que sur un
    orchestrateur complet : construire ce dernier chargerait les chaînes RAG et
    le corpus vectoriel, sans rien ajouter à ce qui est éprouvé ici — le
    décompte a lieu avant que `self` serve à autre chose.
    """
    from apps.agents.agent_orchestrator import AIOrchestrator

    plafonds(individuel=1, global_=100)
    consommer(apprenant)

    faux_orchestrateur = SimpleNamespace(
        user=apprenant, current_module=None, pour_service_ia=False,
    )
    # `_decompter` est une méthode de la classe, pas de l'objet minimal :
    # elle est liée explicitement, comme le fera l'orchestrateur réel.
    faux_orchestrateur._decompter = (
        lambda: AIOrchestrator._decompter(faux_orchestrateur)
    )

    for methode, arguments in (
        (AIOrchestrator.generate_course, ("les listes",)),
        (AIOrchestrator.answer_question, ("qu'est-ce qu'une liste ?",)),
        (AIOrchestrator.create_quiz, ("les listes", 5)),
    ):
        with pytest.raises(QuotaDepasse):
            methode(faux_orchestrateur, *arguments)


# --- L'API du service IA (C9) ----------------------------------------------

def test_le_service_ia_ne_se_voit_pas_appliquer_de_quota_individuel(plafonds):
    """
    Les appels de l'API dépassent le quota individuel sans être refusés.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C13 (épreuve E3)

    Ses consommateurs sont des programmes porteurs d'une clé de service : il
    n'y a aucun apprenant à qui imputer cinq générations. Leur limitation
    propre est le débit par clé, appliqué à l'entrée de l'API.
    """
    plafonds(individuel=2, global_=100)

    for attendu in (1, 2, 3, 4):
        assert consommer_pour_le_service_ia() == attendu


def test_le_service_ia_est_soumis_au_plafond_global(plafonds):
    """
    Le plafond du jour vaut aussi pour l'API.

    Compétence visée : C13 (épreuve E3)

    Sans cela, l'API serait le trou par lequel le budget se vide, et le
    plafond ne bornerait qu'une moitié des dépenses.
    """
    plafonds(individuel=100, global_=2)

    consommer_pour_le_service_ia()
    consommer_pour_le_service_ia()

    with pytest.raises(QuotaDepasse) as refus:
        consommer_pour_le_service_ia()

    assert refus.value.portee == "global"


def test_les_deux_chemins_alimentent_le_meme_plafond(apprenant, plafonds):
    """
    Application web et API se partagent le plafond du jour.

    Compétence visée : C13 (épreuve E3)

    C'est le budget du projet qui est borné, pas celui de chaque façade prise
    séparément. Deux plafonds distincts autoriseraient le double de dépense
    sans que personne ne l'ait décidé.
    """
    plafonds(individuel=10, global_=3)

    consommer(apprenant)
    consommer_pour_le_service_ia()
    consommer(apprenant)

    with pytest.raises(QuotaDepasse) as refus:
        consommer_pour_le_service_ia()
    assert refus.value.portee == "global"

    with pytest.raises(QuotaDepasse) as refus:
        consommer(apprenant)
    assert refus.value.portee == "global"


def test_le_service_ia_tient_sur_une_seule_ligne_par_jour(plafonds):
    """
    Les appels de l'API s'agrègent, ils ne créent pas une ligne chacun.

    Compétence visée : C4 (épreuve E1)

    PostgreSQL considère deux NULL comme distincts : sans la contrainte
    partielle posée sur le modèle, chaque appel créerait sa propre ligne et le
    compteur du service resterait à 1 indéfiniment.
    """
    plafonds(individuel=10, global_=100)

    consommer_pour_le_service_ia()
    consommer_pour_le_service_ia()
    consommer_pour_le_service_ia()

    lignes = ConsommationJournaliere.objects.filter(
        utilisateur__isnull=True, jour=timezone.localdate(),
    )
    assert lignes.count() == 1
    assert lignes.first().generations == 3


# --- L'affichage du compteur ----------------------------------------------

def test_le_compteur_est_expose_aux_gabarits(apprenant, plafonds, rf):
    """
    Le processeur de contexte publie l'état du quota.

    Compétence visée : C17 (épreuve E4)

    Un apprenant ne doit pas découvrir le plafond au moment du refus : le
    compteur s'affiche sur les pages qui déclenchent une génération.
    """
    from apps.quotas.context import quota_generation

    plafonds(individuel=5, global_=100)
    consommer(apprenant)

    requete = rf.get("/")
    requete.user = apprenant

    etat_affiche = quota_generation(requete)["quota_generation"]
    assert etat_affiche["restantes"] == 4
    assert etat_affiche["quota"] == 5


def test_le_compteur_ne_coute_aucune_requete_tant_qu_il_n_est_pas_lu(
    apprenant, plafonds, rf, django_assert_num_queries,
):
    """
    Le calcul est différé jusqu'au premier accès depuis un gabarit.

    Compétence visée : C17 (épreuve E4)

    Sans ce report, chaque page du site paierait une agrégation pour un
    compteur que la plupart n'affichent pas — un coût prélevé sur toutes les
    pages au profit de quatre.
    """
    from apps.quotas.context import quota_generation

    plafonds(individuel=5, global_=100)
    requete = rf.get("/")
    requete.user = apprenant

    with django_assert_num_queries(0):
        contexte = quota_generation(requete)

    # La lecture, elle, interroge bien la base.
    assert contexte["quota_generation"]["restantes"] == 5


def test_aucun_compteur_pour_une_visite_anonyme(rf):
    """
    Sans compte, il n'y a pas de compteur à afficher.

    Compétence visée : C17 (épreuve E4)
    """
    from django.contrib.auth.models import AnonymousUser

    from apps.quotas.context import quota_generation

    requete = rf.get("/")
    requete.user = AnonymousUser()

    # Le contrôle porte sur la valeur de vérité et non sur `is None` : le
    # processeur renvoie un objet différé, qui n'est pas `None` lui-même mais
    # s'évalue à faux — et c'est bien cette évaluation que fait le `{% if %}`
    # du gabarit.
    assert not quota_generation(requete)["quota_generation"]


def test_le_gabarit_annonce_le_quota_epuise(apprenant, plafonds, rf):
    """
    Le fragment d'affichage dit ce qui se passe, en toutes lettres.

    Compétence visée : C17 (épreuve E4) — accessibilité

    L'information n'est pas portée par la seule couleur : un compteur épuisé se
    lit. Le contrôle porte donc sur le texte rendu, pas sur les classes CSS.
    """
    from django.template.loader import render_to_string

    from apps.quotas.context import quota_generation

    plafonds(individuel=2, global_=100)
    consommer(apprenant)
    consommer(apprenant)

    requete = rf.get("/")
    requete.user = apprenant

    rendu = render_to_string(
        "quotas/_compteur_generations.html", quota_generation(requete),
    )

    assert "vos 2 générations du jour" in rendu
    assert "minuit" in rendu
    assert 'role="status"' in rendu


def test_la_page_de_generation_affiche_le_compteur(apprenant, plafonds, client):
    """
    Le compteur est bien inclus dans la page, pas seulement disponible.

    Compétence visée : C17 (épreuve E4)
    Compétence visée : C18 (épreuve E4)

    Un processeur de contexte qui publie une valeur qu'aucun gabarit n'inclut
    ne se voit pas : la valeur existe, l'apprenant ne la lit jamais. Ce
    contrôle passe par la page réelle pour éviter cet écart — c'est le même
    motif que la sonde de monitorage branchée sans effet (incident 003).
    """
    from django.urls import reverse

    plafonds(individuel=5, global_=100)
    consommer(apprenant)
    client.force_login(apprenant)

    # `secure=True` : voir tests/test_effacement_compte.py — hors DEBUG, la
    # redirection HTTPS répond 301 avant la vue, et l'intégration continue ne
    # définit pas DJANGO_DEBUG. La requête est simulée en HTTPS, comme en
    # production, plutôt que la redirection désactivée.
    reponse = client.get(reverse("courses:catalogue"), secure=True)

    assert reponse.status_code == 200
    contenu = reponse.content.decode("utf-8")
    assert "Il vous reste" in contenu
    assert "génération" in contenu
