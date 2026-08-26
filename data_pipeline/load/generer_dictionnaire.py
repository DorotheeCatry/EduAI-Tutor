"""
Engendre le dictionnaire de données de la base eduai_data.

Compétence visée : C4 (épreuve E1) — dictionnaire de données

Choix : lire les scripts SQL plutôt que d'interroger une base en fonctionnement.
Motivation : ces scripts *sont* la source de la base — le conteneur PostgreSQL
la construit à partir d'eux au premier démarrage. Les lire donne donc le même
résultat qu'interroger `information_schema`, sans exiger qu'une base tourne
pour produire un livrable documentaire. Un jury qui clone le dépôt peut
régénérer le dictionnaire immédiatement.

Choix : bibliothèque standard uniquement, aucune dépendance ajoutée. Motivation :
un générateur de documentation ne doit pas alourdir l'environnement d'exécution
du projet.

Sortie : docs/dictionnaire_donnees_eduai_data.md
Lancement : uv run python -m data_pipeline.load.generer_dictionnaire
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances ---

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

REPERTOIRE_SQL = Path("data_pipeline/load/sql")
FICHIER_SORTIE = Path("docs/dictionnaire_donnees_eduai_data.md")


@dataclass
class Colonne:
    """Une colonne de table, telle que déclarée dans le script de schéma."""

    nom: str
    type_sql: str
    obligatoire: bool
    commentaire: str = ""
    cle: str = ""  # « PK », « FK », « PK, FK » ou vide


@dataclass
class Table:
    """Une table du schéma, avec ses colonnes et ses contraintes."""

    nom: str
    commentaire: str = ""
    colonnes: list[Colonne] = field(default_factory=list)
    contraintes: list[str] = field(default_factory=list)


# --- 2. Règles logiques de traitement ---


def retirer_commentaires(sql: str) -> str:
    """
    Retire les commentaires SQL, en préservant les chaînes littérales.

    Compétence visée : C4 (épreuve E1)

    Choix : traitement ligne à ligne plutôt qu'une expression régulière globale.
    Motivation : les descriptions passées à COMMENT ON contiennent des tirets et
    des apostrophes ; une expression régulière naïve couperait au milieu d'une
    chaîne.
    """
    lignes = []
    for ligne in sql.splitlines():
        position = ligne.find("--")
        # On ne coupe que si le « -- » n'est pas à l'intérieur d'une chaîne.
        if position != -1 and ligne[:position].count("'") % 2 == 0:
            ligne = ligne[:position]
        lignes.append(ligne.rstrip())
    sans_ligne = "\n".join(lignes)
    return re.sub(r"/\*.*?\*/", "", sans_ligne, flags=re.DOTALL)


def lire_commentaires(sql: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Collecte les COMMENT ON TABLE et COMMENT ON COLUMN du script.

    Compétence visée : C4 (épreuve E1)
    """
    tables: dict[str, str] = {}
    colonnes: dict[str, str] = {}

    for correspondance in re.finditer(
        r"COMMENT ON TABLE\s+(\w+)\s+IS\s+'(.*?)';", sql, re.DOTALL
    ):
        tables[correspondance.group(1)] = correspondance.group(2).replace("''", "'")

    for correspondance in re.finditer(
        r"COMMENT ON COLUMN\s+(\w+)\.(\w+)\s+IS\s+'(.*?)';", sql, re.DOTALL
    ):
        cle = f"{correspondance.group(1)}.{correspondance.group(2)}"
        colonnes[cle] = correspondance.group(3).replace("''", "'")

    return tables, colonnes


def lire_tables(sql_sans_commentaires: str) -> list[Table]:
    """
    Extrait les tables, leurs colonnes et leurs contraintes du script de schéma.

    Compétence visée : C4 (épreuve E1)

    Choix : analyse par expressions régulières plutôt qu'un analyseur SQL
    complet. Motivation : le script analysé est écrit par le projet et suit une
    mise en forme constante ; introduire une dépendance d'analyse syntaxique
    pour ce seul usage serait disproportionné. La contrepartie est assumée :
    ce générateur ne prétend pas analyser du SQL quelconque.
    """
    tables: list[Table] = []

    for bloc in re.finditer(
        r"CREATE TABLE (\w+) \((.*?)\n\);", sql_sans_commentaires, re.DOTALL
    ):
        table = Table(nom=bloc.group(1))
        cles_primaires: set[str] = set()
        cles_etrangeres: set[str] = set()

        for ligne in bloc.group(2).splitlines():
            ligne = ligne.strip().rstrip(",")
            if not ligne:
                continue

            if ligne.upper().startswith("CONSTRAINT"):
                table.contraintes.append(ligne)
                if pk := re.search(r"PRIMARY KEY \(([^)]*)\)", ligne):
                    cles_primaires |= {c.strip() for c in pk.group(1).split(",")}
                if fk := re.search(r"FOREIGN KEY \(([^)]*)\)", ligne):
                    cles_etrangeres |= {c.strip() for c in fk.group(1).split(",")}
                continue

            # Ligne de continuation d'une contrainte multi-ligne : ignorée.
            if ligne.upper().startswith(("REFERENCES", "CHECK", "PRIMARY", "UNIQUE", "FOREIGN")):
                if table.contraintes:
                    table.contraintes[-1] += " " + ligne
                    if fk := re.search(r"FOREIGN KEY \(([^)]*)\)", table.contraintes[-1]):
                        cles_etrangeres |= {c.strip() for c in fk.group(1).split(",")}
                continue

            declaration = re.match(r"(\w+)\s+(.+)", ligne)
            if declaration is None:
                continue
            nom, reste = declaration.group(1), declaration.group(2)
            table.colonnes.append(
                Colonne(
                    nom=nom,
                    type_sql=nettoyer_type(reste),
                    obligatoire="NOT NULL" in reste.upper()
                    or "GENERATED ALWAYS AS IDENTITY" in reste.upper(),
                )
            )

        for colonne in table.colonnes:
            marques = []
            if colonne.nom in cles_primaires:
                marques.append("PK")
            if colonne.nom in cles_etrangeres:
                marques.append("FK")
            colonne.cle = ", ".join(marques)

        tables.append(table)

    return tables


def nettoyer_type(reste_de_ligne: str) -> str:
    """
    Isole le type SQL d'une déclaration de colonne.

    Compétence visée : C4 (épreuve E1)
    """
    type_sql = re.sub(r"\s+NOT NULL.*$", "", reste_de_ligne, flags=re.IGNORECASE)
    type_sql = re.sub(
        r"\s+GENERATED ALWAYS AS IDENTITY.*$", " (identité)", type_sql, flags=re.IGNORECASE
    )
    return type_sql.strip()


def composer_markdown(tables: list[Table]) -> str:
    """
    Met en forme le dictionnaire en Markdown accessible.

    Compétence visée : C4 (épreuve E1)

    Choix : titres hiérarchisés et tableaux à en-têtes explicites. Motivation :
    l'accessibilité est un critère transversal des grilles, y compris sur la
    documentation. Un tableau sans en-tête n'est pas restituable par un lecteur
    d'écran.
    """
    lignes = [
        "# Dictionnaire de données — base `eduai_data`",
        "",
        "**Compétence visée :** C4 (épreuve E1)",
        "**Engendré par :** `data_pipeline/load/generer_dictionnaire.py`",
        "**Source :** les scripts de `data_pipeline/load/sql/`, à partir "
        "desquels le conteneur PostgreSQL construit la base.",
        "",
        "> Ce document est engendré. Ne pas le modifier à la main : toute "
        "correction se fait dans les scripts SQL, puis on relance le "
        "générateur. C'est ce qui garantit qu'il ne peut pas diverger du "
        "schéma réel.",
        "",
        f"La base compte **{len(tables)} tables**.",
        "",
        "## Vue d'ensemble",
        "",
        "| Table | Colonnes | Rôle |",
        "|---|---|---|",
    ]

    for table in tables:
        resume = table.commentaire.split(".")[0] + "." if table.commentaire else "—"
        lignes.append(f"| `{table.nom}` | {len(table.colonnes)} | {resume} |")

    lignes.append("")

    for table in tables:
        lignes += [
            "---",
            "",
            f"## `{table.nom}`",
            "",
        ]
        if table.commentaire:
            lignes += [table.commentaire, ""]

        lignes += [
            "| Colonne | Type | Clé | Obligatoire | Description |",
            "|---|---|---|---|---|",
        ]
        for colonne in table.colonnes:
            lignes.append(
                f"| `{colonne.nom}` | `{colonne.type_sql}` | {colonne.cle or '—'} | "
                f"{'oui' if colonne.obligatoire else 'non'} | "
                f"{colonne.commentaire or '—'} |"
            )
        lignes.append("")

        if table.contraintes:
            lignes += [f"### Contraintes de `{table.nom}`", ""]
            for contrainte in table.contraintes:
                lignes.append(f"- `{' '.join(contrainte.split())}`")
            lignes.append("")

    return "\n".join(lignes)


# --- 3. Gestion des erreurs et exceptions ---


def charger_schema() -> str:
    """
    Lit le script de schéma, en échouant explicitement s'il est introuvable.

    Compétence visée : C4 (épreuve E1)
    """
    chemin = REPERTOIRE_SQL / "01_schema.sql"
    if not chemin.exists():
        raise FileNotFoundError(
            f"Script de schéma introuvable : {chemin.resolve()}. "
            "Le générateur doit être lancé depuis la racine du projet."
        )
    return chemin.read_text(encoding="utf-8")


# --- 4. Sauvegarde des résultats ---


def ecrire(markdown: str) -> Path:
    """
    Écrit le dictionnaire sur disque.

    Compétence visée : C4 (épreuve E1)
    """
    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_SORTIE.write_text(markdown, encoding="utf-8")
    return FICHIER_SORTIE


# --- 5. Point de lancement ---


def main() -> None:
    """
    Engendre le dictionnaire de données et journalise le bilan.

    Compétence visée : C4 (épreuve E1)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    sql = charger_schema()
    commentaires_tables, commentaires_colonnes = lire_commentaires(sql)
    tables = lire_tables(retirer_commentaires(sql))

    sans_description = 0
    for table in tables:
        table.commentaire = commentaires_tables.get(table.nom, "")
        for colonne in table.colonnes:
            colonne.commentaire = commentaires_colonnes.get(
                f"{table.nom}.{colonne.nom}", ""
            )
            if not colonne.commentaire:
                sans_description += 1

    chemin = ecrire(composer_markdown(tables))

    total_colonnes = sum(len(t.colonnes) for t in tables)
    logger.info(
        "%d tables, %d colonnes, %d contraintes -> %s",
        len(tables),
        total_colonnes,
        sum(len(t.contraintes) for t in tables),
        chemin,
    )
    if sans_description:
        logger.warning(
            "%d colonnes sur %d sans COMMENT ON : le dictionnaire les affiche "
            "avec un tiret.",
            sans_description,
            total_colonnes,
        )


if __name__ == "__main__":
    main()
