"""
Contrôles de la couche de transformation.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C3 (épreuve E1) — nettoyage et agrégation

Les quatre tests sur les clés de déduplication gardent la décision 011 : le vrai
risque n'était pas de rater des doublons, mais d'en inventer. Sur le corpus, 40
enregistrements sont de vrais doublons, tandis que 359 partagent une URL et 34 un
titre sans en être — ce sont les sections d'un même fichier découpé. Dédupliquer
sur l'URL aurait supprimé dix-huit des dix-neuf sections d'un même document, et
le corpus aurait paru plus propre pour cette raison même.
"""

from __future__ import annotations

from data_pipeline.transform.deduplication import dedupliquer
from data_pipeline.transform.homogeneisation_formats import (
    code_licence,
    normaliser_mots_cles,
    normaliser_texte,
)


def _document(identifiant, contenu, url=None, titre="Titre", metadonnees=None):
    return {
        "identifiant": identifiant,
        "titre": titre,
        "contenu": contenu,
        "source_url": url,
        "mots_cles": [],
        "metadonnees": metadonnees or {},
        "extrait_le": "2026-08-27T10:00:00+00:00",
    }


# --- Ce qui doit être dédupliqué ----------------------------------------

def test_deux_documents_de_meme_identifiant_sont_fusionnes():
    """
    Un identifiant en double désigne un vrai doublon.

    Compétence visée : C3 (épreuve E1)
    """
    documents = [
        _document("so_1", "même contenu"),
        _document("so_1", "même contenu"),
    ]
    resultat, rapport = dedupliquer(documents)

    assert len(resultat) == 1
    assert rapport["doublons_identifiant"] == 1


def test_deux_contenus_identiques_sous_des_identifiants_differents_sont_fusionnes():
    """
    Le même texte arrivé par deux chemins reste un seul document.

    Compétence visée : C3 (épreuve E1)

    Les identifiants sont préfixés par extracteur : un texte présent à la fois
    dans l'API et dans le dump porte deux identifiants distincts. Seule
    l'empreinte du contenu les rapproche.
    """
    documents = [
        _document("so_1", "texte partagé"),
        _document("se_datascience_9", "texte partagé"),
    ]
    resultat, rapport = dedupliquer(documents)

    assert len(resultat) == 1
    assert rapport["doublons_contenu"] == 1


# --- Ce qui ne doit SURTOUT PAS l'être ----------------------------------

def test_une_url_partagee_ne_fait_pas_un_doublon():
    """
    Dix-neuf sections d'un même fichier partagent son URL sans être identiques.

    Compétence visée : C3 (épreuve E1) — non-régression, décision 011

    C'est le piège de la déduplication sur ce corpus : 359 enregistrements
    partagent une URL. Les fusionner supprimerait dix-huit sections sur
    dix-neuf pour le seul fichier `itertools-module.md`.
    """
    documents = [
        _document(f"fichier_{n}", f"section numéro {n}", url="courses/itertools.md")
        for n in range(19)
    ]
    resultat, _ = dedupliquer(documents)

    assert len(resultat) == 19, (
        "l'URL ne doit jamais servir de clé de déduplication"
    )


def test_un_titre_partage_ne_fait_pas_un_doublon():
    """
    Deux sections homonymes de contenus différents restent deux documents.

    Compétence visée : C3 (épreuve E1) — non-régression, décision 011
    """
    documents = [
        _document("a", "premier contenu", titre="Exemples"),
        _document("b", "second contenu", titre="Exemples"),
    ]
    resultat, _ = dedupliquer(documents)

    assert len(resultat) == 2


def test_la_fusion_conserve_la_tracabilite_du_doublon():
    """
    Fusionner ne doit pas perdre ce que le doublon apportait.

    Compétence visée : C1 (épreuve E1) — traçabilité de la collecte

    La question `so_16476924` a été trouvée par le tag « python » puis par le
    tag « pandas ». Jeter la seconde copie ferait perdre l'information que la
    question a été atteinte par deux chemins de collecte.
    """
    documents = [
        _document("so_1", "contenu", metadonnees={"tag_recherche": "python"}),
        _document("so_1", "contenu", metadonnees={"tag_recherche": "pandas"}),
    ]
    resultat, _ = dedupliquer(documents)

    tags = resultat[0]["metadonnees"]["tag_recherche"]
    assert sorted(tags) == ["pandas", "python"], (
        "les deux chemins de collecte doivent survivre à la fusion"
    )


def test_la_deduplication_est_deterministe():
    """
    Le même corpus donne toujours le même résultat.

    Compétence visée : C1 (épreuve E1) — idempotence
    """
    documents = [
        _document("a", "un"),
        _document("b", "deux"),
        _document("a", "un"),
    ]
    premier, _ = dedupliquer(list(documents))
    second, _ = dedupliquer(list(documents))

    assert [d["identifiant"] for d in premier] == [d["identifiant"] for d in second]


# --- Homogénéisation ----------------------------------------------------

def test_l_indentation_du_code_est_preservee():
    """
    La normalisation du texte ne touche pas à l'indentation.

    Compétence visée : C3 (épreuve E1)

    Réduire les suites d'espaces rendrait le corpus plus régulier et casserait
    l'indentation du code Python qu'il contient. Un extrait désindenté est
    syntaxiquement faux, donc pire qu'absent dans un index sémantique.
    """
    code = "def f():\n    if True:\n        return 1"
    assert normaliser_texte(code) == code


def test_les_lignes_vides_en_serie_sont_reduites():
    """
    Trois sauts de ligne ou plus deviennent un paragraphe.

    Compétence visée : C3 (épreuve E1)
    """
    assert normaliser_texte("a\n\n\n\n\nb") == "a\n\nb"


def test_les_mots_cles_acceptent_les_deux_formats_de_dump():
    """
    « |python|pandas| » et « <python><pandas> » donnent le même résultat.

    Compétence visée : C3 (épreuve E1)

    Les dumps récents et anciens n'écrivent pas les étiquettes de la même
    manière. Le même code doit produire le même résultat sur les deux, sans
    quoi la comparaison entre volumes porterait sur deux traitements différents.
    """
    assert normaliser_mots_cles("|python|pandas|") == ["pandas", "python"]
    assert normaliser_mots_cles("<python><pandas>") == ["pandas", "python"]


def test_les_mots_cles_sont_normalises_et_dedoublonnes():
    """
    Casse unifiée, doublons retirés, ordre stable.

    Compétence visée : C3 (épreuve E1)
    """
    assert normaliser_mots_cles(["Python", "python", "PANDAS"]) == ["pandas", "python"]


def test_une_licence_inconnue_ne_se_rabat_pas_sur_une_licence_voisine():
    """
    Une licence non reconnue vaut None, jamais une approximation.

    Compétence visée : C4 (épreuve E1) — conditions de réutilisation

    Rattacher d'office « CC BY-SA 3.0 » à « CC-BY-SA-4.0 » ferait redistribuer
    1 663 documents sous des conditions qui ne sont pas les leurs. Une licence
    mal identifiée engage la redistribution du corpus.
    """
    assert code_licence("CC BY-SA 4.0") == "CC-BY-SA-4.0"
    assert code_licence("CC BY-SA 3.0") == "CC-BY-SA-3.0"
    assert code_licence("Licence inventée") is None
    assert code_licence(None) is None
