"""
Extraction depuis BASE DE DONNÉES — productions d'apprenants de eduai_app.

Compétence visée : C1 (épreuve E1) — automatisation de l'extraction
Compétence visée : C2 (épreuve E1) — requêtes de collecte en SQL
Compétence visée : C4 (épreuve E1) — minimisation des données personnelles

Contraintes de la source :
  - Base applicative `eduai_app`, propriété de l'organisme de formation. Les
    données sont celles d'apprenants adultes identifiés (décisions 004 et 005).
  - Connexion ouverte en LECTURE SEULE : le pipeline ne doit en aucun cas
    écrire dans la base de l'application.
  - Rétention de la source S4 dans `eduai_data` : 90 jours, portée par
    `source.duree_conservation_jours`.

Sortie : data_pipeline/data/raw/s4_base_donnees_eduai_app.jsonl

Choix : la minimisation est appliquée dans la projection SQL, et non après
chargement. Motivation : une donnée qu'on ne collecte pas n'a besoin ni de
durée de conservation, ni de procédure d'effacement, ni de mesure de sécurité.
Charger puis purger laisse une fenêtre pendant laquelle la donnée existe hors
de son cadre d'origine — et une purge oubliée ne se voit pas.

Choix : aucun identifiant pseudonyme n'est émis. Motivation : le paragraphe 5
du document RGPD ne l'autorise que si le lien entre plusieurs soumissions d'un
même apprenant est nécessaire au traitement. Ce lien est nécessaire à la
COLLECTE — il faut rapprocher un échec de la correction du même apprenant —
mais pas au RÉSULTAT : une fois la paire constituée, le document porte une
erreur et sa correction, pas une personne. Le rapprochement se fait donc dans
la jointure SQL, sur une colonne qui n'est jamais projetée.

Conséquence assumée : `eduai_data` ne contenant aucun identifiant de personne
pour S4, une demande d'effacement au titre de l'article 17 n'a pas d'objet sur
cette base — il n'y a rien à y retrouver. L'effacement s'exerce sur `eduai_app`,
qui reste la seule base à connaître les apprenants.
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances et connexions externes ---

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from dotenv import load_dotenv

from .base_extractor import Enregistrement, ExtracteurBase

logger = logging.getLogger(__name__)

#: Répertoire des requêtes SQL. Le référentiel (C2) exige que les requêtes
#: vivent dans des fichiers dédiés et documentés, pas en chaînes inline.
REPERTOIRE_REQUETES = Path(__file__).resolve().parent / "sql"

#: Fenêtre de collecte par défaut, en jours.
#:
#: Alignée sur la durée de conservation de la source S4 dans `eduai_data`.
#: Collecter au-delà produirait des enregistrements que la purge par ancienneté
#: supprimerait à la première exécution suivante : autant ne pas les extraire.
FENETRE_JOURS_PAR_DEFAUT = 90

#: Noms de colonnes qu'une projection de ce pipeline ne doit jamais contenir.
#:
#: Compétence visée : C4 (épreuve E1)
#:
#: Cette liste sert de garde-fou exécuté à chaque requête, et non de simple
#: consigne : une règle qui ne vit que dans la documentation ne survit pas à
#: une modification distraite d'un fichier .sql.
COLONNES_INTERDITES = {
    "user_id", "created_by_id", "owner_id",
    "ip_address", "email", "username", "password",
    "first_name", "last_name", "display_name", "avatar",
}

#: Fragments interdits en sous-chaîne, pour attraper les variantes non listées
#: (`author_email`, `student_username`, `submitter_ip`…).
FRAGMENTS_INTERDITS = ("email", "password", "ip_address", "username")


class ExtracteurBaseDonneesEduaiApp(ExtracteurBase):
    """
    Extrait les productions d'apprenants de eduai_app vers le corpus.

    Compétence visée : C1 (épreuve E1) — quatrième type de source exigé
    Compétence visée : C2 (épreuve E1) — requêtes SQL documentées

    Choix : deux requêtes distinctes plutôt qu'une union. Motivation : les deux
    gisements produisent des documents de nature différente — du code corrigé
    d'un côté, une méprise conceptuelle de l'autre. Les fondre en une seule
    requête imposerait des colonnes nulles de part et d'autre et rendrait
    illisibles les choix de jointure, que le référentiel demande justement de
    documenter séparément.

    Choix : connexion en lecture seule. Motivation : `eduai_app` porte les
    comptes des apprenants. Le pipeline n'a aucune raison d'y écrire, et une
    connexion en lecture seule transforme cette intention en garantie tenue par
    le moteur plutôt qu'en promesse tenue par le code.
    """

    nom = "s4_base_donnees_eduai_app"
    type_source = "base_donnees"
    licence = "Production des apprenants — usage interne à l'organisme de formation"

    def __init__(
        self,
        repertoire_sortie: Path | None = None,
        fenetre_jours: int = FENETRE_JOURS_PAR_DEFAUT,
        base: str | None = None,
        hote: str | None = None,
        port: str | None = None,
        utilisateur: str | None = None,
    ) -> None:
        super().__init__(repertoire_sortie)
        self.fenetre_jours = fenetre_jours
        self.base = base
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur

        self.connexion: psycopg.Connection | None = None

        #: Décompte par requête, versé dans les journaux en fin d'extraction.
        self.compteurs: dict[str, int] = {}

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Ouvre la connexion en lecture seule à eduai_app.

        Compétence visée : C1 (épreuve E1)

        Choix : les paramètres de connexion viennent de l'environnement, comme
        pour Django, et le mot de passe n'a aucune valeur de repli. Motivation :
        une valeur par défaut dans le code reproduirait le problème de la clé
        secrète versionnée, en le rendant seulement moins visible.
        """
        load_dotenv(Path.cwd() / ".env")

        base = self.base or os.environ.get("DJANGO_DB_NAME", "eduai_app")
        hote = self.hote or os.environ.get("POSTGRES_HOST", "127.0.0.1")
        port = self.port or os.environ.get("POSTGRES_PORT", "5433")
        utilisateur = self.utilisateur or os.environ.get("POSTGRES_USER", "eduai")
        mot_de_passe = os.environ.get("POSTGRES_PASSWORD")

        if not mot_de_passe:
            raise RuntimeError(
                "POSTGRES_PASSWORD est absente de l'environnement. "
                "La renseigner dans le fichier .env à la racine du projet "
                "(voir .env.example)."
            )

        try:
            self.connexion = psycopg.connect(
                dbname=base, user=utilisateur, password=mot_de_passe,
                host=hote, port=port, connect_timeout=10,
            )
        except psycopg.OperationalError as exception:
            # Erreur différenciée : une base injoignable n'est pas une base
            # vide. La première est une panne, la seconde un état normal.
            raise RuntimeError(
                f"Connexion à {base} sur {hote}:{port} impossible : {exception}. "
                "Vérifier que le conteneur PostgreSQL tourne "
                "(docker compose up -d)."
            ) from exception

        # Lecture seule : le moteur refusera toute écriture, y compris une
        # écriture accidentelle introduite par une modification ultérieure.
        self.connexion.read_only = True

        logger.info(
            "[%s] Connecté à %s sur %s:%s en lecture seule — fenêtre de %d jours",
            self.nom, base, hote, port, self.fenetre_jours,
        )

    # --- 2. Règles logiques de traitement ---

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Exécute les deux requêtes et produit les documents correspondants.

        Compétence visée : C1 (épreuve E1) — règles logiques de traitement

        Choix : une base vide est un succès, pas un échec. Motivation : c'est
        la différence entre cette source et S1. Une API qui ne renvoie rien
        signale une panne, une clé expirée ou un quota atteint. Une base
        applicative qui ne renvoie rien signale simplement qu'aucun apprenant
        n'a encore soumis d'exercice — état normal d'une base fraîchement
        créée. Transformer cet état en erreur ferait échouer le pipeline
        complet pour une raison qui n'en est pas une.
        """
        yield from self._extraire_soumissions_corrigees()
        yield from self._extraire_erreurs_conceptuelles()

        total = sum(self.compteurs.values())
        if total == 0:
            logger.info(
                "[%s] Aucune production d'apprenant sur les %d derniers jours. "
                "Sur une base applicative récemment créée, c'est l'état attendu "
                "et non une anomalie : l'extraction est un succès à zéro "
                "enregistrement.",
                self.nom, self.fenetre_jours,
            )
        else:
            logger.info(
                "[%s] Répartition : %s",
                self.nom,
                ", ".join(f"{cle} = {valeur}" for cle, valeur in self.compteurs.items()),
            )

    def _extraire_soumissions_corrigees(self) -> Iterator[Enregistrement]:
        """
        Produit les documents « code en échec puis code corrigé ».

        Compétence visée : C2 (épreuve E1) — jointure latérale
        Compétence visée : C4 (épreuve E1)

        Choix : concaténer l'énoncé, le code fautif, le message d'erreur et le
        code corrigé dans un seul document. Motivation : séparés, ces éléments
        produisent des fragments que le RAG retrouverait isolément, sans jamais
        pouvoir présenter la correction à côté de l'erreur.
        """
        lignes = self._executer("s4_soumissions_corrigees.sql")
        self.compteurs["soumissions_corrigees"] = len(lignes)

        for ligne in lignes:
            titre = (ligne["titre_exercice"] or "").strip()
            code_fautif = (ligne["code_en_echec"] or "").strip()
            code_corrige = (ligne["code_corrige"] or "").strip()

            if not titre or not code_fautif or not code_corrige:
                continue

            message = (ligne["message_erreur"] or "").strip() or "(aucun message)"
            enonce = (ligne["enonce"] or "").strip()

            contenu = (
                f"Exercice : {titre}\n"
                f"Thème : {ligne['theme']} — difficulté : {ligne['difficulte']}\n\n"
                f"Énoncé :\n{enonce}\n\n"
                f"Code soumis, en échec ({ligne['statut_echec']}) :\n"
                f"```python\n{code_fautif}\n```\n\n"
                f"Erreur produite :\n{message}\n\n"
                f"Code corrigé, accepté ensuite :\n"
                f"```python\n{code_corrige}\n```"
            )

            yield Enregistrement(
                identifiant=f"app_soumission_{ligne['id_echec']}_{ligne['id_reussite']}",
                titre=f"Correction — {titre}",
                contenu=contenu,
                source_nom="EduAI Tutor — soumissions d'exercices",
                source_type=self.type_source,
                source_url=None,
                licence=self.licence,
                langue="fr",
                metadonnees={
                    "gisement": "soumissions_corrigees",
                    "theme": ligne["theme"],
                    "difficulte": ligne["difficulte"],
                    "statut_echec": ligne["statut_echec"],
                    "minutes_jusqu_correction": ligne["minutes_jusqu_correction"],
                    "tentatives_exercice": ligne["tentatives_exercice"],
                    "reussites_exercice": ligne["reussites_exercice"],
                    "date_echec": self._iso(ligne["date_echec"]),
                    # Aucun identifiant d'apprenant : la jointure qui a produit
                    # cette paire ne laisse pas de trace dans le résultat.
                },
            )

    def _extraire_erreurs_conceptuelles(self) -> Iterator[Enregistrement]:
        """
        Produit les documents « méprise conceptuelle et sa correction ».

        Compétence visée : C2 (épreuve E1)
        Compétence visée : C4 (épreuve E1)
        """
        lignes = self._executer("s4_erreurs_conceptuelles.sql")
        self.compteurs["erreurs_conceptuelles"] = len(lignes)

        for ligne in lignes:
            question = (ligne["question"] or "").strip()
            correcte = (ligne["reponse_correcte"] or "").strip()

            if not question or not correcte:
                continue

            donnee = (ligne["reponse_donnee"] or "").strip() or "(aucune réponse)"

            contenu = (
                f"Thème : {ligne['theme']}\n"
                f"Type de méprise : {ligne['type_erreur']}\n\n"
                f"Question :\n{question}\n\n"
                f"Réponse donnée par l'apprenant :\n{donnee}\n\n"
                f"Réponse correcte :\n{correcte}"
            )

            yield Enregistrement(
                identifiant=f"app_erreur_{ligne['id_erreur']}",
                titre=f"Méprise — {ligne['theme']} ({ligne['type_erreur']})",
                contenu=contenu,
                source_nom="EduAI Tutor — erreurs conceptuelles relevées",
                source_type=self.type_source,
                source_url=None,
                licence=self.licence,
                langue="fr",
                metadonnees={
                    "gisement": "erreurs_conceptuelles",
                    "theme": ligne["theme"],
                    "type_erreur": ligne["type_erreur"],
                    "revue": ligne["revue"],
                    "date_erreur": self._iso(ligne["date_erreur"]),
                },
            )

    def _executer(self, nom_fichier: str) -> list[dict[str, Any]]:
        """
        Exécute une requête du répertoire SQL et contrôle sa projection.

        Compétence visée : C2 (épreuve E1)
        Compétence visée : C4 (épreuve E1)

        Choix : contrôler les colonnes retournées avant de lire la moindre
        ligne. Motivation : le respect de la minimisation repose sur ce que la
        requête projette. Le vérifier à l'exécution, et non seulement à la
        relecture, fait de la règle une garantie : ajouter `user_id` à un
        fichier .sql interrompt le traitement au lieu de remplir discrètement
        le corpus d'identifiants.
        """
        requete = self._lire_requete(nom_fichier)

        with self.connexion.cursor() as curseur:
            curseur.execute(requete, {"fenetre_jours": self.fenetre_jours})
            colonnes = [description.name for description in curseur.description]
            self._verifier_projection(nom_fichier, colonnes)
            lignes = [dict(zip(colonnes, valeurs)) for valeurs in curseur.fetchall()]

        logger.info("[%s] %s → %d lignes", self.nom, nom_fichier, len(lignes))
        return lignes

    @staticmethod
    def _verifier_projection(nom_fichier: str, colonnes: list[str]) -> None:
        """
        Refuse toute projection contenant une colonne à caractère personnel.

        Compétence visée : C4 (épreuve E1) — minimisation

        Choix : interrompre plutôt qu'avertir. Motivation : un avertissement
        dans un journal se perd ; une extraction qui s'arrête se remarque. Le
        pendant de ce garde-fou existe en S5, où la lecture de Users.xml est
        refusée par le code et pas seulement déconseillée par la documentation.
        """
        fautives = sorted(
            colonne for colonne in colonnes
            if colonne.lower() in COLONNES_INTERDITES
            or any(fragment in colonne.lower() for fragment in FRAGMENTS_INTERDITS)
        )
        if fautives:
            raise ValueError(
                f"{nom_fichier} projette une ou plusieurs colonnes à caractère "
                f"personnel : {', '.join(fautives)}. La minimisation exigée par "
                "l'article 5.1.c impose de les retirer de la projection, et non "
                "de les purger après chargement. "
                "Voir docs/rgpd_eduai_data.md §5."
            )

    def _lire_requete(self, nom_fichier: str) -> str:
        """
        Charge une requête SQL depuis son fichier dédié.

        Compétence visée : C2 (épreuve E1)

        Choix : lire la requête depuis un fichier plutôt que l'écrire en chaîne
        dans le code. Motivation : le référentiel demande des requêtes
        documentées, lisibles et exécutables indépendamment du programme. Un
        fichier `.sql` s'ouvre dans un client SQL et se rejoue tel quel.
        """
        chemin = REPERTOIRE_REQUETES / nom_fichier
        if not chemin.is_file():
            raise FileNotFoundError(f"Requête SQL introuvable : {chemin}")
        return chemin.read_text(encoding="utf-8")

    @staticmethod
    def _iso(valeur: Any) -> str | None:
        """Normalise un horodatage en ISO 8601, format retenu pour tout le corpus."""
        if valeur is None:
            return None
        if isinstance(valeur, datetime):
            return valeur.astimezone(timezone.utc).isoformat()
        return str(valeur)

    # --- 3. Gestion des erreurs : politique héritée de ExtracteurBase ---
    # --- 4. Sauvegarde : héritée de ExtracteurBase ---

    def nettoyer(self) -> None:
        """
        Ferme la connexion à la base.

        Compétence visée : C1 (épreuve E1)

        Choix : fermeture explicite dans `nettoyer`, appelée par le socle dans
        un bloc `finally`. Motivation : une connexion laissée ouverte occupe un
        emplacement du pool PostgreSQL, dont le nombre est borné.
        """
        if self.connexion is not None:
            self.connexion.close()
            self.connexion = None
            logger.info("[%s] Connexion à eduai_app fermée.", self.nom)


# --- 5. Point de lancement ---

def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Décrit les paramètres de ligne de commande.

    Compétence visée : C1 (épreuve E1) — point de lancement
    """
    analyseur = argparse.ArgumentParser(
        description=(
            "Extraction des productions d'apprenants depuis la base "
            "applicative eduai_app vers le corpus eduai_data."
        ),
    )
    analyseur.add_argument(
        "--fenetre-jours", type=int, default=FENETRE_JOURS_PAR_DEFAUT,
        help=(
            "Ancienneté maximale des productions collectées, en jours "
            f"(défaut : {FENETRE_JOURS_PAR_DEFAUT}, aligné sur la durée de "
            "conservation de la source S4)."
        ),
    )
    analyseur.add_argument("--base", default=None, help="Nom de la base (défaut : DJANGO_DB_NAME).")
    analyseur.add_argument("--hote", default=None, help="Hôte PostgreSQL (défaut : POSTGRES_HOST).")
    analyseur.add_argument("--port", default=None, help="Port PostgreSQL (défaut : POSTGRES_PORT).")
    analyseur.add_argument(
        "--utilisateur", default=None, help="Rôle PostgreSQL (défaut : POSTGRES_USER).",
    )
    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement de l'extraction depuis la base applicative.

    Compétence visée : C1 (épreuve E1)

    Choix : journalisation par le module `logging` et non par `print`.
    Motivation : le référentiel exige une trace du début, de la fin, de la
    volumétrie et des erreurs, avec des niveaux distincts.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    arguments = analyser_arguments(argv)

    extracteur = ExtracteurBaseDonneesEduaiApp(
        fenetre_jours=arguments.fenetre_jours,
        base=arguments.base,
        hote=arguments.hote,
        port=arguments.port,
        utilisateur=arguments.utilisateur,
    )

    try:
        bilan = extracteur.executer()
    except FileNotFoundError as exception:
        logger.error("Requête manquante : %s", exception)
        return 2
    except ValueError as exception:
        # Levée par le garde-fou de projection : une colonne personnelle a été
        # ajoutée à un fichier .sql. Code de sortie distinct d'une panne.
        logger.error("Projection refusée : %s", exception)
        return 3
    except RuntimeError as exception:
        logger.error("Prérequis manquant : %s", exception)
        return 2
    except Exception as exception:  # noqa: BLE001 — journalisé puis remonté en code de sortie
        logger.exception("Extraction interrompue : %s", exception)
        return 1

    logger.info(
        "Bilan — %d documents en %.2f s (%d erreurs)",
        bilan["enregistrements"], bilan["duree_secondes"], bilan["erreurs"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
