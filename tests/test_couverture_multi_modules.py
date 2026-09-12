"""
L'import de cours n'est plus verrouillé sur un seul module.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C21 (E5) — traitement des anomalies ; C10 (E3)

Le référentiel déclare quatre modules et vingt et une compétences. Sept
compétences portaient un cours, quatorze n'en portaient aucun — et la cause
n'était pas seulement l'absence de matière : `rattachement-cours.json` ne
déclarait qu'un unique couple index/répertoire, si bien que l'import n'aurait
rien pris même si les supports avaient été déposés (réserve 25).

Ces tests défendent trois propriétés : plusieurs corpus sont importés, leurs
parties se rassemblent par compétence au lieu de s'écraser, et un écart dans
n'importe lequel arrête tout avant publication.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.courses.models import CoursDeReference
from apps.referentiel.models import Competence

FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer",
                 stdout=StringIO())


def _poser_un_corpus(racine, nom_module, fichiers, sous_module="01_bases"):
    """Crée un répertoire de supports et son index, et rend les deux chemins."""
    repertoire = racine / nom_module
    repertoire.mkdir(parents=True)
    for nom, contenu in fichiers.items():
        (repertoire / nom).write_text(contenu, encoding="utf-8")

    index = racine / f"{nom_module}_index.json"
    index.write_text(json.dumps({sous_module: list(fichiers)}), encoding="utf-8")
    return str(index), str(repertoire)


def _carte(racine, entrees):
    """Écrit un fichier de rattachement à plusieurs corpus, et rend son chemin."""
    chemin = racine / "rattachement.json"
    chemin.write_text(json.dumps({"corpus": entrees}, ensure_ascii=False),
                      encoding="utf-8")
    return str(chemin)


@pytest.mark.django_db
def test_deux_corpus_alimentent_deux_modules(tmp_path, referentiel):
    """
    Deux modules distincts reçoivent chacun leur cours.

    Compétence visée : C17 (épreuve E4)

    C'est la propriété que le fichier à plat rendait impossible : un seul
    couple index/répertoire y était déclaré, donc un seul module pouvait être
    servi, quelle que soit la matière présente ailleurs.
    """
    index_py, rep_py = _poser_un_corpus(
        tmp_path, "python", {"variables.md": "# Les variables\n\nDu contenu."})
    index_sql, rep_sql = _poser_un_corpus(
        tmp_path, "sql", {"jointures.md": "# Les jointures\n\nDu contenu."})

    carte = _carte(tmp_path, [
        {"module": "Python", "index": index_py, "repertoire": rep_py,
         "sous_modules": {"01_bases": {"competence": "types-et-variables",
                                       "titre": "Types et variables"}}},
        {"module": "SQL", "index": index_sql, "repertoire": rep_sql,
         "sous_modules": {"01_bases": {"competence": "joindre",
                                       "titre": "Joindre des tables"}}},
    ])

    call_command("importer_cours", rattachement=carte, stdout=StringIO())

    actifs = {c.competence.code: c for c in CoursDeReference.objects
              .filter(remplace_le__isnull=True).select_related("competence")}
    assert "types-et-variables" in actifs
    assert "joindre" in actifs, (
        "le second corpus doit être importé, pas ignoré"
    )
    assert actifs["joindre"].titre == "Joindre des tables"


@pytest.mark.django_db
def test_deux_corpus_sur_une_meme_competence_s_additionnent(tmp_path, referentiel):
    """
    Le second corpus n'efface pas le travail du premier.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    `publier_le_cours` met de côté le cours actif de la compétence et en publie
    un neuf. Publier corpus par corpus aurait donc fait remplacer, par le
    second, le cours que le premier venait de publier sur la même compétence.
    Les parties sont rassemblées avant publication, pas après.
    """
    index_a, rep_a = _poser_un_corpus(
        tmp_path, "premier", {"a.md": "# A\n\nPremière partie."})
    index_b, rep_b = _poser_un_corpus(
        tmp_path, "second", {"b.md": "# B\n\nSeconde partie."})

    rattachement = {"01_bases": {"competence": "modeliser",
                                 "titre": "Modéliser"}}
    carte = _carte(tmp_path, [
        {"index": index_a, "repertoire": rep_a, "sous_modules": rattachement},
        {"index": index_b, "repertoire": rep_b, "sous_modules": rattachement},
    ])

    call_command("importer_cours", rattachement=carte, stdout=StringIO())

    cours = CoursDeReference.objects.get(
        competence=Competence.objects.get(code="modeliser"),
        remplace_le__isnull=True)
    fichiers = {p.fichier_source for p in cours.parties.all()}
    assert fichiers == {"a.md", "b.md"}, (
        "les parties des deux corpus doivent coexister dans le même cours"
    )


@pytest.mark.django_db
def test_un_ecart_dans_un_seul_corpus_arrete_tout(tmp_path, referentiel):
    """
    Rien n'est publié tant qu'un corpus ne concorde pas.

    Compétence visée : C21 (épreuve E5)

    C'est la règle d'origine — « aucun cours n'a été publié » — étendue au cas
    de plusieurs corpus. Vérifier au fil de l'eau aurait publié les premiers
    avant d'échouer sur le dernier, et la promesse ne vaudrait plus.
    """
    index_bon, rep_bon = _poser_un_corpus(
        tmp_path, "bon", {"a.md": "# A\n\nContenu."})
    index_faux, rep_faux = _poser_un_corpus(
        tmp_path, "faux", {"b.md": "# B\n\nContenu."})
    # Un fichier declaré dans l'index et absent du disque.
    (tmp_path / "faux_index.json").write_text(
        json.dumps({"01_bases": ["b.md", "fantome.md"]}), encoding="utf-8")

    carte = _carte(tmp_path, [
        {"index": index_bon, "repertoire": rep_bon,
         "sous_modules": {"01_bases": {"competence": "types-et-variables",
                                       "titre": "T"}}},
        {"index": index_faux, "repertoire": rep_faux,
         "sous_modules": {"01_bases": {"competence": "joindre", "titre": "J"}}},
    ])

    with pytest.raises(SystemExit) as sortie:
        call_command("importer_cours", rattachement=carte, stdout=StringIO())

    assert "fantome.md" in str(sortie.value)
    assert CoursDeReference.objects.count() == 0, (
        "le corpus valide ne doit pas non plus avoir été publié"
    )


@pytest.mark.django_db
def test_la_forme_a_plat_reste_acceptee(tmp_path, referentiel):
    """
    Un fichier de rattachement à corpus unique fonctionne toujours.

    Compétence visée : C18 (épreuve E4)

    L'option `--rattachement` permet de passer un autre fichier : la liste est
    un élargissement, pas un remplacement.
    """
    index, repertoire = _poser_un_corpus(
        tmp_path, "seul", {"a.md": "# A\n\nContenu."})
    chemin = tmp_path / "a-plat.json"
    chemin.write_text(json.dumps({
        "index": index, "repertoire": repertoire,
        "sous_modules": {"01_bases": {"competence": "types-et-variables",
                                      "titre": "Types et variables"}},
    }), encoding="utf-8")

    call_command("importer_cours", rattachement=str(chemin), stdout=StringIO())

    assert CoursDeReference.objects.filter(remplace_le__isnull=True).count() == 1


# --- Le diaporama entre dans le corpus vectoriel ---------------------------


def test_le_format_pptx_est_lu():
    """
    Un diaporama rend son texte, diapositive par diapositive.

    Compétence visée : C10 (épreuve E3), C4 (E1)

    `data/contents/courses/03_sql/` porte le seul support hors Python du dépôt,
    au format `.pptx`, que `prepare_chroma` ignorait : il n'était ni indexé ni
    consultable. Le format figure désormais parmi ceux qu'il lit.
    """
    from pathlib import Path

    from apps.rag.scripts.prepare_chroma import SUPPORTED_TEXT_EXTS, load_document

    assert ".pptx" in SUPPORTED_TEXT_EXTS

    support = Path("data/contents/courses/03_sql/relations entre les tables.pptx")
    if not support.exists():
        pytest.skip("support SQL absent de cette machine")

    documents = load_document(support)

    assert len(documents) == 1
    contenu = documents[0].page_content
    assert documents[0].metadata["type"] == "pptx"
    assert "## Diapositive 1" in contenu, "la structure par diapositive est gardée"
    assert "One-to-Many" in contenu, "le contenu des diapositives est bien extrait"
