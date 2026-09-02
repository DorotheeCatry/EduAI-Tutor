"""
Chargement du corpus transformé dans la base eduai_data.

Compétence visée : C4 (épreuve E1) — création et alimentation de la base
Compétence visée : C3 (épreuve E1) — le chargement consomme la sortie de la
                   transformation, jamais les extractions brutes

Entrée : data_pipeline/data/processed/corpus.jsonl
Sortie : la base eduai_data, plus un rapport de chargement à côté du corpus.

Choix : le chargeur lit `processed/` et jamais `raw/`. Motivation : brancher le
chargement sur le brut ferait de la transformation une étape facultative, que
rien n'obligerait à rejouer après modification d'un extracteur. Le corpus
transformé est la seule entrée légitime.

Choix : une seule transaction pour l'ensemble du chargement. Motivation : le
déclencheur `document_partition_totale` est différé — il vérifie au moment de
la validation qu'aucun document n'existe sans sa ligne de spécialisation. Un
découpage en lots ferait passer ce contrôle lot par lot, ce qui reste correct,
mais laisserait la base à moitié chargée en cas d'échec. Six mille huit cents
documents ne justifient pas ce risque : ou tout entre, ou rien n'entre.

Choix : aucun `TRUNCATE` préalable. Motivation : le chargement est idempotent
par `ON CONFLICT`, ce qui suffit à le rejouer. Vider la table avant chaque
chargement détruirait les documents d'une source pendant qu'on recharge une
autre, et rendrait le chargement partiel destructeur.
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances et connexions externes ---

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CORPUS_PAR_DEFAUT = Path("data_pipeline/data/processed/corpus.jsonl")
REPERTOIRE_REQUETES = Path(__file__).resolve().parent / "requetes"

#: Table de spécialisation par type de source.
#:
#: Le nom de la table ne peut pas être un paramètre SQL. Il est donc pris dans
#: cette table fermée, jamais construit depuis une donnée du corpus : c'est ce
#: qui exclut toute injection par le champ `code_type_source`.
TABLES_SIMPLES = {
    "big_data": "document_big_data",
    "base_donnees": "document_base_donnees",
}

#: Catégories de la nomenclature `mot_cle`.
CATEGORIE_ETIQUETTE = "tag_source"
CATEGORIE_MODULE = "module"

#: Répertoire où les extracteurs déposent leur bilan d'exécution.
REPERTOIRE_BILANS_PAR_DEFAUT = Path("data_pipeline/data/raw")

#: Champ de métadonnée décrivant, pour chaque type de source, le chemin par
#: lequel un document a été atteint.
#:
#: Compétence visée : C1 (épreuve E1) — traçabilité de la collecte
#:
#: Choix : un critère propre à chaque type plutôt qu'un libellé générique.
#: Motivation : « par quel chemin ce document est-il arrivé ? » n'a pas la même
#: réponse selon la source — un tag de recherche pour une API, une page pour du
#: scraping, un fichier pour une lecture locale. Un libellé unique ne
#: répondrait à la question pour aucune d'elles.
CRITERE_PAR_TYPE = {
    "api_rest": "tag_recherche",
    "scraping": "page",
    "fichier": "fichier",
    "big_data": "site",
    "base_donnees": "gisement",
}


class Chargeur:
    """
    Verse le corpus transformé dans eduai_data.

    Compétence visée : C4 (épreuve E1)

    Choix : les nomenclatures sont lues depuis la base au démarrage, jamais
    codées en dur. Motivation : `attribution_requise` fait partie de la clé
    étrangère composite vers `licence`. La supposer dans le code créerait deux
    sources de vérité, dont l'une dériverait silencieusement. La lire garantit
    que le chargeur et la base disent la même chose — et fait échouer tôt, avec
    un message clair, quand une nomenclature manque.
    """

    def __init__(
        self,
        chemin_corpus: Path = CORPUS_PAR_DEFAUT,
        repertoire_bilans: Path = REPERTOIRE_BILANS_PAR_DEFAUT,
        base: str | None = None,
        hote: str | None = None,
        port: str | None = None,
        utilisateur: str | None = None,
    ) -> None:
        self.chemin_corpus = Path(chemin_corpus)
        self.repertoire_bilans = Path(repertoire_bilans)
        self.base = base
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur

        self.connexion: psycopg.Connection | None = None
        self.requetes: dict[str, str] = {}

        #: Nomenclatures lues en base : elles font foi, pas le code.
        self.attribution_par_licence: dict[str, bool] = {}
        self.source_par_type: dict[str, str] = {}
        self.sources_connues: set[str] = set()

        #: Bilans d'extraction lus sur disque, indexés par code de source.
        self.bilans: dict[str, dict[str, Any]] = {}

        #: Identifiant de campagne en base, par code de source.
        self.extraction_par_source: dict[str, int] = {}

        self.rapport: dict[str, Any] = {
            "documents_lus": 0,
            "documents_charges": 0,
            "mots_cles_charges": 0,
            "rattachements_charges": 0,
            "par_type_source": {},
            "campagnes_chargees": {},
            "sources_sans_bilan": [],
            "collectes_chargees": 0,
            "documents_retires": [],
            "sources_balayees": [],
            "rejets": [],
        }
        self.horodatage_chargement: datetime | None = None

    # --- 1. Initialisation ---

    def initialiser(self) -> None:
        """
        Ouvre la connexion, charge les requêtes et lit les nomenclatures.

        Compétence visée : C4 (épreuve E1)

        Choix : vérifier les nomenclatures avant d'insérer la moindre ligne.
        Motivation : sans licence `CC-BY-SA-3.0` en base, le chargement
        échouerait au 1 664e document sur une violation de clé étrangère, après
        avoir travaillé pour rien. Le contrôle préalable dit ce qui manque, en
        une phrase, avant de commencer.
        """
        load_dotenv(Path.cwd() / ".env")

        if not self.chemin_corpus.is_file():
            raise FileNotFoundError(
                f"Corpus transformé introuvable : {self.chemin_corpus}. "
                "Lancer la transformation avant le chargement : "
                "uv run python -m data_pipeline.transform.transformer"
            )

        mot_de_passe = os.environ.get("POSTGRES_PASSWORD")
        if not mot_de_passe:
            raise RuntimeError(
                "POSTGRES_PASSWORD est absente de l'environnement. "
                "La renseigner dans le fichier .env (voir .env.example)."
            )

        base = self.base or os.environ.get("POSTGRES_DB", "eduai_data")
        hote = self.hote or os.environ.get("POSTGRES_HOST", "127.0.0.1")
        port = self.port or os.environ.get("POSTGRES_PORT", "5433")
        utilisateur = self.utilisateur or os.environ.get("POSTGRES_USER", "eduai")

        try:
            self.connexion = psycopg.connect(
                dbname=base, user=utilisateur, password=mot_de_passe,
                host=hote, port=port, connect_timeout=10,
            )
        except psycopg.OperationalError as exception:
            raise RuntimeError(
                f"Connexion à {base} sur {hote}:{port} impossible : {exception}. "
                "Vérifier que le conteneur PostgreSQL tourne "
                "(docker compose up -d)."
            ) from exception

        for chemin in sorted(REPERTOIRE_REQUETES.glob("*.sql")):
            self.requetes[chemin.stem] = chemin.read_text(encoding="utf-8")
        logger.info("%d requêtes de chargement chargées.", len(self.requetes))

        self._lire_nomenclatures()
        self._lire_bilans()
        logger.info("Connecté à %s sur %s:%s", base, hote, port)

    def _lire_bilans(self) -> None:
        """
        Lit les bilans d'exécution déposés par les extracteurs.

        Compétence visée : C4 (épreuve E1) — alimentation de `extraction`

        Choix : une source sans bilan est signalée, pas suppléée. Motivation :
        le chargeur pourrait compter les documents d'une source et en déduire
        une campagne plausible. Il ignorerait la durée réelle, les erreurs
        rencontrées et les enregistrements écartés. Une ligne d'`extraction`
        ainsi fabriquée aurait toutes les apparences d'une mesure sans en être
        une — c'est exactement le travers dont l'incident du 27/08 a montré le
        coût. Mieux vaut une traçabilité incomplète et annoncée qu'une
        traçabilité complète et fausse.
        """
        for chemin in sorted(self.repertoire_bilans.glob("*.bilan.json")):
            try:
                bilan = json.loads(chemin.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exception:
                logger.warning("Bilan illisible, ignoré — %s : %s", chemin.name, exception)
                continue
            code = (bilan.get("code_source") or "").strip()
            if not code:
                logger.warning(
                    "Bilan sans code_source, ignoré — %s. L'extracteur doit "
                    "déclarer son code de source.", chemin.name,
                )
                continue
            self.bilans[code] = bilan

        if self.bilans:
            logger.info(
                "Bilans d'extraction lus : %s",
                ", ".join(f"{c} ({b['statut']}, {b['enregistrements']})"
                          for c, b in sorted(self.bilans.items())),
            )
        else:
            logger.warning(
                "Aucun bilan d'extraction dans %s : les tables extraction et "
                "collecte resteront vides.", self.repertoire_bilans,
            )

    def _lire_nomenclatures(self) -> None:
        """
        Lit `licence` et `source` depuis la base.

        Compétence visée : C4 (épreuve E1)
        """
        with self.connexion.cursor() as curseur:
            curseur.execute("SELECT code_licence, attribution_requise FROM licence")
            self.attribution_par_licence = dict(curseur.fetchall())

            curseur.execute("SELECT code_type_source, code_source FROM source")
            lignes = curseur.fetchall()

        # Le rattachement d'un document à sa source passe par le `code_source`
        # que le document porte. `source_par_type` n'est plus qu'un repli, pour
        # les corpus transformés avant que ce champ n'existe.
        #
        # Compétence visée : C4 (épreuve E1)
        # Ce chargeur refusait de démarrer si deux sources partageaient un type,
        # et il avait raison tant qu'il déduisait la source du type : la
        # sixième source est un second scraping, et le rattachement devenait
        # ambigu. Plutôt que de lever la garde, on a supprimé la déduction
        # qu'elle protégeait.
        self.sources_connues = {ligne[1].strip() for ligne in lignes}
        self.source_par_type = {ligne[0]: ligne[1].strip() for ligne in lignes}

        types = [ligne[0] for ligne in lignes]
        doublons = {t for t in types if types.count(t) > 1}
        if doublons:
            logger.warning(
                "Plusieurs sources déclarent le type %s. Les documents portant "
                "leur `code_source` sont rattachés sans ambiguïté ; ceux qui "
                "n'en portent pas — corpus transformé avant ce champ — seraient "
                "rattachés au hasard et seront rejetés.",
                sorted(doublons),
            )

        # Ces SELECT ont ouvert une transaction implicite : psycopg n'est pas
        # en autocommit. La clore ici est indispensable, et non cosmétique —
        # `connexion.transaction()` ne valide QUE s'il est le bloc le plus
        # externe. Laissée ouverte, la transaction implicite ferait de lui un
        # simple point de reprise : le chargement paraîtrait réussir, la
        # fermeture de la connexion annulerait tout, et la base resterait vide
        # sans le moindre message d'erreur. Le cas s'est produit.
        self.connexion.rollback()

        logger.info(
            "Nomenclatures : %d licences, %d sources (%s)",
            len(self.attribution_par_licence), len(self.source_par_type),
            ", ".join(sorted(self.source_par_type.values())),
        )

    # --- 2. Règles logiques de traitement ---

    def lire_corpus(self) -> Iterator[dict[str, Any]]:
        """
        Lit le corpus transformé ligne à ligne.

        Compétence visée : C4 (épreuve E1)
        """
        with self.chemin_corpus.open(encoding="utf-8") as flux:
            for numero, ligne in enumerate(flux, start=1):
                if not ligne.strip():
                    continue
                try:
                    yield json.loads(ligne)
                except json.JSONDecodeError as exception:
                    self._rejeter(f"ligne {numero}", f"JSON illisible : {exception}")

    def charger(self) -> dict[str, Any]:
        """
        Verse l'ensemble du corpus en une transaction.

        Compétence visée : C4 (épreuve E1)

        Ordre imposé : les mots-clés d'abord, puis les documents avec leur
        spécialisation, puis les rattachements. La table `description`
        référence `mot_cle` par clé étrangère — la nomenclature doit exister
        avant qu'on s'y réfère.
        """
        debut = datetime.now(timezone.utc)
        # Un seul horodatage pour toute la passe : c'est lui qui distingue les
        # documents revus de ceux qui ne l'ont pas été. Rafraîchir l'heure
        # document par document rendrait la comparaison finale illisible.
        self.horodatage_chargement = debut
        documents = list(self.lire_corpus())
        self.rapport["documents_lus"] = len(documents)
        logger.info("%d documents lus dans %s", len(documents), self.chemin_corpus)

        with self.connexion.transaction():
            self._charger_campagnes()
            self._charger_mots_cles(documents)
            for document in documents:
                self._charger_document(document)
            self._marquer_documents_retires(documents)

        # Contrôle explicite : à la sortie du bloc, la transaction doit être
        # close. Si elle ne l'est pas, c'est qu'une transaction implicite
        # l'englobait et que rien n'a été validé. Mieux vaut échouer ici que
        # rendre un bilan flatteur sur une base restée vide.
        statut = self.connexion.info.transaction_status
        if statut != psycopg.pq.TransactionStatus.IDLE:
            raise RuntimeError(
                "La transaction de chargement n'a pas été validée "
                f"(statut {statut!r}). Aucune donnée n'a été écrite. "
                "Une transaction implicite englobait le bloc de chargement."
            )

        self.rapport["duree_secondes"] = round(
            (datetime.now(timezone.utc) - debut).total_seconds(), 2
        )
        return self.rapport

    def _charger_campagnes(self) -> None:
        """
        Verse les bilans d'extraction dans la table `extraction`.

        Compétence visée : C4 (épreuve E1)

        Choix : les campagnes sont chargées avant les documents. Motivation :
        `collecte` référence `extraction` par clé étrangère, et chaque document
        chargé rattache aussitôt sa ligne de collecte. Sans les campagnes en
        place, ce rattachement échouerait document par document.
        """
        connues = set()
        with self.connexion.cursor() as curseur:
            for code, bilan in sorted(self.bilans.items()):
                # `sources_connues` et non `source_par_type.values()` : ce
                # dictionnaire est indexé par TYPE, et depuis que deux sources
                # partagent « scraping », la seconde écrase la première — le
                # bilan de S2 était rejeté au motif que sa source n'existait
                # pas, alors qu'elle était déclarée. Sa campagne d'extraction
                # manquait, et ses documents échappaient au marquage des
                # disparus.
                if code not in self.sources_connues:
                    self._rejeter(
                        f"bilan {code}",
                        f"la source « {code} » n'est pas déclarée dans la table source",
                    )
                    continue
                curseur.execute(self.requetes["inserer_extraction"], {
                    "code_source": code,
                    "horodatage_debut": _horodatage(bilan.get("horodatage")),
                    "duree_secondes": bilan.get("duree_secondes") or 0,
                    "statut": bilan.get("statut"),
                    "nb_enregistrements": bilan.get("enregistrements") or 0,
                    "nb_erreurs": bilan.get("erreurs") or 0,
                    "fichier_sortie": str(bilan.get("fichier") or "")[:255],
                })
                self.extraction_par_source[code] = curseur.fetchone()[0]
                connues.add(code)
                self.rapport["campagnes_chargees"][code] = {
                    "statut": bilan.get("statut"),
                    "enregistrements": bilan.get("enregistrements"),
                    "erreurs": bilan.get("erreurs"),
                    "duree_secondes": bilan.get("duree_secondes"),
                }

        manquantes = sorted(set(self.source_par_type.values()) - connues)
        self.rapport["sources_sans_bilan"] = manquantes
        if manquantes:
            logger.warning(
                "Sources sans bilan d'exécution : %s. Leurs documents seront "
                "chargés, mais sans ligne de collecte — la traçabilité de leur "
                "campagne manquera jusqu'à leur prochaine extraction.",
                ", ".join(manquantes),
            )
        logger.info("Campagnes d'extraction enregistrées : %d", len(connues))

    def _charger_mots_cles(self, documents: list[dict[str, Any]]) -> None:
        """
        Alimente la nomenclature des mots-clés avant tout rattachement.

        Compétence visée : C4 (épreuve E1)

        Choix : les étiquettes de source et les modules pédagogiques entrent
        dans la même table, avec deux catégories distinctes. Motivation : ce
        sont deux vocabulaires d'origines différentes — la communauté Stack
        Exchange d'un côté, le programme de formation de l'autre — mais un
        document se cherche par l'un comme par l'autre. Deux tables
        obligeraient toute requête thématique à faire une union.
        """
        etiquettes: set[str] = set()
        modules: set[str] = set()

        for document in documents:
            etiquettes.update(document.get("mots_cles") or [])
            module = (document.get("metadonnees") or {}).get("module")
            if module:
                modules.add(str(module).strip().lower())

        # Un libellé présent dans les deux vocabulaires n'est inséré qu'une
        # fois : la clé primaire est le libellé seul. L'étiquette l'emporte,
        # étant traitée en premier, et le résultat ne dépend donc pas de
        # l'ordre du corpus.
        with self.connexion.cursor() as curseur:
            for mot in sorted(etiquettes):
                curseur.execute(
                    self.requetes["inserer_mot_cle"],
                    {"code_mot_cle": mot[:60], "categorie": CATEGORIE_ETIQUETTE},
                )
            for mot in sorted(modules - etiquettes):
                curseur.execute(
                    self.requetes["inserer_mot_cle"],
                    {"code_mot_cle": mot[:60], "categorie": CATEGORIE_MODULE},
                )

        self.rapport["mots_cles_charges"] = len(etiquettes | modules)
        logger.info(
            "Mots-clés : %d étiquettes de source, %d modules pédagogiques",
            len(etiquettes), len(modules),
        )

    def _charger_document(self, document: dict[str, Any]) -> None:
        """
        Charge un document, sa spécialisation et ses mots-clés.

        Compétence visée : C4 (épreuve E1)
        """
        type_source = document["code_type_source"]
        # Le code porté par le document prime sur la déduction par le type.
        #
        # Compétence visée : C4 (épreuve E1)
        # Choix : `code_source` d'abord, `source_par_type` en repli. Motivation :
        # la déduction par le type supposait une source par type, ce qui a cessé
        # d'être vrai avec la sixième source — un second scraping. Le repli est
        # conservé pour les corpus transformés avant ce changement, qui ne
        # portent pas le champ.
        code_source = document.get("code_source")
        if code_source is None:
            # Repli pour les corpus antérieurs au champ. Il n'est employé que
            # si le type désigne une source et une seule.
            memes_types = [t for t in self.source_par_type if t == type_source]
            code_source = (self.source_par_type.get(type_source)
                           if len(memes_types) == 1 else None)
        if code_source is None:
            self._rejeter(
                document["identifiant"],
                f"aucune source déclarée pour le type « {type_source} »",
            )
            return
        if code_source not in self.sources_connues:
            self._rejeter(
                document["identifiant"],
                f"source « {code_source} » absente de la nomenclature",
            )
            return

        code_licence = document.get("code_licence")
        if code_licence not in self.attribution_par_licence:
            self._rejeter(
                document["identifiant"],
                f"licence « {code_licence} » absente de la nomenclature",
            )
            return

        parametres = {
            "code_source": code_source,
            "code_type_source": type_source,
            "identifiant_source": document["identifiant"][:120],
            "code_licence": code_licence,
            "attribution_requise": self.attribution_par_licence[code_licence],
            "titre": document["titre"][:255],
            "contenu": document["contenu"],
            "url_source": (document.get("source_url") or None),
            "langue": document.get("langue") or "en",
            "extrait_le": _horodatage(document.get("extrait_le")),
            "dernier_vu_le": self.horodatage_chargement,
        }

        with self.connexion.cursor() as curseur:
            curseur.execute(self.requetes["inserer_document"], parametres)
            id_document = curseur.fetchone()[0]
            self._charger_specialisation(curseur, id_document, document)
            self._rattacher_mots_cles(curseur, id_document, document)
            self._rattacher_collecte(curseur, id_document, document, code_source)

        self.rapport["documents_charges"] += 1
        compte = self.rapport["par_type_source"]
        compte[type_source] = compte.get(type_source, 0) + 1

    def _charger_specialisation(self, curseur, id_document: int,
                                document: dict[str, Any]) -> None:
        """
        Insère la ligne de la table fille correspondant au type de source.

        Compétence visée : C4 (épreuve E1)

        Le déclencheur `document_partition_totale` exige exactement une ligne
        fille par document. Il est différé : la vérification a lieu à la
        validation de la transaction, ce qui autorise l'insertion du document
        avant celle de sa spécialisation.
        """
        type_source = document["code_type_source"]
        metriques = document.get("metriques") or {}
        metadonnees = document.get("metadonnees") or {}

        if type_source == "api_rest":
            curseur.execute(self.requetes["inserer_specialisation_api_rest"], {
                "id_document": id_document,
                "score": metriques.get("score") or 0,
                "nombre_reponses": metriques.get("nombre_reponses") or 0,
                "nombre_vues": metriques.get("vues") or 0,
                "cree_le": _horodatage(document.get("cree_le")),
            })

        elif type_source == "scraping":
            curseur.execute(self.requetes["inserer_specialisation_web"], {
                "id_document": id_document,
                "page": str(metadonnees.get("page") or "")[:255],
                "ancre_section": (str(metadonnees["section_html"])[:255]
                                  if metadonnees.get("section_html") else None),
            })

        elif type_source == "fichier":
            curseur.execute(self.requetes["inserer_specialisation_fichier"], {
                "id_document": id_document,
                "chemin_fichier": str(metadonnees.get("fichier") or "")[:255],
                "format": metadonnees.get("format"),
                "module_pedagogique": str(metadonnees.get("module") or "")[:50],
                "index_section": metadonnees.get("section_index") or 0,
                "origine_declaree": str(metadonnees.get("origine") or "A VERIFIER")[:255],
            })

        else:
            table = TABLES_SIMPLES.get(type_source)
            if table is None:
                raise RuntimeError(
                    f"Type de source « {type_source} » sans table de "
                    "spécialisation. La partition du modèle est totale : "
                    "ajouter la table avant de charger ce type."
                )
            # Le nom de table vient de TABLES_SIMPLES, liste fermée définie
            # dans ce fichier, et jamais d'une donnée du corpus.
            curseur.execute(
                self.requetes["inserer_specialisation_simple"].format(table=table),
                {"id_document": id_document, "code_type_source": type_source},
            )

    def _rattacher_mots_cles(self, curseur, id_document: int,
                             document: dict[str, Any]) -> None:
        """
        Rattache le document à ses mots-clés.

        Compétence visée : C4 (épreuve E1)
        """
        mots = set(document.get("mots_cles") or [])
        module = (document.get("metadonnees") or {}).get("module")
        if module:
            mots.add(str(module).strip().lower())

        for mot in sorted(mots):
            curseur.execute(self.requetes["inserer_description"], {
                "id_document": id_document,
                "code_mot_cle": mot[:60],
            })
            self.rapport["rattachements_charges"] += 1

    def _marquer_documents_retires(self, documents: list[dict[str, Any]]) -> None:
        """
        Marque les documents que ce chargement n'a pas revus.

        Compétence visée : C4 (épreuve E1) — cohérence du jeu de données
        Compétence visée : C1 (épreuve E1) — traçabilité

        Choix : marquer plutôt que supprimer. Motivation : une section de
        documentation qui disparaît entre deux scrapings n'est pas une erreur
        du pipeline, c'est une information sur la source. La supprimer
        effacerait cette information, et avec elle les lignes de `collecte` qui
        attestent qu'elle avait bien été collectée. Le marquage conserve les
        deux et corrige le décompte servi par l'API.

        Choix : ne balayer que les sources présentes dans le corpus chargé.
        Motivation : une source absente ne permet pas de distinguer « rien
        n'a été extrait cette fois » de « tout a disparu ». Sans ce garde-fou,
        recharger après avoir réextrait une seule source retirerait tout le
        reste du corpus — un effacement de masse déclenché par une commande
        anodine.
        """
        # Les codes portés par les documents, et non déduits de leur type.
        #
        # Compétence visée : C4 (épreuve E1)
        # La déduction passait par `source_par_type`, indexé par TYPE : depuis
        # que deux sources partagent « scraping », l'une y écrase l'autre et
        # sortait de cette liste. Ses documents échappaient alors au marquage
        # des disparus — un document retiré de S2 serait resté en base, présenté
        # comme courant, sans que rien ne le signale.
        sources_chargees = sorted({
            d.get("code_source") or self.source_par_type.get(d["code_type_source"])
            for d in documents
        } - {None})

        if not sources_chargees:
            logger.info(
                "Aucune source dans le corpus chargé : aucun marquage de "
                "retrait, faute de pouvoir distinguer une absence d'extraction "
                "d'une disparition.",
            )
            return

        with self.connexion.cursor() as curseur:
            curseur.execute(self.requetes["marquer_documents_retires"], {
                "horodatage": self.horodatage_chargement,
                "sources_chargees": sources_chargees,
            })
            retires = curseur.fetchall()

        self.rapport["documents_retires"] = [
            {
                "id_document": ligne[0],
                "code_source": ligne[1].strip(),
                "identifiant_source": ligne[2],
                "titre": ligne[3],
            }
            for ligne in retires
        ]
        self.rapport["sources_balayees"] = sources_chargees

        if retires:
            logger.warning(
                "%d document(s) marqué(s) retirés — absents de leur source "
                "lors de ce chargement : %s",
                len(retires),
                ", ".join(f"{ligne[1].strip()}/{ligne[2]}" for ligne in retires[:5]),
            )
        else:
            logger.info(
                "Aucun document retiré : tous ceux des sources %s ont été revus.",
                ", ".join(sources_chargees),
            )

    def _rattacher_collecte(self, curseur, id_document: int,
                            document: dict[str, Any], code_source: str) -> None:
        """
        Rattache le document à la campagne qui l'a ramené, et par quel chemin.

        Compétence visée : C4 (épreuve E1)
        Compétence visée : C1 (épreuve E1) — traçabilité de la collecte

        Choix : un document trouvé par plusieurs chemins produit plusieurs
        lignes. Motivation : la question so_16476924 est arrivée par le tag
        « python » puis par le tag « pandas ». La transformation a fusionné les
        deux exemplaires en conservant les deux critères ; n'en enregistrer
        qu'un perdrait au chargement ce qu'elle avait pris soin de sauver.

        Une source sans campagne enregistrée ne produit aucune ligne : mieux
        vaut une absence visible qu'un rattachement à une campagne inventée.
        """
        id_extraction = self.extraction_par_source.get(code_source)
        if id_extraction is None:
            return

        metadonnees = document.get("metadonnees") or {}
        champ = CRITERE_PAR_TYPE.get(document["code_type_source"])
        brut = metadonnees.get(champ) if champ else None

        if brut is None:
            # Repli explicite : le nom de la source elle-même. Le critère est
            # NOT NULL, et un document sans chemin de collecte identifiable
            # reste rattaché à sa campagne plutôt que d'en être exclu.
            criteres = [document.get("source_nom") or code_source]
        elif isinstance(brut, (list, tuple, set)):
            criteres = [str(valeur) for valeur in brut if str(valeur).strip()]
        else:
            criteres = [str(brut)]

        vu_le = _horodatage(document.get("extrait_le"))
        for critere in criteres:
            curseur.execute(self.requetes["inserer_collecte"], {
                "id_extraction": id_extraction,
                "id_document": id_document,
                "critere_collecte": critere[:200],
                "vu_le": vu_le,
            })
            self.rapport["collectes_chargees"] += 1

    # --- 3. Gestion des erreurs et exceptions ---

    def _rejeter(self, identifiant: str, motif: str) -> None:
        """
        Consigne un document écarté sans interrompre le chargement.

        Compétence visée : C4 (épreuve E1)

        Choix : un rejet est compté et journalisé, jamais silencieux. Un
        chargement qui annonce 6 800 documents alors que 36 ont été écartés
        est un chargement qui ment. Les rejets figurent au rapport, avec leur
        motif.
        """
        self.rapport["rejets"].append({"document": identifiant, "motif": motif})
        logger.warning("Document écarté — %s : %s", identifiant, motif)

    def nettoyer(self) -> None:
        """
        Ferme la connexion à la base.

        Compétence visée : C4 (épreuve E1)
        """
        if self.connexion is not None:
            self.connexion.close()
            self.connexion = None
            logger.info("Connexion à eduai_data fermée.")


# --- 4. Sauvegarde des résultats ---

def _horodatage(valeur: str | None) -> datetime | None:
    """
    Convertit une chaîne ISO du corpus en objet daté.

    Compétence visée : C4 (épreuve E1)

    Choix : passer un `datetime` à psycopg plutôt qu'une chaîne. Motivation :
    le pilote applique alors le typage `timestamptz` sans interprétation
    textuelle côté serveur, et une valeur mal formée échoue ici, avec le nom du
    document, plutôt qu'à l'insertion.
    """
    if not valeur:
        return None
    return datetime.fromisoformat(valeur)


def ecrire_rapport(rapport: dict[str, Any], repertoire: Path) -> Path:
    """
    Écrit le rapport de chargement à côté du corpus.

    Compétence visée : C4 (épreuve E1)
    """
    chemin = repertoire / "rapport_chargement.json"
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Rapport de chargement écrit : %s", chemin)
    return chemin


# --- 5. Point de lancement ---

def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement du chargement.

    Compétence visée : C4 (épreuve E1)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    analyseur = argparse.ArgumentParser(
        description="Chargement du corpus transformé dans eduai_data.",
    )
    analyseur.add_argument(
        "--corpus", type=Path, default=CORPUS_PAR_DEFAUT,
        help=f"Corpus transformé à charger (défaut : {CORPUS_PAR_DEFAUT}).",
    )
    analyseur.add_argument("--base", default=None, help="Nom de la base (défaut : POSTGRES_DB).")
    analyseur.add_argument("--hote", default=None, help="Hôte PostgreSQL (défaut : POSTGRES_HOST).")
    analyseur.add_argument("--port", default=None, help="Port PostgreSQL (défaut : POSTGRES_PORT).")
    analyseur.add_argument("--utilisateur", default=None, help="Rôle (défaut : POSTGRES_USER).")
    arguments = analyseur.parse_args(argv)

    chargeur = Chargeur(
        chemin_corpus=arguments.corpus, base=arguments.base,
        hote=arguments.hote, port=arguments.port, utilisateur=arguments.utilisateur,
    )

    try:
        chargeur.initialiser()
        rapport = chargeur.charger()
    except FileNotFoundError as exception:
        logger.error("Prérequis manquant : %s", exception)
        return 2
    except RuntimeError as exception:
        logger.error("Chargement impossible : %s", exception)
        return 2
    except psycopg.errors.ForeignKeyViolation as exception:
        # Différencié des autres erreurs de base : c'est le symptôme d'une
        # nomenclature incomplète, et le message doit le dire.
        logger.error(
            "Clé étrangère violée : %s. Une nomenclature est incomplète — "
            "vérifier les tables licence, source et type_source.", exception,
        )
        return 3
    except Exception as exception:  # noqa: BLE001 — journalisé puis remonté
        logger.exception("Chargement interrompu : %s", exception)
        return 1
    finally:
        chargeur.nettoyer()

    ecrire_rapport(rapport, arguments.corpus.parent)
    logger.info(
        "Bilan — %d documents lus, %d chargés, %d campagnes, %d mots-clés, "
        "%d rattachements, %d collectes, %d retirés, %d rejets, %.2f s",
        rapport["documents_lus"], rapport["documents_charges"],
        len(rapport["campagnes_chargees"]), rapport["mots_cles_charges"],
        rapport["rattachements_charges"], rapport["collectes_chargees"],
        len(rapport["documents_retires"]), len(rapport["rejets"]),
        rapport["duree_secondes"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
