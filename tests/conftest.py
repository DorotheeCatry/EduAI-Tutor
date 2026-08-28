"""
Fixtures communes à la suite de tests.

Compétence visée : C18 (épreuve E4) — tests automatisés

Choix : les tests qui touchent PostgreSQL ou le corpus se **sautent** quand la
dépendance manque, au lieu d'échouer. Motivation : un test rouge doit signifier
« le code est cassé ». S'il peut aussi signifier « la base n'est pas démarrée »,
il cesse d'être un signal — on prend l'habitude de le voir rouge, et le jour où
il l'est pour une vraie raison, personne ne regarde.

Choix : le saut est explicite et motivé dans le message. Un test sauté sans
raison lisible est un test qu'on oublie d'exécuter.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

#: Racine du dépôt, pour retrouver les fichiers de données.
RACINE = Path(__file__).resolve().parent.parent


def _charger_environnement() -> None:
    """
    Charge le fichier .env, comme le font les autres points d'entrée du projet.

    Compétence visée : C18 (épreuve E4)

    Choix : `python-dotenv` plutôt qu'un `source .env` dans le shell.
    Motivation : la clé secrète Django contient des parenthèses et des
    dollars, que le shell interprète — un `source` échoue dessus, et les
    variables déclarées après ne sont pas chargées. Le contrôle passe alors ou
    non selon la position d'une variable dans un fichier, ce qui n'est pas un
    critère.

    Choix : `override=False`. Motivation : en intégration continue, les
    variables viennent de l'environnement du travail et doivent primer sur un
    éventuel fichier local.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(RACINE / ".env", override=False)
    except ImportError:  # pragma: no cover — dotenv est une dépendance du projet
        pass


_charger_environnement()


def _connexion_possible() -> tuple[bool, str]:
    """
    Dit si PostgreSQL est joignable avec le schéma attendu.

    Compétence visée : C18 (épreuve E4)
    """
    mot_de_passe = os.environ.get("POSTGRES_PASSWORD")
    if not mot_de_passe:
        return False, "POSTGRES_PASSWORD absente de l'environnement"
    try:
        import psycopg

        with psycopg.connect(
            dbname=os.environ.get("POSTGRES_DB", "eduai_data"),
            user=os.environ.get("POSTGRES_USER", "eduai"),
            password=mot_de_passe,
            host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            port=os.environ.get("POSTGRES_PORT", "5433"),
            connect_timeout=5,
        ) as connexion:
            with connexion.cursor() as curseur:
                curseur.execute("SELECT to_regclass('public.document')")
                if curseur.fetchone()[0] is None:
                    return False, "la table document n'existe pas dans cette base"
        return True, ""
    except Exception as exception:  # noqa: BLE001 — diagnostic, pas propagation
        return False, f"connexion impossible ({type(exception).__name__}: {exception})"


@pytest.fixture(scope="session")
def base_donnees():
    """
    Connexion à `eduai_data`, ou saut motivé.

    Compétence visée : C18 (épreuve E4)
    """
    joignable, motif = _connexion_possible()
    if not joignable:
        pytest.skip(f"PostgreSQL indisponible : {motif}")

    import psycopg

    connexion = psycopg.connect(
        dbname=os.environ.get("POSTGRES_DB", "eduai_data"),
        user=os.environ.get("POSTGRES_USER", "eduai"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
    )
    # Lecture seule : un test ne doit pas pouvoir modifier la base qu'il observe.
    connexion.read_only = True
    yield connexion
    connexion.close()


@pytest.fixture(scope="session")
def corpus_charge(base_donnees):
    """
    Exige un corpus non vide, et le saute sinon.

    Compétence visée : C18 (épreuve E4)

    En intégration continue, la base est créée par les scripts de schéma mais
    reste vide : reconstituer 6 836 documents y prendrait des heures et exigerait
    les dumps. Les tests qui portent sur le contenu du corpus se sautent donc,
    et le disent.
    """
    with base_donnees.cursor() as curseur:
        curseur.execute("SELECT count(*) FROM document")
        total = curseur.fetchone()[0]
    if total == 0:
        pytest.skip(
            "corpus vide : ces contrôles portent sur des documents chargés, "
            "que l'intégration continue ne reconstitue pas"
        )
    return total


@pytest.fixture
def repertoire_temporaire(tmp_path):
    """Répertoire jetable, propre à chaque test."""
    return tmp_path
