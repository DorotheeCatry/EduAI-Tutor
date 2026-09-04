"""
Purge des documents dont la durée de conservation est échue.

Compétence visée : C4 (épreuve E1) — durée de conservation
Compétences concernées : C2 (E1) ; C21 (E5)

Le schéma portait une durée de conservation par source depuis l'origine, la
requête de purge était écrite, et **rien ne l'exécutait**. Une durée de
conservation qu'aucun programme n'applique est une intention, pas une mesure :
c'est exactement le motif que ce projet a documenté trois fois — du code écrit,
atteignable, que rien n'appelle.

Ce module est ce qui manquait. Il ne planifie rien : l'ordonnancement relève de
l'hébergeur, et la procédure est décrite dans `docs/chaine_livraison.md`. Il
rend la purge exécutable, constatable et rejouable.

Usage :
    uv run python -m data_pipeline.load.purge --a-blanc   # compte, n'écrit pas
    uv run python -m data_pipeline.load.purge             # supprime
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

REPERTOIRE_SQL = Path(__file__).resolve().parent / "sql"
DENOMBREMENT = REPERTOIRE_SQL / "05_purge_denombrement.sql"
SUPPRESSION = REPERTOIRE_SQL / "05_purge_conservation.sql"


def _connexion():
    """
    Ouvre la connexion au jeu de données, comme le chargeur.

    Compétence visée : C4 (épreuve E1)

    Choix : le compte d'écriture du pipeline, et non le compte de lecture de
    l'API. Motivation : ce dernier n'a pas le droit de supprimer — et c'est
    voulu. Une purge est une écriture ; elle passe par le seul compte qui en a
    le droit.
    """
    # Le fichier d'environnement est lu ici comme le chargeur le fait : la
    # purge s'exécute par une tâche planifiée, sans shell qui l'aurait chargé.
    load_dotenv(Path.cwd() / ".env")

    mot_de_passe = os.environ.get("POSTGRES_PASSWORD")
    if not mot_de_passe:
        raise RuntimeError(
            "POSTGRES_PASSWORD est absente de l'environnement. "
            "La renseigner dans le fichier .env (voir .env.example)."
        )
    return psycopg.connect(
        dbname=os.environ.get("POSTGRES_DB", "eduai_data"),
        user=os.environ.get("POSTGRES_USER", "eduai"),
        password=mot_de_passe,
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
        connect_timeout=10,
    )


def denombrer(connexion) -> list[dict]:
    """
    Rend, par source, ce que la purge supprimerait.

    Compétence visée : C4 (épreuve E1)

    Choix : dénombrer AVANT de supprimer, toujours, y compris quand la
    suppression suit immédiatement. Motivation : le compte d'avant est la seule
    façon de dire ensuite si la base a fait ce qu'on lui demandait. C'est la
    leçon de l'incident 001 — un chargement s'était annoncé réussi sur une base
    restée vide, parce qu'il comptait ce qu'il croyait avoir écrit.
    """
    with connexion.cursor() as curseur:
        curseur.execute(DENOMBREMENT.read_text(encoding="utf-8"))
        colonnes = [description[0] for description in curseur.description]
        return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]


def purger(connexion) -> list[tuple]:
    """
    Supprime les documents échus et rend ce qui a réellement été supprimé.

    Compétence visée : C4 (épreuve E1)

    La clause `RETURNING` de la requête rend les lignes effacées : le décompte
    vient de la base, pas d'un compteur tenu par le programme.
    """
    with connexion.cursor() as curseur:
        curseur.execute(SUPPRESSION.read_text(encoding="utf-8"))
        return curseur.fetchall()


def executer(a_blanc: bool = False) -> dict:
    """
    Point de lancement : dénombre, puis supprime si on ne travaille pas à blanc.

    Compétence visée : C4 (épreuve E1)

    Choix : la transaction n'est validée qu'après vérification du compte.
    Motivation : si la base supprime autre chose que ce qu'elle avait annoncé,
    la purge doit être annulée, pas signalée après coup.
    """
    with _connexion() as connexion:
        attendu = denombrer(connexion)
        total_attendu = sum(ligne["documents_echus"] for ligne in attendu)

        for ligne in attendu:
            logger.info(
                "[purge] %s : %s documents échus sur une conservation de %s jours "
                "(le plus ancien : %s)",
                ligne["code_source"], ligne["documents_echus"],
                ligne["duree_conservation_jours"], ligne["plus_ancien"],
            )
        if not total_attendu:
            logger.info("[purge] aucun document échu — rien à supprimer.")

        if a_blanc:
            connexion.rollback()
            return {"a_blanc": True, "attendu": total_attendu, "supprimes": 0,
                    "par_source": attendu}

        supprimes = purger(connexion)
        if len(supprimes) != total_attendu:
            connexion.rollback()
            raise RuntimeError(
                f"La purge a supprimé {len(supprimes)} documents alors que "
                f"{total_attendu} étaient échus. Transaction annulée : une "
                "suppression qui ne correspond pas à ce qui a été annoncé ne "
                "doit pas être validée."
            )
        connexion.commit()
        logger.info("[purge] %s documents supprimés, transaction validée.",
                    len(supprimes))
        return {"a_blanc": False, "attendu": total_attendu,
                "supprimes": len(supprimes), "par_source": attendu}


def main(argv: list[str] | None = None) -> int:
    """Point de lancement en ligne de commande."""
    analyseur = argparse.ArgumentParser(
        description="Supprime les documents dont la durée de conservation est échue.")
    analyseur.add_argument(
        "--a-blanc", action="store_true",
        help="Compte les documents échus sans rien supprimer.")
    arguments = analyseur.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-8s %(message)s")
    try:
        bilan = executer(a_blanc=arguments.a_blanc)
    except (RuntimeError, psycopg.Error) as panne:
        logger.error("[purge] %s", panne)
        return 1

    verbe = "seraient supprimés" if bilan["a_blanc"] else "supprimés"
    print(f"{bilan['attendu']} document(s) {verbe}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
