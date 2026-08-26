"""
Source 1 — Service web (API REST) : Stack Overflow via l'API Stack Exchange.

Compétence visée : C1 (épreuve E1) — extraction depuis un service web

Type de source : api_rest (1 des 5 types exigés par le référentiel)
Licence du contenu : CC BY-SA 4.0 — attribution obligatoire, conservée dans
    les métadonnées de chaque enregistrement (champ `source_url`).
Conditions d'utilisation : https://api.stackexchange.com/docs
Quota : 300 requêtes/jour sans clé, 10 000 avec clé applicative gratuite.
    Le quota restant est retourné par l'API dans le champ `quota_remaining`
    et journalisé à chaque appel.

Choix : Stack Overflow plutôt qu'une source documentaire. Motivation : le
corpus existant (data/contents/) couvre déjà la théorie. Ce qui lui manque,
ce sont les erreurs réelles des apprenants et les cas limites — exactement ce
que contiennent les questions Stack Overflow. La valeur ajoutée pour le RAG est
donc complémentaire, pas redondante.

Choix : filtrage par tags alignés sur les modules du corpus (python, pandas,
sql, machine-learning, numpy) plutôt qu'une collecte généraliste. Motivation :
un RAG se dégrade quand le corpus s'éloigne du domaine interrogé.

Choix : pagination limitée et pause entre appels, même sous le quota autorisé.
Motivation : C1 exige le respect des contraintes de la source. Un extracteur
qui sature un quota gratuit est un extracteur mal conçu.
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
from typing import Any, Iterator

import requests

from .base_extractor import Enregistrement, ExtracteurBase

logger = logging.getLogger(__name__)

URL_API = "https://api.stackexchange.com/2.3/questions"

# Tags alignés sur les modules 01 à 05 et 08 du corpus.
TAGS_CIBLES = ("python", "pandas", "sql", "machine-learning", "numpy")

# Filtre Stack Exchange incluant le corps des questions ET le tableau des
# réponses. Sans filtre personnalisé, l'API ne retourne que les métadonnées :
# ni `question.body`, ni `question.answers`, donc rien d'exploitable pour un RAG.
#
# Un identifiant de filtre peut être invalidé par le fournisseur. Commande de
# régénération (vérifiée le 26/08/2026, retourne un JSON contenant `filter`) :
#   GET https://api.stackexchange.com/2.3/filters/create
#       ?base=default&unsafe=false
#       &include=question.body;question.answers;answer.body;answer.is_accepted
FILTRE_AVEC_CORPS = "!20aKG._8Oscv*6djs8Pgm"

PAUSE_ENTRE_APPELS_SECONDES = 1.0
PAGES_MAX_PAR_TAG = 3
TAILLE_PAGE = 100

# Nombre de tentatives par appel avant abandon, en cas d'erreur réseau ou
# d'erreur serveur. Voir `_appeler_api`.
TENTATIVES_MAX = 3


class ExtracteurStackOverflow(ExtracteurBase):
    """
    Extrait les questions résolues de Stack Overflow pour les tags ciblés.

    Compétence visée : C1 (épreuve E1)

    Choix : ne conserver que les questions disposant d'une réponse acceptée.
    Motivation : une question sans réponse validée introduit du bruit dans le
    RAG — le modèle pourrait citer une piste erronée comme si elle faisait
    autorité.

    Note vérifiée sur l'API : le point de terminaison /questions n'accepte pas
    de paramètre `accepted` (réservé à /search/advanced) et l'ignore
    silencieusement. Le filtrage est donc appliqué côté client dans
    `_convertir`, ce qui écarte environ 9 % des questions retournées.
    """

    nom = "s1_stackoverflow"
    type_source = "api_rest"
    licence = "CC BY-SA 4.0"

    def __init__(self, tags: tuple[str, ...] = TAGS_CIBLES, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tags = tags
        self.session: requests.Session | None = None
        self.cle_api = os.getenv("STACKEXCHANGE_KEY")  # optionnelle
        self.quota_restant: int | None = None

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Ouvre la session HTTP et vérifie que l'API répond.

        Compétence visée : C1 (épreuve E1)

        Choix : un User-Agent identifiant explicitement le projet. Motivation :
        exigence de bonne conduite vis-à-vis de la source, et traçabilité côté
        fournisseur en cas de comportement anormal de l'extracteur.
        """
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "EduAI-Tutor/1.0 (projet pedagogique RNCP 37827)"}
        )

        reponse = self.session.get(
            URL_API,
            params={"site": "stackoverflow", "pagesize": 1},
            timeout=15,
        )
        reponse.raise_for_status()
        self.quota_restant = reponse.json().get("quota_remaining")
        logger.info(
            "[%s] API joignable — quota restant : %s", self.nom, self.quota_restant
        )

        if self.cle_api is None:
            logger.warning(
                "[%s] Aucune clé STACKEXCHANGE_KEY : quota limité à 300 req/jour.",
                self.nom,
            )

    # --- 2. Règles logiques de traitement ---

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Parcourt les tags ciblés et produit un enregistrement par question.

        Compétence visée : C1 (épreuve E1)
        """
        for tag in self.tags:
            logger.info("[%s] Extraction du tag « %s »", self.nom, tag)
            yield from self._extraire_tag(tag)

    def _extraire_tag(self, tag: str) -> Iterator[Enregistrement]:
        """
        Extrait les questions d'un tag, page par page.

        Compétence visée : C1 (épreuve E1)
        """
        for numero_page in range(1, PAGES_MAX_PAR_TAG + 1):
            donnees = self._appeler_api(tag, numero_page)

            for question in donnees.get("items", []):
                enregistrement = self._convertir(question, tag)
                if enregistrement is not None:
                    yield enregistrement

            if not donnees.get("has_more"):
                logger.info("[%s] Tag « %s » : fin à la page %d", self.nom, tag, numero_page)
                break

    def _appeler_api(self, tag: str, numero_page: int) -> dict[str, Any]:
        """
        Appelle l'API avec réessais, en distinguant les causes d'échec.

        Compétence visée : C1 (épreuve E1) — gestion des erreurs et exceptions

        Choix : trois familles d'erreurs traitées différemment plutôt qu'un
        `except Exception` unique. Motivation : elles n'appellent pas la même
        réaction. Une coupure réseau ou une erreur 5xx est transitoire et
        justifie un réessai ; une erreur 4xx (hors 429) vient de notre requête
        et sera identique au réessai suivant — insister ne ferait que
        consommer le quota.
        """
        if self.session is None:
            raise RuntimeError(
                f"[{self.nom}] initialiser() doit être appelé avant _appeler_api()."
            )

        derniere_erreur: Exception | None = None

        for tentative in range(1, TENTATIVES_MAX + 1):
            # Rythme d'appel appliqué avant chaque requête, y compris entre
            # deux tags : le quota gratuit est un bien commun, pas une cible.
            time.sleep(PAUSE_ENTRE_APPELS_SECONDES)
            try:
                return self._appel_unique(tag, numero_page)

            except requests.HTTPError as erreur:
                statut = (
                    erreur.response.status_code if erreur.response is not None else None
                )
                if statut is not None and 400 <= statut < 500 and statut != 429:
                    logger.error(
                        "[%s] Requête refusée (HTTP %s) sur le tag « %s » — "
                        "aucun réessai, la requête est en cause.",
                        self.nom, statut, tag,
                    )
                    raise
                derniere_erreur = erreur

            except (requests.ConnectionError, requests.Timeout) as erreur:
                derniere_erreur = erreur

            except ValueError as erreur:
                # Corps de réponse non décodable en JSON : souvent une page
                # d'erreur HTML servie par un intermédiaire réseau.
                derniere_erreur = erreur

            attente = PAUSE_ENTRE_APPELS_SECONDES * 2 ** tentative
            logger.warning(
                "[%s] Tentative %d/%d échouée sur « %s » page %d (%s) — "
                "nouvel essai dans %.0f s",
                self.nom, tentative, TENTATIVES_MAX, tag, numero_page,
                type(derniere_erreur).__name__, attente,
            )
            time.sleep(attente)

        raise RuntimeError(
            f"[{self.nom}] Abandon après {TENTATIVES_MAX} tentatives "
            f"sur le tag « {tag} », page {numero_page}."
        ) from derniere_erreur

    def _appel_unique(self, tag: str, numero_page: int) -> dict[str, Any]:
        """
        Effectue un appel à l'API et retourne la réponse décodée.

        Compétence visée : C1 (épreuve E1)

        Choix : respect immédiat du champ `backoff` renvoyé par l'API.
        Motivation : ignorer un backoff conduit au blocage de l'adresse IP par
        le fournisseur, ce qui rendrait la source indisponible pour la suite du
        projet.
        """
        assert self.session is not None  # garanti par _appeler_api

        parametres: dict[str, Any] = {
            "site": "stackoverflow",
            "tagged": tag,
            "sort": "votes",
            "order": "desc",
            "filter": FILTRE_AVEC_CORPS,
            "pagesize": TAILLE_PAGE,
            "page": numero_page,
        }
        if self.cle_api:
            parametres["key"] = self.cle_api

        reponse = self.session.get(URL_API, params=parametres, timeout=30)
        reponse.raise_for_status()
        donnees = reponse.json()

        self.quota_restant = donnees.get("quota_remaining", self.quota_restant)
        logger.debug(
            "[%s] Tag « %s » page %d : %d éléments, quota restant %s",
            self.nom, tag, numero_page, len(donnees.get("items", [])),
            self.quota_restant,
        )

        if "backoff" in donnees:
            attente = int(donnees["backoff"])
            logger.warning("[%s] Backoff demandé : pause de %d s", self.nom, attente)
            time.sleep(attente)

        return donnees

    def _convertir(self, question: dict[str, Any], tag: str) -> Enregistrement | None:
        """
        Transforme une question de l'API en Enregistrement du contrat commun.

        Compétence visée : C1 (épreuve E1)

        Choix : concaténer question et réponse acceptée dans un seul contenu.
        Motivation : pour un RAG, une question sans sa réponse est inutilisable,
        et les séparer produirait des chunks orphelins.

        Returns:
            None si la question est inexploitable (contenu vide) — l'appelant
            ignore alors l'enregistrement plutôt que de polluer le corpus.
        """
        corps_question = self._nettoyer_html(question.get("body", ""))
        reponse_acceptee = self._trouver_reponse_acceptee(question)

        if not corps_question or not reponse_acceptee:
            return None

        titre = html.unescape(question.get("title", "")).strip()
        contenu = (
            f"Question : {titre}\n\n"
            f"{corps_question}\n\n"
            f"Réponse acceptée :\n{reponse_acceptee}"
        )

        return Enregistrement(
            identifiant=f"so_{question['question_id']}",
            titre=titre,
            contenu=contenu,
            source_nom="Stack Overflow",
            source_type=self.type_source,
            source_url=question.get("link"),
            licence=self.licence,
            langue="en",
            metadonnees={
                "tag_recherche": tag,
                "tags": question.get("tags", []),
                "score": question.get("score"),
                "nombre_reponses": question.get("answer_count"),
                "vues": question.get("view_count"),
                "cree_le": question.get("creation_date"),
            },
        )

    @staticmethod
    def _trouver_reponse_acceptee(question: dict[str, Any]) -> str | None:
        """
        Extrait le corps de la réponse acceptée d'une question.

        Compétence visée : C1 (épreuve E1)
        """
        identifiant_accepte = question.get("accepted_answer_id")
        if identifiant_accepte is None:
            return None

        for reponse in question.get("answers", []):
            if reponse.get("answer_id") == identifiant_accepte:
                return ExtracteurStackOverflow._nettoyer_html(reponse.get("body", ""))
        return None

    @staticmethod
    def _nettoyer_html(contenu_html: str) -> str:
        """
        Convertit le HTML de l'API en texte, en préservant les blocs de code.

        Compétence visée : C1 (épreuve E1)

        Choix : isoler les blocs de code avant la normalisation des espaces,
        puis les réinsérer délimités par des triples backticks. Motivation : le
        code est l'essentiel de la valeur pédagogique ici. Normaliser les
        espaces sans cette précaution écrase l'indentation — un extrait Python
        désindenté est syntaxiquement faux, donc pire qu'absent dans un RAG.

        Note : le nettoyage fin (normalisation, déduplication) relève de la
        phase de transformation (C3), pas de l'extraction. On reste ici au
        strict nécessaire pour obtenir du texte lisible.
        """
        if not contenu_html:
            return ""

        # Les blocs de code sont mis de côté AVANT toute normalisation des
        # espaces : appliquer « suites d'espaces -> un espace » à du Python
        # détruirait l'indentation, donc la validité du code.
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

        # Réinsertion des blocs de code, indentation intacte.
        for numero, bloc in enumerate(blocs_code):
            code = bloc.strip("\n")
            texte = texte.replace(f"\x00BLOC{numero}\x00", f"```\n{code}\n```")

        return texte

    # --- 3. Gestion des erreurs : héritée de ExtracteurBase ---
    # --- 4. Sauvegarde : héritée de ExtracteurBase ---

    def nettoyer(self) -> None:
        """
        Ferme la session HTTP.

        Compétence visée : C1 (épreuve E1)
        """
        if self.session is not None:
            self.session.close()
            self.session = None
        logger.info("[%s] Quota restant en fin d'extraction : %s", self.nom, self.quota_restant)


# --- 5. Point de lancement ---

def main() -> None:
    """
    Point d'entrée du script, exécutable indépendamment du pipeline complet.

    Compétence visée : C1 (épreuve E1)

    Le référentiel exige que chaque script d'extraction dispose de son propre
    point de lancement. Il reste par ailleurs appelable depuis l'orchestrateur.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    bilan = ExtracteurStackOverflow().executer()
    logger.info("Bilan : %s", bilan)


if __name__ == "__main__":
    main()
