"""
Ce qui a été retiré ne revient pas, et ce qui est branché le reste.

Compétence visée : C18 (épreuve E4) — qualité et non-régression
Compétences concernées : C1 (E1) ; C3 (E1) ; C4 (E1) ; C10 (E3)

Un relevé du 12/09/2026 a montré que le dépôt portait plusieurs dispositifs
qui n'étaient atteints par rien : deux points d'API sans appelant, deux vues
rendant des gabarits d'une ligne, un modèle Django dont la table restait vide,
un script qui ne s'importait même plus, et un contrat de transformation que ni
la transformation ni le chargement n'employaient.

Le code mort n'est pas seulement encombrant : il ment. Il décrit un dispositif
qui n'existe pas, et personne ne le corrige puisque personne ne l'exécute.
Ces tests tiennent les deux bouts du ménage.
"""

import json
from pathlib import Path

import pytest
from django.urls import NoReverseMatch, reverse


# --- Ce qui a été retiré ---------------------------------------------------


@pytest.mark.parametrize("nom", [
    "courses:modules_api",
    "courses:sections_api",
    "quiz:result",
    "revision:review",
])
def test_les_urls_mortes_ont_disparu(nom):
    """
    Compétence visée : C18 (épreuve E4)

    Les deux premières menaient à des vues que ni gabarit ni script n'appelait.
    Les deux suivantes rendaient des gabarits d'une seule ligne — `{% load
    i18n %}` — donc des pages blanches, atteignables par quiconque tapait
    l'adresse.
    """
    with pytest.raises(NoReverseMatch):
        reverse(nom)


def test_le_modele_coursesection_a_disparu():
    """
    Compétence visée : C4 (épreuve E1)

    Un modèle Django non employé n'est pas inerte : il crée une table, une clé
    étrangère et une contrainte d'unicité, et il apparaît au schéma comme si le
    dispositif existait. Sa table était vide, et le découpage des cours est
    porté par `PartieDeCours`.
    """
    import apps.courses.models as modeles

    assert not hasattr(modeles, "CourseSection")


def test_contexte_general_a_disparu():
    """
    Compétence visée : C10 (épreuve E3)

    Le défaut « page sans contexte » est tenu par le panneau du tuteur, en
    JavaScript. Une seconde formulation côté serveur, que rien n'appelait,
    n'aurait pu que diverger de celle qui s'exécute.
    """
    import apps.chat.contexte as contexte

    assert not hasattr(contexte, "contexte_general")


# --- Ce qui doit rester atteignable ----------------------------------------


def test_le_script_de_preparation_du_corpus_s_importe():
    """
    `prepare_chroma` s'importe, donc peut être lancé.

    Compétence visée : C18 (épreuve E4), C10 (E3)

    Il importait `apps.rag.module_index_map`, un module de compatibilité
    supprimé le 30/08/2026. Le script levait donc `ModuleNotFoundError` avant
    d'exécuter une seule ligne, et rien ne le signalait puisque rien ne
    l'importe. C'est lui qui construit la collection pédagogique
    `eduai_knowledge_base` ; sans lui, elle n'est plus reconstructible.
    """
    import importlib

    module = importlib.import_module("apps.rag.scripts.prepare_chroma")

    assert module.MODULE_INDEX_MAP, (
        "la carte des index doit être peuplée depuis data/contents/index/"
    )


def test_les_six_sources_sont_branchees_au_point_de_lancement():
    """
    Le flux orchestré sait reproduire le corpus qu'il a chargé.

    Compétence visée : C1 (épreuve E1), C3 (E1)

    S6 avait sa décision (039), sa réserve (20), son extracteur de 22 Ko, et le
    transformeur comme le chargeur savaient la traiter — mais la table `SOURCES`
    de l'orchestrateur ne la portait pas. Son fichier brut existe pourtant, avec
    1 005 enregistrements : l'extraction avait été lancée à la main. Le point de
    lancement unique ne savait donc pas reproduire son propre jeu de données.
    """
    from data_pipeline.orchestrator import SOURCES

    codes = [code for code, _libelle, _classe in SOURCES]

    assert codes == ["s1", "s2", "s3", "s4", "s5", "s6"]
    # Cinq TYPES pour six sources : S2 et S6 sont deux scrapings distincts.
    assert len({classe for _c, _l, classe in SOURCES}) == 6, (
        "une classe d'extracteur par source, jamais une abstraction commune"
    )


# --- Le contrat de transformation ------------------------------------------


def test_le_contrat_de_transformation_est_reellement_applique():
    """
    Il est importé et appelé par la couche qu'il gouverne.

    Compétence visée : C3 (épreuve E1)

    Ce contrat était écrit, documenté, présenté en en-tête comme « le contrat
    de sortie de la couche de transformation » — et importé par personne. Il
    avait d'ailleurs déjà dérivé sans que rien ne le dise : le champ
    `code_source`, ajouté au corpus réel avec la sixième source, n'y figurait
    pas.
    """
    source = Path("data_pipeline/transform/transformer.py").read_text(
        encoding="utf-8")

    assert "from .contrat_transforme import DocumentTransforme" in source
    assert "DocumentTransforme.depuis_dict" in source


def test_un_document_hors_contrat_arrete_la_transformation():
    """
    L'écart est levé avant la moindre écriture.

    Compétence visée : C3 (épreuve E1), C21 (E5)

    Le chargeur écrit dans une base contrainte. Un corpus hors contrat l'y
    ferait échouer une ligne à la fois, à l'insertion, après avoir déjà écrit
    les précédentes. S'arrêter avant d'écrire le fichier coûte moins cher.
    """
    from data_pipeline.transform.contrat_transforme import DocumentTransforme

    with pytest.raises(TypeError):
        DocumentTransforme.depuis_dict({"identifiant": "x"})      # champs manquants

    with pytest.raises(TypeError):
        DocumentTransforme.depuis_dict(_document_valide() | {"inconnu": 1})


def test_le_corpus_reel_respecte_le_contrat():
    """
    Le contrat décrit le corpus qui existe, pas un corpus idéal.

    Compétence visée : C3 (épreuve E1), C4 (E1)

    C'est ce test qui aurait vu la dérive de `code_source`. Il est sauté si le
    corpus transformé n'a pas été produit sur cette machine — il éprouve une
    donnée, pas du code.
    """
    corpus = Path("data_pipeline/data/processed/corpus.jsonl")
    if not corpus.exists():
        pytest.skip("corpus transformé absent de cette machine")

    from data_pipeline.transform.contrat_transforme import DocumentTransforme

    with corpus.open(encoding="utf-8") as flux:
        for rang, ligne in enumerate(flux):
            DocumentTransforme.depuis_dict(json.loads(ligne))
    assert rang > 0


def _document_valide() -> dict:
    """Un document minimal conforme au contrat, pour les cas d'écart."""
    return {
        "identifiant": "x", "titre": "t", "contenu": "c",
        "code_type_source": "scraping", "code_source": "s2",
        "source_nom": "n", "source_url": None,
        "code_licence": None, "licence_declaree": "d",
        "langue": "fr", "extrait_le": "2026-09-12T00:00:00+00:00",
        "cree_le": None,
    }
