"""
Tests de l'empreinte du corpus vectoriel.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C13 (E3) — livraison ; C20 (E5) — sonde de santé

Depuis la décision 023, le corpus voyage sur un volume persistant et non plus
dans l'image : il peut donc être plus ancien que le code qui l'interroge.
L'empreinte est le seul dispositif qui rende cet écart constatable. Ces tests
portent sur ce qu'elle doit garantir en toutes circonstances — et d'abord sur
le fait qu'elle ne mette jamais la sonde de santé en défaut.
"""

import json

import pytest

from apps.rag import empreinte_corpus


def test_l_empreinte_absente_ne_leve_pas(tmp_path, monkeypatch):
    """
    Un corpus sans empreinte rend `None`, jamais une exception.

    Compétence visée : C13 (épreuve E3), C20 (épreuve E5)

    `lire()` est appelée par `/ai/sante`, dont la raison d'être est de
    répondre quand quelque chose ne va pas. Une sonde qui échoue parce que
    l'objet observé est en défaut n'observe rien.
    """
    monkeypatch.setattr(empreinte_corpus, "FICHIER_EMPREINTE",
                        tmp_path / "EMPREINTE.json")

    assert empreinte_corpus.lire() is None


def test_une_empreinte_illisible_ne_leve_pas(tmp_path, monkeypatch):
    """
    Un fichier d'empreinte corrompu rend `None`, jamais une exception.

    Compétence visée : C13 (épreuve E3), C20 (épreuve E5)

    Le fichier traverse un téléversement : il peut arriver tronqué. C'est
    précisément le cas où la sonde doit continuer de répondre.
    """
    fichier = tmp_path / "EMPREINTE.json"
    fichier.write_text('{"date_releve": "2026-08-30T', encoding="utf-8")
    monkeypatch.setattr(empreinte_corpus, "FICHIER_EMPREINTE", fichier)

    assert empreinte_corpus.lire() is None


def test_l_empreinte_relue_est_celle_qui_a_ete_ecrite(tmp_path, monkeypatch):
    """
    Ce que `ecrire()` pose, `lire()` le rend à l'identique.

    Compétence visée : C13 (épreuve E3)
    """
    fichier = tmp_path / "EMPREINTE.json"
    monkeypatch.setattr(empreinte_corpus, "FICHIER_EMPREINTE", fichier)
    releve = {
        "date_releve": "2026-08-30T15:43:32+00:00",
        "empreinte_sha256": "a" * 64,
        "octets_base": 140_701_696,
        "modele_embarquement": "mxbai-embed-large",
        "collections": {"eduai_corpus_documentaire": 21189,
                        "eduai_knowledge_base": 387},
    }

    empreinte_corpus.ecrire(releve)

    assert empreinte_corpus.lire() == releve
    assert json.loads(fichier.read_text(encoding="utf-8")) == releve


def test_un_corpus_absent_interrompt_le_releve(tmp_path, monkeypatch):
    """
    Sans corpus, aucune empreinte n'est produite.

    Compétence visée : C13 (épreuve E3)

    Une empreinte produite sur un corpus absent décrirait le vide, et serait
    téléversée comme si elle décrivait quelque chose. C'est le motif de
    l'incident 001 — un traitement qui s'annonce réussi sur rien.
    """
    monkeypatch.setattr(empreinte_corpus, "CHEMIN_CORPUS", tmp_path / "absent")

    with pytest.raises(FileNotFoundError):
        empreinte_corpus.verifier_le_corpus()


def test_un_repertoire_sans_base_chroma_interrompt_le_releve(tmp_path,
                                                             monkeypatch):
    """
    Un répertoire présent mais vide n'est pas un corpus.

    Compétence visée : C13 (épreuve E3)

    C'est le cas d'un volume monté mais jamais peuplé : le chemin existe, le
    corpus non. Les distinguer évite de conclure d'une arborescence à un
    contenu.
    """
    corpus = tmp_path / "chroma"
    corpus.mkdir()
    monkeypatch.setattr(empreinte_corpus, "CHEMIN_CORPUS", corpus)
    monkeypatch.setattr(empreinte_corpus, "BASE_CHROMA",
                        corpus / "chroma.sqlite3")

    with pytest.raises(FileNotFoundError):
        empreinte_corpus.verifier_le_corpus()


def test_une_collection_illisible_vaut_absente_et_non_zero(tmp_path,
                                                           monkeypatch):
    """
    Une collection introuvable est relevée `None`, pas `0`.

    Compétence visée : C13 (épreuve E3)

    « Je n'ai pas trouvé la collection » et « la collection est vide » sont
    deux états différents. Les confondre est ce que ce projet a déjà payé :
    un chargement annoncé réussi sur une base restée vide (incident 001).
    """
    class ClientSansCollection:
        def get_collection(self, nom):
            raise ValueError(f"collection {nom} introuvable")

    faux_chromadb = type("chromadb", (), {
        "PersistentClient": staticmethod(lambda path: ClientSansCollection()),
    })
    monkeypatch.setitem(__import__("sys").modules, "chromadb", faux_chromadb)
    monkeypatch.setattr(empreinte_corpus, "CHEMIN_CORPUS", tmp_path)

    releve = empreinte_corpus.relever_collections()

    assert releve == {"eduai_corpus_documentaire": None,
                      "eduai_knowledge_base": None}
    assert 0 not in releve.values()


def test_la_somme_de_controle_change_avec_le_contenu(tmp_path):
    """
    Deux corpus différents n'ont pas la même empreinte.

    Compétence visée : C13 (épreuve E3)

    C'est la propriété qui fait tout le dispositif : sans elle, comparer
    l'empreinte du serveur à celle du poste ne prouverait rien.
    """
    premier = tmp_path / "un.sqlite3"
    second = tmp_path / "deux.sqlite3"
    premier.write_bytes(b"corpus du 29 aout")
    second.write_bytes(b"corpus du 30 aout")

    assert (empreinte_corpus.somme_de_controle(premier)
            != empreinte_corpus.somme_de_controle(second))
    assert (empreinte_corpus.somme_de_controle(premier)
            == empreinte_corpus.somme_de_controle(premier))
