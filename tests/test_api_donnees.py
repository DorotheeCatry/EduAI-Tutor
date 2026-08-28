"""
Contrôles de l'API du jeu de données.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données
Compétence visée : C4 (épreuve E1) — respect des conditions de licence

Le cœur de ce fichier est le contrôle du filtrage par licence **sur trois
vecteurs**. Une exigence RGPD vérifiée sur un seul chemin d'accès n'est pas
vérifiée : il suffit d'un point de terminaison écrit un jour sans y penser pour
diffuser ce qui ne doit pas l'être. C'est pourquoi le filtre vit dans le
gestionnaire par défaut du modèle, et pourquoi ce fichier l'éprouve par la
liste, par l'accès direct et par la recherche.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def acces_lecture_seule(django_db_blocker):
    """
    Autorise l'accès à la base réelle, en lecture seule.

    Compétence visée : C18 (épreuve E4)

    Choix : `django_db_blocker.unblock()` plutôt que le marqueur `django_db`.
    Motivation : ce marqueur crée et détruit des bases de TEST, ce qui n'a pas
    de sens ici — les modèles sont en `managed = False`, leur schéma appartient
    aux scripts SQL du pipeline, et ce qu'on éprouve est le comportement du
    gestionnaire d'exposition sur le corpus réellement chargé.

    Le blocage de pytest-django existe pour empêcher un test d'écrire dans une
    base de production par mégarde. Ici, aucun test n'écrit : ils comptent et
    ils lisent. Le déblocage est donc explicite et circonscrit à ce module,
    plutôt que désactivé globalement.
    """
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def modeles(base_donnees):
    """
    Charge les modèles de l'API après amorçage de Django.

    Compétence visée : C18 (épreuve E4)
    """
    import django

    django.setup()
    from apps.api_data import models

    return models


def _un_document_non_diffusable(modeles):
    """Renvoie l'identifiant d'un document que l'API ne doit pas servir."""
    from django.db import connections

    with connections["eduai_data"].cursor() as curseur:
        curseur.execute("""
            SELECT d.id_document, d.titre
              FROM document d JOIN licence l ON l.code_licence = d.code_licence
             WHERE l.redistribution_autorisee = FALSE
             LIMIT 1
        """)
        return curseur.fetchone()


# --- Le filtrage par licence, sur trois vecteurs -------------------------

def test_le_gestionnaire_exclut_les_documents_non_diffusables(modeles, corpus_charge):
    """
    Vecteur 1 : la liste ne contient aucun document non redistribuable.

    Compétence visée : C4 (épreuve E1)
    """
    from django.db import connections

    with connections["eduai_data"].cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document d
              JOIN licence l ON l.code_licence = d.code_licence
             WHERE l.redistribution_autorisee = FALSE
        """)
        non_diffusables = curseur.fetchone()[0]

    if non_diffusables == 0:
        pytest.skip("aucun document non diffusable en base : rien à écarter")

    exposes = modeles.Document.objects.count()
    codes = set(
        modeles.Document.objects.values_list("licence__redistribution_autorisee", flat=True)
    )
    assert codes <= {True}, "l'API expose un document dont la licence interdit la diffusion"
    assert exposes > 0


def test_un_document_non_diffusable_est_introuvable_en_acces_direct(modeles, corpus_charge):
    """
    Vecteur 2 : connaître l'identifiant ne suffit pas à obtenir le document.

    Compétence visée : C4 (épreuve E1)

    C'est le vecteur qu'un filtrage posé dans la vue de liste laisserait
    ouvert : la vue de détail n'y passe pas.
    """
    cible = _un_document_non_diffusable(modeles)
    if cible is None:
        pytest.skip("aucun document non diffusable en base")

    id_document, _ = cible
    assert not modeles.Document.objects.filter(id_document=id_document).exists(), (
        f"le document {id_document} est atteignable par son identifiant"
    )


def test_un_document_non_diffusable_est_introuvable_par_la_recherche(modeles, corpus_charge):
    """
    Vecteur 3 : la recherche plein texte ne le ramène pas non plus.

    Compétence visée : C4 (épreuve E1)

    La recherche construit son propre jeu de requêtes ; si elle partait d'un
    gestionnaire non filtré, elle rendrait ce que les deux autres chemins
    refusent.
    """
    from django.contrib.postgres.search import SearchQuery, SearchVector

    from apps.api_data.filtres import CONFIGURATION_RECHERCHE

    cible = _un_document_non_diffusable(modeles)
    if cible is None:
        pytest.skip("aucun document non diffusable en base")

    id_document, titre = cible
    terme = (titre or "").split()[0] if titre else None
    if not terme:
        pytest.skip("le document témoin n'a pas de titre exploitable")

    vecteur = SearchVector("titre", "contenu", config=CONFIGURATION_RECHERCHE)
    requete = SearchQuery(terme, config=CONFIGURATION_RECHERCHE)
    trouves = (
        modeles.Document.objects.annotate(v=vecteur).filter(v=requete)
        .values_list("id_document", flat=True)
    )

    assert id_document not in set(trouves), (
        "la recherche plein texte ramène un document que l'API ne doit pas servir"
    )


def test_le_gestionnaire_exclut_les_documents_retires(modeles, corpus_charge):
    """
    Un document disparu de sa source n'est plus servi, mais reste en base.

    Compétence visée : C4 (épreuve E1) — décision 013

    La disparition d'une section entre deux scrapings est une information sur la
    source, pas une erreur : on la marque au lieu de la purger. Le document
    conserve ses lignes de collecte, et sort du corpus servi.
    """
    from django.db import connections

    with connections["eduai_data"].cursor() as curseur:
        curseur.execute("SELECT id_document FROM document WHERE retire_le IS NOT NULL LIMIT 1")
        ligne = curseur.fetchone()

    if ligne is None:
        pytest.skip("aucun document marqué retiré")

    assert not modeles.Document.objects.filter(id_document=ligne[0]).exists()


def test_le_decompte_par_source_ne_compte_que_l_exposable(modeles, corpus_charge):
    """
    `/sources/` n'annonce pas plus de documents que la liste n'en sert.

    Compétence visée : C5 (épreuve E1)

    Les agrégations traversant la relation inverse n'appliquent pas le
    gestionnaire du modèle lié : la condition doit y être réécrite. Ce contrôle
    garde les deux formulations alignées — annoncer 380 documents pour une
    source dont l'API n'en sert que 298 ferait passer un filtrage voulu pour une
    panne.
    """
    from django.db.models import Count

    sources = modeles.Source.objects.annotate(
        n=Count("documents", filter=modeles.condition_exposable_depuis_source(), distinct=True)
    )
    for source in sources:
        servis = modeles.Document.objects.filter(source_id=source.code_source).count()
        assert source.n == servis, (
            f"source {source.code_source} : {source.n} annoncés, {servis} servis"
        )


# --- Lecture seule -------------------------------------------------------

def test_le_routeur_refuse_toute_ecriture(modeles):
    """
    L'ORM ne peut pas écrire dans le jeu de données.

    Compétence visée : C5 (épreuve E1) — décision 012

    Premier des trois garde-fous superposés. Les deux autres — l'absence de
    route d'écriture et le rôle PostgreSQL restreint au SELECT — tiennent même
    si celui-ci cède.
    """
    from apps.api_data.routeurs import EcritureInterdite, RouteurJeuDonnees

    with pytest.raises(EcritureInterdite):
        RouteurJeuDonnees().db_for_write(modeles.Document)


def test_aucune_migration_n_est_permise_sur_le_jeu_de_donnees():
    """
    Le schéma appartient aux scripts SQL, pas aux migrations Django.

    Compétence visée : C4 (épreuve E1) — décision 006

    Les deux règles comptent autant l'une que l'autre : ne pas migrer les
    modèles de l'API, et ne rien migrer DANS eduai_data. Sans la seconde,
    `migrate` y créerait le schéma applicatif de Django.
    """
    from apps.api_data.routeurs import RouteurJeuDonnees

    routeur = RouteurJeuDonnees()
    assert routeur.allow_migrate("default", "api_data") is False
    assert routeur.allow_migrate("eduai_data", "users") is False
