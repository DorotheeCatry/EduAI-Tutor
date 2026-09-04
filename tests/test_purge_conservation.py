"""
La purge par ancienneté : ce qu'elle supprime, et ce qu'elle refuse de faire.

Compétence visée : C4 (épreuve E1) — durée de conservation
Compétences concernées : C2 (E1) ; C21 (E5)

Le schéma portait une durée de conservation par source depuis l'origine, la
requête était écrite, et **rien ne l'exécutait**. Une durée qu'aucun programme
n'applique est une intention, pas une mesure.

Ces tests portent sur la garantie qui compte : la purge ne valide sa
transaction que si la base a supprimé exactement ce que le dénombrement avait
annoncé. C'est la leçon de l'incident 001 — un chargement s'était annoncé
réussi sur une base restée vide, parce qu'il comptait ce qu'il croyait avoir
écrit plutôt que ce que la base avait fait.

La connexion est simulée : ces tests éprouvent la logique de sûreté, pas le
moteur PostgreSQL. Le critère SQL lui-même a été éprouvé sur les données
réelles, dans une transaction annulée — 1 273 documents annoncés, 1 273
supprimés, spécialisations et rattachements emportés par les cascades.
"""

import pytest

from data_pipeline.load import purge


class CurseurFactice:
    """Rend des lignes préparées, et retient les requêtes exécutées."""

    def __init__(self, denombrement, suppression):
        self.denombrement = denombrement
        self.suppression = suppression
        self.dernier = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, requete):
        # Les deux fichiers commencent par leur en-tête commenté : on cherche
        # donc le verbe dans le corps, pas au premier caractère.
        self.dernier = ("suppression" if "DELETE FROM document" in requete
                        else "denombrement")

    @property
    def description(self):
        return [("code_source",), ("nom",), ("duree_conservation_jours",),
                ("documents_echus",), ("plus_ancien",)]

    def fetchall(self):
        return self.denombrement if self.dernier == "denombrement" else self.suppression


class ConnexionFactice:
    def __init__(self, denombrement, suppression):
        self.curseur = CurseurFactice(denombrement, suppression)
        self.valide = False
        self.annulee = False

    def cursor(self):
        return self.curseur

    def commit(self):
        self.valide = True

    def rollback(self):
        self.annulee = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _brancher(monkeypatch, denombrement, suppression):
    connexion = ConnexionFactice(denombrement, suppression)
    monkeypatch.setattr(purge, "_connexion", lambda: connexion)
    return connexion


def test_a_blanc_ne_supprime_rien_et_annule_la_transaction(monkeypatch):
    """
    Compétence visée : C4 (épreuve E1)

    Une purge doit pouvoir être constatée avant d'être subie.
    """
    connexion = _brancher(monkeypatch,
                          [("s1", "Stack Overflow", 365, 12, None)], [])

    bilan = purge.executer(a_blanc=True)

    assert bilan["a_blanc"] is True
    assert bilan["attendu"] == 12 and bilan["supprimes"] == 0
    assert connexion.annulee is True and connexion.valide is False


def test_la_transaction_est_validee_quand_les_comptes_concordent(monkeypatch):
    """
    Compétence visée : C4 (épreuve E1)
    """
    connexion = _brancher(monkeypatch,
                          [("s1", "Stack Overflow", 365, 2, None)],
                          [(1, "s1", None), (2, "s1", None)])

    bilan = purge.executer()

    assert bilan["supprimes"] == 2 and bilan["attendu"] == 2
    assert connexion.valide is True and connexion.annulee is False


def test_un_ecart_entre_l_annonce_et_le_fait_annule_tout(monkeypatch):
    """
    La purge refuse de valider ce qu'elle n'avait pas annoncé.

    Compétence visée : C4 (épreuve E1)
    Compétence concernée : C21 (E5)

    Si la base supprime autre chose que ce qui était échu — une contrainte
    changée, une jointure qui dérive — la transaction est annulée. Constater
    l'écart après validation ne servirait à rien : les documents seraient
    partis.
    """
    connexion = _brancher(monkeypatch,
                          [("s1", "Stack Overflow", 365, 2, None)],
                          [(1, "s1", None)])

    with pytest.raises(RuntimeError, match="Transaction annulée"):
        purge.executer()

    assert connexion.annulee is True and connexion.valide is False


def test_une_base_sans_document_echu_ne_valide_aucune_ecriture(monkeypatch):
    """
    Compétence visée : C4 (épreuve E1)

    Le cas courant : aucune durée n'est échue. La purge doit le dire et ne
    rien faire — c'est l'état du corpus aujourd'hui, âgé de dix jours pour des
    conservations de 90 et 365 jours.
    """
    connexion = _brancher(monkeypatch, [], [])

    bilan = purge.executer()

    assert bilan["attendu"] == 0 and bilan["supprimes"] == 0
    assert connexion.valide is True, "une purge vide reste une transaction close"


def test_les_deux_requetes_existent_et_disent_ce_qu_elles_font():
    """
    Compétence visée : C2 (épreuve E1)

    Deux fichiers, deux verbes : le lecteur d'un fichier nommé « purge » doit
    voir un DELETE, celui d'un « dénombrement » un SELECT. Une requête qui
    supprime ou non selon un drapeau se relit trop tard.
    """
    import re as _re

    def sans_commentaire(texte):
        """Le corps de la requête, l'en-tête retiré : c'est lui qui agit."""
        return _re.sub(r"/\*.*?\*/", "", texte, flags=_re.S).strip()

    denombrement = sans_commentaire(purge.DENOMBREMENT.read_text(encoding="utf-8"))
    suppression = sans_commentaire(purge.SUPPRESSION.read_text(encoding="utf-8"))

    assert denombrement.startswith("SELECT") and "DELETE" not in denombrement
    assert suppression.startswith("DELETE FROM document")
    assert "RETURNING" in suppression, "le décompte doit venir de la base"
    for requete in (denombrement, suppression):
        assert "duree_conservation_jours IS NOT NULL" in requete, (
            "une durée absente signifie « sans terme » et exclut la source"
        )
    for fichier in (purge.DENOMBREMENT, purge.SUPPRESSION):
        assert "Compétence visée" in fichier.read_text(encoding="utf-8"), (
            "chaque requête porte son en-tête documenté"
        )
