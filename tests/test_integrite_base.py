"""
Contrôles d'intégrité de la base du jeu de données.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C4 (épreuve E1) — base de données et contraintes

Ces contrôles reprennent des vérifications faites en SQL à la main pendant le
chargement. Ils exigent PostgreSQL et se sautent proprement sinon : un test rouge
doit vouloir dire « le code est cassé », pas « la base n'est pas démarrée ».
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_les_cinq_types_de_sources_sont_declares(base_donnees):
    """
    Le référentiel exige cinq types de sources ; la nomenclature les porte.

    Compétence visée : C1 (épreuve E1) — couverture des cinq types

    Ce contrôle tient en une requête, indépendamment de l'état d'avancement des
    extracteurs : c'est la preuve que le modèle couvre l'exigence.
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("SELECT code_type_source FROM type_source ORDER BY 1")
        types = [ligne[0] for ligne in curseur.fetchall()]

    assert set(types) == {
        "api_rest", "scraping", "fichier", "base_donnees", "big_data",
    }


def test_chaque_source_est_rattachee_a_un_type_connu(base_donnees):
    """
    Aucune source orpheline.

    Compétence visée : C4 (épreuve E1)
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM source s
             WHERE NOT EXISTS (SELECT 1 FROM type_source t
                                WHERE t.code_type_source = s.code_type_source)
        """)
        assert curseur.fetchone()[0] == 0


def test_la_partition_des_documents_est_totale(base_donnees, corpus_charge):
    """
    Chaque document appartient à exactement une table fille.

    Compétence visée : C4 (épreuve E1) — spécialisation totale

    La partition est vérifiée par un déclencheur à chaque validation. Ce
    contrôle le confirme sur l'état chargé : un document orphelin signalerait
    que le déclencheur a été contourné ou désactivé.
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document d
             WHERE NOT EXISTS (
                 SELECT 1 FROM document_api_rest     WHERE id_document = d.id_document
                 UNION ALL SELECT 1 FROM document_web           WHERE id_document = d.id_document
                 UNION ALL SELECT 1 FROM document_fichier       WHERE id_document = d.id_document
                 UNION ALL SELECT 1 FROM document_big_data      WHERE id_document = d.id_document
                 UNION ALL SELECT 1 FROM document_base_donnees  WHERE id_document = d.id_document)
        """)
        orphelins = curseur.fetchone()[0]

    assert orphelins == 0, f"{orphelins} document(s) sans table de spécialisation"


def test_aucun_document_ne_porte_une_licence_inconnue(base_donnees, corpus_charge):
    """
    La clé étrangère vers `licence` est respectée sur tout le corpus.

    Compétence visée : C4 (épreuve E1)
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document d
             WHERE NOT EXISTS (SELECT 1 FROM licence l
                                WHERE l.code_licence = d.code_licence)
        """)
        assert curseur.fetchone()[0] == 0


def test_attribution_requise_ne_diverge_pas_de_sa_licence(base_donnees, corpus_charge):
    """
    La colonne dénormalisée reste cohérente avec la nomenclature.

    Compétence visée : C4 (épreuve E1)

    `attribution_requise` est recopiée dans `document` pour permettre une clé
    étrangère composite, qui interdit la divergence. Ce contrôle vérifie que la
    contrainte fait bien son office.
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document d
              JOIN licence l ON l.code_licence = d.code_licence
             WHERE l.attribution_requise <> d.attribution_requise
        """)
        assert curseur.fetchone()[0] == 0


def test_une_licence_exigeant_l_attribution_impose_une_url(base_donnees, corpus_charge):
    """
    Un document CC BY-SA sans URL serait impossible à créditer.

    Compétence visée : C4 (épreuve E1) — respect des conditions de licence
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document
             WHERE attribution_requise AND url_source IS NULL
        """)
        assert curseur.fetchone()[0] == 0


def test_les_comptes_par_source_correspondent_aux_specialisations(base_donnees, corpus_charge):
    """
    Le décompte par type coïncide avec celui des tables filles.

    Compétence visée : C4 (épreuve E1)

    Un écart signalerait un document rattaché à la mauvaise table fille — ce que
    les contraintes de vérification interdisent, et qu'il vaut mieux constater
    que supposer.
    """
    correspondances = {
        "api_rest": "document_api_rest",
        "scraping": "document_web",
        "fichier": "document_fichier",
        "big_data": "document_big_data",
        "base_donnees": "document_base_donnees",
    }
    with base_donnees.cursor() as curseur:
        for type_source, table in correspondances.items():
            curseur.execute(
                "SELECT count(*) FROM document WHERE code_type_source = %s",
                (type_source,),
            )
            attendu = curseur.fetchone()[0]
            curseur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 — table fermée
            assert curseur.fetchone()[0] == attendu, (
                f"{type_source} : {attendu} documents mais une autre quantité dans {table}"
            )


def test_un_statut_de_succes_exige_des_enregistrements(base_donnees):
    """
    La contrainte née de l'incident S1 est bien en place et respectée.

    Compétence visée : C21 (épreuve E5) — non-régression, incident S1 du 26/08

    « Une extraction ne peut pas réussir en ne produisant rien. » La contrainte
    a été écrite après qu'un extracteur eut rendu « succes, 0 enregistrement ».
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM extraction
             WHERE statut = 'succes' AND nb_enregistrements = 0
        """)
        assert curseur.fetchone()[0] == 0

        curseur.execute("""
            SELECT count(*) FROM extraction
             WHERE statut = 'vide' AND nb_enregistrements <> 0
        """)
        assert curseur.fetchone()[0] == 0, (
            "le statut « vide » ne doit pas devenir un moyen de contourner la contrainte"
        )


def test_un_retrait_n_est_jamais_anterieur_a_la_derniere_observation(base_donnees):
    """
    La chronologie du cycle de vie d'un document est cohérente.

    Compétence visée : C4 (épreuve E1)
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("""
            SELECT count(*) FROM document
             WHERE retire_le IS NOT NULL AND retire_le < dernier_vu_le
        """)
        assert curseur.fetchone()[0] == 0
