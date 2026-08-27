"""
Extraction depuis SYSTÈME BIG DATA — dump Stack Exchange traité par Apache Spark.

Compétence visée : C1 (épreuve E1) — automatisation de l'extraction
Compétence visée : C2 (épreuve E1) — requêtes de collecte en Spark SQL
Compétence visée : C4 (épreuve E1) — minimisation des données personnelles

Contraintes de la source :
  - Licence du contenu : CC BY-SA (3.0 ou 4.0 selon la date du post, l'attribut
    ContentLicense de chaque ligne fait foi). L'attribution est assurée par
    l'URL du post, où Stack Exchange crédite lui-même son auteur.
  - Les dumps sont publiés par Stack Exchange sur archive.org. Aucun accès
    réseau n'est effectué par ce script : il lit un dump déjà téléchargé.
  - Le fichier Users.xml du dump n'est jamais ouvert (voir `_refuser_users_xml`).

Sortie : data_pipeline/data/raw/s5_bigdata_stackexchange.jsonl
         plus un rapport de métriques .metriques.json à côté.

Choix : Spark plutôt que pandas ou un analyseur XML séquentiel. Motivation :
le même code doit traiter le dump Data Science (123 Mio, 78 926 posts) et celui
de Stack Overflow (environ 22 Gio), qui ne tient pas en mémoire sur la machine
de développement. C'est la comparaison chiffrée des deux exécutions, produite
par le rapport de métriques, qui justifie le recours à un moteur distribué —
et non l'affirmation qu'un tel moteur serait nécessaire.

Choix : le chemin du dump est un paramètre de ligne de commande. Motivation :
rejouer strictement le même traitement sur les deux volumes est la condition
pour que la comparaison des durées ait un sens. Un chemin codé en dur imposerait
de modifier le script entre les deux mesures, donc de comparer deux codes.
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances et connexions externes ---

import argparse
import html
import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .base_extractor import Enregistrement, ExtracteurBase

logger = logging.getLogger(__name__)

#: Dump utilisé par défaut. Hors du dépôt : les dumps pèsent de 123 Mio à
#: 22 Gio et n'ont rien à faire dans Git.
DUMP_PAR_DEFAUT = Path("/media/apprenant/Stockage/eduai-data/dumps/datascience")

#: Racine des tables Parquet produites. Hors du dépôt, même raison.
PARQUET_PAR_DEFAUT = Path("/media/apprenant/Stockage/eduai-data/parquet")

#: Répertoire des requêtes Spark SQL. Le référentiel (C2) exige que les
#: requêtes vivent dans des fichiers dédiés, pas en chaînes de caractères
#: inline : elles doivent être lisibles et exécutables indépendamment du code.
REPERTOIRE_REQUETES = Path(__file__).resolve().parent / "sql"

#: Fichiers du dump que ce script s'interdit d'ouvrir.
#:
#: Users.xml ne contient que des données à caractère personnel : nom
#: d'affichage, site web, localisation déclarée, biographie, date de dernier
#: accès. Aucune n'a d'utilité pédagogique pour le corpus. Le principe de
#: minimisation (art. 5.1.c) impose donc de ne pas les collecter du tout,
#: plutôt que de les charger puis de les purger.
FICHIERS_INTERDITS = {"Users.xml"}

#: Correspondance dossier de dump -> domaine, pour reconstruire les URL
#: d'attribution. Une entrée par site traité ; le repli couvre les autres.
DOMAINES_STACK_EXCHANGE = {
    "datascience": "datascience.stackexchange.com",
    "stackoverflow": "stackoverflow.com",
    "stats": "stats.stackexchange.com",
}


class ExtracteurBigDataStackExchange(ExtracteurBase):
    """
    Convertit un dump XML Stack Exchange en Parquet, puis l'interroge en Spark SQL.

    Compétence visée : C1 (épreuve E1) — cinquième type de source exigé
    Compétence visée : C2 (épreuve E1) — second langage de requête

    Choix : deux phases distinctes et chronométrées séparément — conversion
    XML vers Parquet, puis sélection en Spark SQL. Motivation : ce sont deux
    coûts de nature différente. La conversion est un balayage complet, payé une
    fois ; la sélection profite du partitionnement et se paie à chaque requête.
    Les confondre en une seule durée rendrait la comparaison entre les deux
    dumps inexploitable à l'oral.

    Choix : les requêtes sont lues depuis des fichiers `.spark.sql` et exécutées
    par `spark.sql`, sans passer par l'API DataFrame pour la logique de
    sélection. Motivation : le référentiel exige deux langages de requête
    distincts en C2. Écrire la même sélection en API DataFrame produirait le
    même résultat sans démontrer le second langage.
    """

    nom = "s5_bigdata_stackexchange"
    type_source = "big_data"
    licence = "CC BY-SA 3.0 / 4.0 (attribut ContentLicense par post)"
    code_source = "s5"

    def __init__(
        self,
        # Même défaut que l'option --dump de la ligne de commande. Sans lui,
        # l'orchestrateur — qui instancie les cinq extracteurs de façon
        # uniforme, sans argument — ne pouvait pas construire celui-ci.
        chemin_dump: Path = DUMP_PAR_DEFAUT,
        chemin_parquet: Path | None = None,
        repertoire_sortie: Path | None = None,
        annee_min: int = 2015,
        score_min: int = 2,
        taille_min: int = 200,
        limite: int | None = None,
        forcer_conversion: bool = False,
        memoire_pilote: str = "4g",
    ) -> None:
        super().__init__(repertoire_sortie)
        self.chemin_dump = Path(chemin_dump)
        self.chemin_parquet = Path(chemin_parquet or PARQUET_PAR_DEFAUT / self.chemin_dump.name)
        self.annee_min = annee_min
        self.score_min = score_min
        self.taille_min = taille_min
        self.limite = limite
        self.forcer_conversion = forcer_conversion
        self.memoire_pilote = memoire_pilote

        self.spark = None
        self.domaine = self._resoudre_domaine(self.chemin_dump)

        #: Mesures alimentant la justification chiffrée du recours au big data.
        #:
        #: `limite` y figure même lorsqu'elle vaut None : un rapport doit dire
        #: si la sélection a été plafonnée, sans quoi rien ne distingue une
        #: extraction complète d'un essai tronqué. Les paramètres de sélection
        #: y figurent pour la même raison — comparer deux mesures suppose de
        #: pouvoir vérifier qu'elles ont été prises avec les mêmes filtres.
        self.metriques: dict[str, Any] = {
            "dump": str(self.chemin_dump),
            "parquet": str(self.chemin_parquet),
            "limite": limite,
            "selection": {
                "annee_min": annee_min,
                "score_min": score_min,
                "taille_min": taille_min,
            },
        }

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Vérifie le dump, refuse les fichiers interdits et ouvre la session Spark.

        Compétence visée : C1 (épreuve E1)

        Choix : échouer avant tout traitement si un prérequis manque, plutôt
        que de laisser Spark produire une trace de plusieurs centaines de
        lignes sur un chemin inexistant. Une erreur de chemin est l'erreur la
        plus probable ici, puisque le chemin est un paramètre.
        """
        if not self.chemin_dump.is_dir():
            raise FileNotFoundError(
                f"Dump introuvable : {self.chemin_dump}. "
                "Indiquer le dossier décompressé du dump avec --dump."
            )

        self._refuser_users_xml()

        posts = self.chemin_dump / "Posts.xml"
        if not posts.is_file():
            raise FileNotFoundError(
                f"Posts.xml absent de {self.chemin_dump}. "
                "Ce script ne traite que ce fichier du dump."
            )

        taille_mio = posts.stat().st_size / 1024 / 1024
        self.metriques["taille_posts_xml_mio"] = round(taille_mio, 1)
        logger.info(
            "[%s] Dump : %s — Posts.xml de %.1f Mio, site %s",
            self.nom, self.chemin_dump, taille_mio, self.domaine,
        )

        self.spark = self._ouvrir_session_spark()

    def _refuser_users_xml(self) -> None:
        """
        Interdit explicitement la lecture des fichiers porteurs de données personnelles.

        Compétence visée : C4 (épreuve E1) — minimisation

        Choix : un garde-fou dans le code, et pas seulement une consigne dans la
        documentation. Motivation : une règle qui ne vit que dans un document
        n'est pas vérifiable par le jury et ne survit pas à une modification
        distraite. Ici, pointer `--dump` sur un fichier interdit arrête le
        traitement.

        Le fichier Users.xml n'est pas supprimé du dump : le dump reste
        l'original téléchargé, non modifié. C'est sa lecture qui est refusée.
        """
        if self.chemin_dump.name in FICHIERS_INTERDITS:
            raise ValueError(
                f"{self.chemin_dump.name} contient des données à caractère "
                "personnel (noms d'affichage, sites web, localisations) et ce "
                "script s'interdit de le lire. Voir docs/rgpd_eduai_data.md §5."
            )

        presents = [f for f in FICHIERS_INTERDITS if (self.chemin_dump / f).is_file()]
        if presents:
            logger.info(
                "[%s] Présents dans le dump mais NON lus (minimisation C4) : %s",
                self.nom, ", ".join(sorted(presents)),
            )
        self.metriques["fichiers_non_lus"] = sorted(presents)

    def _ouvrir_session_spark(self):
        """
        Crée la session Spark locale.

        Compétence visée : C1 (épreuve E1)

        Choix : exécution en mode local avec tous les cœurs (`local[*]`) plutôt
        qu'un cluster. Motivation : le projet tourne sur une seule machine. Le
        mode local conserve le modèle de programmation distribué — partitions,
        exécution paresseuse, plan optimisé — sans exiger une infrastructure
        que le rendu du 4 septembre ne permet pas de monter. Le même code
        s'exécuterait sur un cluster en changeant la seule ligne `master`.

        Choix : l'exécution adaptative est laissée active (valeur par défaut
        depuis Spark 3.2). Motivation : elle recoalesce les partitions après
        remaniement en fonction des volumes réels. Sur le dump Data Science,
        les 200 partitions de remaniement par défaut produiraient des fichiers
        de quelques kilooctets ; sur celui de Stack Overflow, elles sont trop
        peu nombreuses. Un réglage fixe ne peut pas convenir aux deux.
        """
        from pyspark.sql import SparkSession

        session = (
            SparkSession.builder
            .appName(f"eduai-{self.nom}")
            .master("local[*]")
            .config("spark.driver.memory", self.memoire_pilote)
            # Horodatages du dump en UTC : les dates de création servent au
            # partitionnement, un décalage de fuseau déplacerait des posts de
            # partition selon la machine qui exécute le traitement.
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.parquet.compression.codec", "snappy")
            # Les journaux d'événements ne servent qu'à l'interface Spark, qui
            # n'est pas exploitée ici : les écrire coûterait des entrées-sorties
            # sans contrepartie.
            .config("spark.eventLog.enabled", "false")
            .getOrCreate()
        )
        session.sparkContext.setLogLevel("WARN")

        self.metriques["spark_version"] = session.version
        self.metriques["parallelisme"] = session.sparkContext.defaultParallelism
        logger.info(
            "[%s] Spark %s démarré, parallélisme %d, mémoire pilote %s",
            self.nom, session.version,
            session.sparkContext.defaultParallelism, self.memoire_pilote,
        )
        return session

    # --- 2. Règles logiques de traitement ---

    def convertir_en_parquet(self) -> float:
        """
        Convertit Posts.xml en table Parquet partitionnée par année.

        Compétence visée : C2 (épreuve E1) — requête de conversion en Spark SQL
        Compétence visée : C4 (épreuve E1) — minimisation à la projection

        Choix : Parquet partitionné plutôt qu'une lecture directe du XML à
        chaque requête. Motivation : le XML impose de relire et de réanalyser
        l'intégralité du fichier pour toute question, si petite soit-elle.
        Parquet est colonne et compressé : une requête ne lit que les colonnes
        projetées, et le partitionnement par année lui évite les répertoires
        exclus par le filtre. C'est ce qui rend le traitement du dump de 22 Gio
        praticable après une conversion payée une seule fois.

        Choix : idempotence par présence de la table. Motivation : relancer le
        script ne doit pas reconvertir 22 Gio. `--forcer-conversion` rend la
        reconversion explicite.

        Returns:
            Durée de la conversion en secondes, ou 0.0 si elle a été sautée.
        """
        marqueur = self.chemin_parquet / "_SUCCESS"

        if marqueur.is_file() and not self.forcer_conversion:
            logger.info(
                "[%s] Table Parquet déjà présente dans %s — conversion sautée "
                "(--forcer-conversion pour la refaire).",
                self.nom, self.chemin_parquet,
            )
            self.metriques["conversion_sautee"] = True
            return 0.0

        if self.chemin_parquet.exists():
            # Écriture en mode « overwrite » plus bas, mais on supprime d'abord :
            # un partitionnement qui change laisserait sinon des répertoires
            # d'années orphelins que les requêtes liraient encore.
            logger.info("[%s] Suppression de la table précédente.", self.nom)
            shutil.rmtree(self.chemin_parquet)

        debut = datetime.now(timezone.utc)

        # Lecture ligne à ligne : les dumps Stack Exchange écrivent un élément
        # <row/> par ligne, ce qui rend le fichier découpable en blocs
        # indépendants, donc lisible en parallèle. Un analyseur XML global
        # sérialiserait la lecture sur un flux unique.
        lignes = self.spark.read.text(str(self.chemin_dump / "Posts.xml"))
        lignes = lignes.withColumnRenamed("value", "ligne")
        lignes.createOrReplaceTempView("posts_brut")

        requete = self._lire_requete("s5_conversion_parquet.spark.sql")
        posts = self.spark.sql(requete)

        (
            posts.write
            .mode("overwrite")
            .partitionBy("annee")
            .parquet(str(self.chemin_parquet))
        )

        duree = (datetime.now(timezone.utc) - debut).total_seconds()
        self.metriques["conversion_sautee"] = False
        self.metriques["duree_conversion_secondes"] = round(duree, 2)
        logger.info(
            "[%s] Conversion terminée en %.2f s vers %s",
            self.nom, duree, self.chemin_parquet,
        )
        return duree

    def calculer_metriques(self) -> list[dict[str, Any]]:
        """
        Exécute la requête de volumétrie sur la table Parquet.

        Compétence visée : C2 (épreuve E1)
        Compétence visée : C20 (épreuve E5) — mesure d'un traitement

        Choix : mesurer avant de filtrer. Motivation : c'est l'écart entre le
        volume traité et le volume retenu qui donne son sens à la comparaison
        entre les deux dumps. Ne compter que la sortie masquerait le travail
        réellement effectué.
        """
        debut = datetime.now(timezone.utc)
        requete = self._lire_requete("s5_metriques_volumetrie.spark.sql")
        lignes = [ligne.asDict() for ligne in self.spark.sql(requete).collect()]
        duree = (datetime.now(timezone.utc) - debut).total_seconds()

        total = sum(ligne["posts_total"] for ligne in lignes)
        self.metriques["duree_metriques_secondes"] = round(duree, 2)
        self.metriques["posts_dans_parquet"] = total
        self.metriques["partitions_annee"] = len(lignes)
        self.metriques["volumetrie_par_annee"] = lignes

        logger.info(
            "[%s] Volumétrie : %d posts répartis sur %d partitions annuelles "
            "(%.2f s)",
            self.nom, total, len(lignes), duree,
        )
        return lignes

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Exécute la requête de sélection et produit les enregistrements.

        Compétence visée : C1 (épreuve E1) — règles logiques de traitement
        Compétence visée : C2 (épreuve E1) — jointure en Spark SQL

        Choix : `toLocalIterator` plutôt que `collect`. Motivation : `collect`
        rapatrie tout le résultat dans la mémoire du pilote. Sur le dump Stack
        Overflow, la sélection peut porter sur plusieurs centaines de milliers
        de documents : le pilote tomberait. `toLocalIterator` ramène une
        partition à la fois, ce qui préserve l'écriture au fil de l'eau voulue
        par le socle commun.
        """
        self.convertir_en_parquet()

        table = self.spark.read.parquet(str(self.chemin_parquet))
        table.createOrReplaceTempView("posts")

        self.calculer_metriques()

        debut = datetime.now(timezone.utc)
        requete = self._lire_requete("s5_selection_documents.spark.sql")

        # Paramètres passés à Spark, pas interpolés dans la chaîne : la requête
        # reste un fichier exécutable tel quel et aucune valeur ne peut modifier
        # la structure de la requête.
        resultat = self.spark.sql(
            requete,
            args={
                "annee_min": self.annee_min,
                "score_min": self.score_min,
                "taille_min": self.taille_min,
            },
        )

        if self.limite is not None:
            # Plafond d'exploitation, pas critère de collecte : il sert aux
            # essais rapides sur le gros dump. Il reste hors du fichier .sql
            # pour que la requête versionnée décrive la collecte réelle.
            resultat = resultat.limit(self.limite)

        retenus = 0
        for ligne in resultat.toLocalIterator():
            enregistrement = self._construire_enregistrement(ligne.asDict())
            if enregistrement is not None:
                retenus += 1
                yield enregistrement

        duree = (datetime.now(timezone.utc) - debut).total_seconds()
        self.metriques["duree_selection_secondes"] = round(duree, 2)
        self.metriques["documents_retenus"] = retenus
        logger.info(
            "[%s] Sélection : %d documents retenus en %.2f s",
            self.nom, retenus, duree,
        )

    def _construire_enregistrement(self, ligne: dict[str, Any]) -> Enregistrement | None:
        """
        Assemble une question et sa réponse acceptée en un document du corpus.

        Compétence visée : C1 (épreuve E1)
        Compétence visée : C4 (épreuve E1)

        Choix : concaténer question et réponse, comme le fait S1. Motivation :
        pour un RAG, une question sans sa réponse produit un fragment orphelin
        qui pollue l'index sans jamais constituer une réponse utile.

        Choix : aucun champ d'auteur dans les métadonnées. Motivation : ces
        champs n'ont pas été extraits à la conversion — ils n'existent tout
        simplement pas dans la table lue ici. L'attribution CC BY-SA passe par
        `source_url`.
        """
        corps_question = self._html_vers_texte(ligne.get("corps_question") or "")
        corps_reponse = self._html_vers_texte(ligne.get("corps_reponse") or "")
        titre = html.unescape(ligne.get("titre") or "").strip()

        if not titre or not corps_question or not corps_reponse:
            return None

        contenu = (
            f"Question : {titre}\n\n"
            f"{corps_question}\n\n"
            f"Réponse acceptée :\n{corps_reponse}"
        )

        identifiant_site = self.chemin_dump.name
        date_creation = ligne.get("date_creation")

        return Enregistrement(
            identifiant=f"se_{identifiant_site}_{ligne['id_question']}",
            titre=titre,
            contenu=contenu,
            source_nom=f"Stack Exchange — {self.domaine}",
            source_type=self.type_source,
            source_url=f"https://{self.domaine}/questions/{ligne['id_question']}",
            licence=ligne.get("licence") or self.licence,
            langue="en",
            metadonnees={
                "site": identifiant_site,
                "mots_cles": self._decouper_mots_cles(ligne.get("mots_cles_bruts")),
                "score_question": ligne.get("score_question"),
                "score_reponse": ligne.get("score_reponse"),
                "vues": ligne.get("nombre_vues"),
                "nombre_reponses": ligne.get("nombre_reponses"),
                "annee": ligne.get("annee"),
                "cree_le": date_creation.isoformat() if date_creation else None,
            },
        )

    @staticmethod
    def _decouper_mots_cles(brut: str | None) -> list[str]:
        """
        Normalise les deux formats d'étiquettes rencontrés dans les dumps.

        Compétence visée : C3 (épreuve E1) — homogénéisation des formats

        Choix : traiter les deux formats plutôt que celui du seul dump sous la
        main. Motivation : les dumps récents écrivent « |a|b| », les plus
        anciens « <a><b> ». Le script doit produire le même résultat sur les
        deux dumps, sans quoi la comparaison annoncée à l'oral porterait sur
        deux traitements différents.
        """
        if not brut:
            return []
        normalise = brut.replace("<", "|").replace(">", "|")
        return [mot for mot in normalise.split("|") if mot]

    @staticmethod
    def _html_vers_texte(contenu_html: str) -> str:
        """
        Convertit le HTML d'un post en texte, en préservant les blocs de code.

        Compétence visée : C1 (épreuve E1)

        Choix : une implémentation propre à cet extracteur plutôt qu'une
        fonction partagée avec S1. Motivation : la règle du projet veut que
        chaque type de source garde son fichier et sa logique, pour que la
        couverture des cinq types reste lisible. Les deux sources reçoivent
        d'ailleurs leur HTML par des canaux différents — réponse JSON d'API
        pour S1, attribut XML déjà déséchappé par `xpath_string` ici.

        Choix : mettre les blocs de code de côté avant de normaliser les
        espaces. Motivation : appliquer « suites d'espaces vers un espace » à
        du Python détruit l'indentation, donc la validité du code — et le code
        est l'essentiel de la valeur pédagogique de ces documents.
        """
        if not contenu_html:
            return ""

        blocs_code: list[str] = []

        def mettre_de_cote(correspondance: re.Match[str]) -> str:
            blocs_code.append(html.unescape(correspondance.group(1)))
            return f"\n\x00BLOC{len(blocs_code) - 1}\x00\n"

        texte = re.sub(
            r"<pre><code>(.*?)</code></pre>",
            mettre_de_cote,
            contenu_html,
            flags=re.DOTALL,
        )
        texte = re.sub(r"<[^>]+>", " ", texte)
        texte = html.unescape(texte)
        texte = re.sub(r"[ \t]+", " ", texte)
        texte = re.sub(r"\n{3,}", "\n\n", texte)
        texte = texte.strip()

        for numero, bloc in enumerate(blocs_code):
            code = bloc.strip("\n")
            texte = texte.replace(f"\x00BLOC{numero}\x00", f"```\n{code}\n```")

        return texte

    def _lire_requete(self, nom_fichier: str) -> str:
        """
        Charge une requête Spark SQL depuis son fichier dédié.

        Compétence visée : C2 (épreuve E1)

        Choix : lire la requête depuis un fichier plutôt que l'écrire en chaîne
        dans le code. Motivation : le référentiel demande des requêtes
        documentées et lisibles indépendamment du programme qui les exécute.
        Un fichier `.spark.sql` s'ouvre, se relit et s'exécute tel quel.
        """
        chemin = REPERTOIRE_REQUETES / nom_fichier
        if not chemin.is_file():
            raise FileNotFoundError(f"Requête Spark SQL introuvable : {chemin}")
        return chemin.read_text(encoding="utf-8")

    @staticmethod
    def _resoudre_domaine(chemin_dump: Path) -> str:
        """
        Déduit le domaine du site à partir du nom du dossier de dump.

        Compétence visée : C1 (épreuve E1)

        Le domaine sert à reconstruire l'URL d'attribution exigée par CC BY-SA.
        Repli explicite plutôt que silencieux : un dump inconnu produit une URL
        plausible, et le nom du dossier reste visible dans les métadonnées.
        """
        cle = chemin_dump.name.lower()
        if cle in DOMAINES_STACK_EXCHANGE:
            return DOMAINES_STACK_EXCHANGE[cle]
        logger.warning(
            "Site « %s » inconnu de la table des domaines : URL reconstruite "
            "en %s.stackexchange.com. Compléter DOMAINES_STACK_EXCHANGE si "
            "l'attribution doit être exacte.", cle, cle,
        )
        return f"{cle}.stackexchange.com"

    # --- 3. Gestion des erreurs : politique héritée de ExtracteurBase ---
    # --- 4. Sauvegarde : héritée de ExtracteurBase ---

    def nettoyer(self) -> None:
        """
        Ferme la session Spark.

        Compétence visée : C1 (épreuve E1)

        Choix : arrêt explicite plutôt que de compter sur la fin du processus.
        Motivation : la JVM lancée par Spark ne s'arrête pas toujours avec
        l'interpréteur Python, et une session résiduelle garde ses fichiers
        temporaires et ses ports ouverts.
        """
        if self.spark is not None:
            self.spark.stop()
            self.spark = None
            logger.info("[%s] Session Spark fermée.", self.nom)


# --- 4. Sauvegarde des résultats : rapport de métriques ---

def ecrire_rapport(extracteur: ExtracteurBigDataStackExchange,
                   bilan: dict[str, Any]) -> Path:
    """
    Écrit le rapport chiffré de l'exécution à côté du fichier de sortie.

    Compétence visée : C20 (épreuve E5) — suivi et mesure d'un traitement

    Choix : un fichier de référence par dump, nommé d'après lui. Motivation :
    c'est la comparaison de deux rapports — dump Data Science contre dump Stack
    Overflow — qui constitue la justification chiffrée du recours au big data.
    Un fichier unique écrasé à chaque exécution détruirait ce qu'on compare.

    Choix : une exécution qui saute la conversion n'écrase PAS le rapport de
    référence, elle écrit à côté. Motivation : le cas s'est produit deux fois.
    Relancer l'extraction pour vérifier autre chose remplaçait une mesure
    complète par une mesure où la conversion vaut 0,00 s — chiffre exact mais
    trompeur, et en contradiction avec la mesure de référence citée dans
    `docs/decisions/009`. Un artefact de preuve qui s'écrase à chaque
    exécution n'est pas une preuve.
    """
    rapport = {**bilan, **extracteur.metriques}
    nom_dump = extracteur.chemin_dump.name
    # Concaténation et non `with_suffix` : le nom du dump est lui-même un
    # segment séparé par un point, et `with_suffix` le remplacerait au lieu de
    # s'y ajouter. Le nom du dump doit survivre — c'est lui qui distingue les
    # rapports que la mesure comparative confronte.
    repertoire = extracteur.repertoire_sortie
    reference = repertoire / f"{extracteur.nom}.{nom_dump}.metriques.json"
    reference.parent.mkdir(parents=True, exist_ok=True)

    complete = not extracteur.metriques.get("conversion_sautee", False)

    if complete or not reference.is_file():
        chemin = reference
    else:
        # Exécution partielle alors qu'une référence complète existe déjà :
        # on la préserve et on consigne celle-ci à part.
        chemin = repertoire / f"{extracteur.nom}.{nom_dump}.derniere_execution.json"
        logger.info(
            "Conversion sautée : le rapport de référence %s est préservé.",
            reference.name,
        )

    rapport["mesure_complete"] = complete
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Rapport de métriques écrit dans %s", chemin)
    return chemin


# --- 5. Point de lancement ---

def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Décrit les paramètres de ligne de commande.

    Compétence visée : C1 (épreuve E1) — point de lancement

    Choix : le chemin du dump est un paramètre et non une constante.
    Motivation : le même traitement doit s'exécuter sur le dump Data Science
    (123 Mio) et sur celui de Stack Overflow (environ 22 Gio) pour que la
    comparaison des durées mesure le volume et non deux versions du code.
    """
    analyseur = argparse.ArgumentParser(
        description=(
            "Extraction big data : dump XML Stack Exchange vers Parquet "
            "partitionné, puis sélection en Spark SQL."
        ),
    )
    analyseur.add_argument(
        "--dump", type=Path, default=DUMP_PAR_DEFAUT,
        help=f"Dossier du dump décompressé (défaut : {DUMP_PAR_DEFAUT}).",
    )
    analyseur.add_argument(
        "--parquet", type=Path, default=None,
        help=f"Destination de la table Parquet (défaut : {PARQUET_PAR_DEFAUT}/<nom du dump>).",
    )
    analyseur.add_argument(
        "--sortie", type=Path, default=None,
        help=(
            "Répertoire du fichier JSONL et du bilan. Par défaut, celui du "
            "socle d'extraction. À utiliser pour une mesure comparative : sans "
            "lui, traiter un second dump écrase le corpus produit par le "
            "premier, les deux fichiers portant le même nom."
        ),
    )
    analyseur.add_argument(
        "--annee-min", type=int, default=2015,
        help="Année de création minimale des questions retenues (défaut : 2015).",
    )
    analyseur.add_argument(
        "--score-min", type=int, default=2,
        help="Score minimal des questions retenues (défaut : 2).",
    )
    analyseur.add_argument(
        "--taille-min", type=int, default=200,
        help="Longueur minimale de la réponse acceptée, en caractères (défaut : 200).",
    )
    analyseur.add_argument(
        "--limite", type=int, default=None,
        help="Plafond de documents écrits. Pour les essais sur gros volume.",
    )
    analyseur.add_argument(
        "--forcer-conversion", action="store_true",
        help="Reconvertit le XML même si la table Parquet existe déjà.",
    )
    analyseur.add_argument(
        "--memoire-pilote", default="4g",
        help="Mémoire allouée au pilote Spark (défaut : 4g).",
    )
    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement de l'extraction big data.

    Compétence visée : C1 (épreuve E1)

    Choix : journalisation structurée par le module `logging` et non par
    `print`. Motivation : le référentiel exige une trace du début, de la fin,
    de la volumétrie et des erreurs. `print` n'offre ni niveau, ni horodatage,
    ni redirection vers un fichier.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    arguments = analyser_arguments(argv)

    extracteur = ExtracteurBigDataStackExchange(
        chemin_dump=arguments.dump,
        chemin_parquet=arguments.parquet,
        repertoire_sortie=arguments.sortie,
        annee_min=arguments.annee_min,
        score_min=arguments.score_min,
        taille_min=arguments.taille_min,
        limite=arguments.limite,
        forcer_conversion=arguments.forcer_conversion,
        memoire_pilote=arguments.memoire_pilote,
    )

    try:
        bilan = extracteur.executer()
    except FileNotFoundError as exception:
        logger.error("Prérequis manquant : %s", exception)
        return 2
    except ValueError as exception:
        logger.error("Paramètre refusé : %s", exception)
        return 2
    except Exception as exception:  # noqa: BLE001 — journalisé puis remonté en code de sortie
        logger.exception("Extraction interrompue : %s", exception)
        return 1

    ecrire_rapport(extracteur, bilan)

    duree_conversion = extracteur.metriques.get("duree_conversion_secondes", 0.0)
    duree_selection = extracteur.metriques.get("duree_selection_secondes", 0.0)
    logger.info(
        "Bilan — %d documents, conversion %.2f s, sélection %.2f s, total %.2f s",
        bilan["enregistrements"], duree_conversion, duree_selection,
        bilan["duree_secondes"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
