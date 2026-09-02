"""
Extraction depuis SCRAPING — documentation officielle des bibliothèques.

Compétence visée : C1 (épreuve E1)
Compétences concernées : C2 (E1) ; C4 (E1) — licence et attribution

**Cette source ne débloque aucun critère de C1.** Les cinq types exigés — service
web, scraping, fichier, base de données, big data — sont couverts par S1 à S5.
S6 est un second scraping : elle enrichit le corpus, elle n'élargit pas la
couverture. Voir décision 039, qui le dit dans ces termes.

Ce qu'elle apporte : le corpus ne contenait aucune documentation de référence
sur les bibliothèques que le programme enseigne. Six modules du référentiel sont
couverts, un septième — le module 09 — a été écarté parce que la documentation
de Git est en GPL v2, dont les obligations dépassent le cadre de ce corpus.

Contraintes des sources :
    - `robots.txt` vérifié **par le code**, cible par cible, et téléchargé avec
      l'agent du projet. Ce dernier point n'est pas un détail : voir la note
      « Le robots.txt se télécharge avec notre agent » plus bas.
    - Deux secondes entre requêtes, `User-Agent` identifiant le projet.
    - Licences vérifiées à la source, jamais reprises d'un tableau.

Sortie : data_pipeline/data/raw/s6_documentation_bibliotheques.jsonl
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from data_pipeline.extract.base_extractor import Enregistrement, ExtracteurBase
from data_pipeline.extract.s2_scraping_python_docs import ExtracteurPythonDocs

logger = logging.getLogger(__name__)

# --- 1. Initialisation des dépendances et connexions externes ---

USER_AGENT = "EduAI-Tutor/1.0 (projet pedagogique RNCP 37827)"
PAUSE_ENTRE_REQUETES_SECONDES = 2.0
DELAI_EXPIRATION_SECONDES = 30

# En deçà, une section est un sommaire ou un renvoi, pas du contenu.
LONGUEUR_MINIMALE = 200


def _nettoyer_titre(texte: str) -> str:
    """
    Retire le lien d'ancre que les générateurs collent au bout des titres.

    Compétence visée : C1 (épreuve E1)
    Choix : traiter « # » comme « ¶ ». Motivation : S2 ne retirait que le
    pied-de-mouche, forme employée par les anciennes versions de Sphinx. Les
    documentations collectées ici emploient le croisillon, et les titres
    arrivaient en « torch.Tensor# ».
    """
    return texte.rstrip("¶#").replace("\xa0", " ").strip()


@dataclass(frozen=True)
class Cible:
    """
    Une documentation à collecter, avec ce qui la distingue des autres.

    Compétence visée : C1 (épreuve E1)
    Choix : un objet par cible plutôt qu'une suite de conditions dans le code.
    Motivation : ces sept documentations n'ont ni la même structure HTML, ni la
    même licence, ni le même module de rattachement. Les décrire en données
    rend le périmètre lisible d'un coup d'œil — c'est lui qui a été validé, pas
    le code qui le parcourt.
    """

    cle: str
    nom_source: str
    racine: str
    licence: str
    module: str
    selecteur: str | None   # conteneur de contenu ; None = balises <section>
    copyright: str
    pages: tuple[str, ...]


CIBLES: tuple[Cible, ...] = (
    Cible(
        cle="pandas",
        nom_source="Documentation pandas",
        racine="https://pandas.pydata.org/docs/user_guide/",
        licence="BSD 3-Clause",
        module="02 — Analyse de données",
        selecteur=None,
        copyright="Copyright (c) 2008-2026, AQR Capital Management, LLC, "
                  "Lambda Foundry, Inc. and PyData Development Team",
        # `io.html` est volontairement absent : 251 230 caractères, soit 314
        # fragments à lui seul — plus que le module 03 entier. C'est la
        # référence exhaustive des entrées et sorties, que le cadrage exclut au
        # profit des guides d'utilisation (décision 039).
        pages=("dsintro.html", "basics.html", "indexing.html", "missing_data.html",
               "groupby.html", "merging.html", "reshaping.html", "timeseries.html",
               "categorical.html"),
    ),
    Cible(
        cle="postgresql",
        nom_source="Documentation PostgreSQL",
        racine="https://www.postgresql.org/docs/current/",
        licence="PostgreSQL License",
        module="03 — SQL et bases relationnelles",
        selecteur="div.sect1",
        copyright="Copyright (c) 1996-2026 The PostgreSQL Global Development Group",
        pages=("tutorial-select.html", "tutorial-join.html", "tutorial-agg.html",
               "tutorial-update.html", "ddl-constraints.html", "indexes-intro.html",
               "queries-table-expressions.html", "functions-aggregate.html",
               "transaction-iso.html", "performance-tips.html"),
    ),
    Cible(
        cle="scikit-learn",
        nom_source="Documentation scikit-learn",
        racine="https://scikit-learn.org/stable/modules/",
        licence="BSD 3-Clause",
        module="04 — Apprentissage automatique",
        selecteur=None,
        copyright="Copyright (c) 2007-2026 The scikit-learn developers",
        pages=("tree.html", "linear_model.html", "svm.html", "ensemble.html",
               "neighbors.html", "clustering.html", "cross_validation.html",
               "grid_search.html", "preprocessing.html", "model_evaluation.html"),
    ),
    Cible(
        cle="pytorch",
        # URL versionnée, et c'est délibéré : `/docs/stable/` ne sert pas de
        # documentation mais une redirection JavaScript de quarante-cinq
        # caractères. La péremption silencieuse que cela crée est consignée en
        # réserve 20.
        nom_source="Documentation PyTorch 2.13",
        racine="https://docs.pytorch.org/docs/2.13/",
        licence="BSD 3-Clause",
        module="05 — Apprentissage profond",
        selecteur=None,
        copyright="Copyright (c) 2016-2026 PyTorch contributors",
        pages=("tensors.html", "notes/autograd.html", "nn.html", "optim.html",
               "data.html"),
    ),
    Cible(
        cle="opencv",
        nom_source="Documentation OpenCV",
        racine="https://docs.opencv.org/4.x/",
        licence="Apache 2.0",
        module="06 — Vision par ordinateur",
        selecteur="div.textblock",
        copyright="Copyright (c) 2026 OpenCV team",
        pages=(),  # relevées depuis le sommaire, voir `_pages_opencv`
    ),
    Cible(
        cle="drf",
        nom_source="Documentation Django REST framework",
        racine="https://www.django-rest-framework.org/api-guide/",
        licence="BSD 3-Clause",
        module="08 — API web",
        selecteur="div.md-main__inner",
        copyright="Copyright (c) 2011-2026, Encode OSS Ltd.",
        pages=("serializers/", "views/", "generic-views/", "viewsets/", "routers/",
               "authentication/", "permissions/", "throttling/", "pagination/",
               "filtering/"),
    ),
    Cible(
        cle="fastapi",
        nom_source="Documentation FastAPI",
        racine="https://fastapi.tiangolo.com/tutorial/",
        licence="MIT",
        module="08 — API web",
        selecteur="div.md-main__inner",
        copyright="Copyright (c) 2018-2026 Sebastián Ramírez",
        pages=("first-steps/", "path-params/", "query-params/", "body/",
               "response-model/", "dependencies/", "security/first-steps/",
               "handling-errors/"),
    ),
)


class ExtracteurDocumentationBibliotheques(ExtracteurBase):
    """
    Collecte la documentation officielle des bibliothèques du programme.

    Compétence visée : C1 (épreuve E1)

    Choix : découpage par section, comme S2, et non par page. Motivation : une
    page de documentation dépasse souvent 50 000 caractères — `pandas/io.html`
    en compte 251 230 — ce qui produirait des unités sans cohérence. La section
    est le découpage choisi par l'auteur du texte.

    Choix : le nettoyage HTML est **importé de S2**, non réécrit. Motivation :
    il préserve l'indentation des blocs de code, correction issue d'un défaut
    de S1 (décision 003). En réécrire un second exposerait à refaire l'erreur.
    """

    nom = "s6_documentation_bibliotheques"
    type_source = "scraping"
    # La licence varie d'une cible à l'autre : elle est portée par chaque
    # enregistrement, et le chargeur la lit là (`code_licence` par document).
    licence = "multiple — portée par chaque enregistrement"
    code_source = "s6"

    def __init__(self, cibles: tuple[Cible, ...] = CIBLES, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cibles = cibles
        self.session: requests.Session | None = None
        self.robots_par_hote: dict[str, RobotFileParser] = {}

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Ouvre la session HTTP et charge le `robots.txt` de chaque hôte.

        Compétence visée : C1 (épreuve E1)

        **Le robots.txt se télécharge avec NOTRE agent.**

        `RobotFileParser.read()` va chercher le fichier lui-même, avec l'agent
        d'urllib — que plusieurs de ces sites refusent. Le refus porte alors sur
        *le téléchargement du fichier de règles*, jamais sur les pages que ces
        règles autorisent, et `can_fetch` répond `False` : une valeur
        parfaitement valide, qui veut dire « n'y allez pas ».

        Deux cibles licites ont failli être écartées ainsi. Le fichier est donc
        récupéré par la session du projet, puis passé à `parse()`.

        Choix : échouer si un `robots.txt` répond autre chose que des règles ou
        une absence franche. Motivation : un fichier qui renvoie du HTML n'est
        pas un fichier de règles ; décider soi-même qu'il vaut permission serait
        s'accorder une autorisation que personne n'a donnée.
        """
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        for hote in sorted({urlparse(c.racine).netloc for c in self.cibles}):
            url_robots = f"https://{hote}/robots.txt"
            try:
                reponse = self.session.get(url_robots, timeout=DELAI_EXPIRATION_SECONDES)
            except requests.RequestException as exception:
                raise RuntimeError(
                    f"robots.txt injoignable ({url_robots}) : {exception}. "
                    "Extraction annulée."
                ) from exception

            lecteur = RobotFileParser()
            if reponse.status_code == 404:
                # Absence franche : la convention veut que tout soit permis.
                lecteur.parse([])
                logger.info("[%s] %s — pas de robots.txt, accès libre", self.nom, hote)
            elif reponse.status_code == 200 and "<html" not in reponse.text[:200].lower():
                lecteur.parse(reponse.text.splitlines())
                logger.info("[%s] %s — robots.txt chargé", self.nom, hote)
            else:
                raise RuntimeError(
                    f"robots.txt inexploitable pour {hote} "
                    f"(http {reponse.status_code}). Extraction annulée."
                )
            self.robots_par_hote[hote] = lecteur

    def _est_autorise(self, url: str) -> bool:
        """Indique si le `robots.txt` de l'hôte autorise cette URL à notre agent."""
        lecteur = self.robots_par_hote.get(urlparse(url).netloc)
        if lecteur is None:
            return False
        return lecteur.can_fetch(USER_AGENT, url)

    # --- 2. Règles logiques de traitement ---

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Parcourt chaque cible et produit un enregistrement par section.

        Compétence visée : C1 (épreuve E1)
        """
        for cible in self.cibles:
            pages = self._pages_opencv() if cible.cle == "opencv" else cible.pages
            logger.info("[%s] %s — %d pages", self.nom, cible.cle, len(pages))
            for page in pages:
                url = urljoin(cible.racine, page)
                if not self._est_autorise(url):
                    logger.warning("[%s] robots.txt interdit %s — page ignorée",
                                   self.nom, url)
                    continue
                yield from self._extraire_page(cible, url)
                time.sleep(PAUSE_ENTRE_REQUETES_SECONDES)

    def _pages_opencv(self) -> tuple[str, ...]:
        """
        Relève les tutoriels Python d'OpenCV depuis leurs sommaires.

        Compétence visée : C1 (épreuve E1)

        Choix : lire la liste dans les sommaires du site plutôt que d'écrire à
        la main des URL Doxygen. Motivation : ces URL portent un condensé —
        `d3/df2/tutorial_py_basic_ops.html` — qu'on ne devine pas et qu'une
        faute de frappe rendrait silencieusement absent du corpus.

        Ce n'est **pas** un parcours automatique du site : la profondeur est de
        deux niveaux, bornée par les sommaires que les auteurs ont eux-mêmes
        écrits. Les pages d'installation et les index de navigation sont
        écartés — ils n'ont pas de contenu pédagogique.
        """
        racine = "https://docs.opencv.org/4.x/"
        depart = urljoin(racine, "d6/d00/tutorial_py_root.html")
        soup = BeautifulSoup(self._telecharger(depart), "html.parser")
        time.sleep(PAUSE_ENTRE_REQUETES_SECONDES)

        sommaires = {urljoin(depart, a["href"])
                     for a in soup.find_all("a", href=True)
                     if "tutorial_py_" in a["href"] and "table_of_contents" in a["href"]}

        pages: set[str] = set()
        for sommaire in sorted(sommaires):
            page = BeautifulSoup(self._telecharger(sommaire), "html.parser")
            for lien in page.find_all("a", href=True):
                href = lien["href"]
                if "tutorial_py_" in href and "table_of_contents" not in href:
                    pages.add(urljoin(sommaire, href))
            time.sleep(PAUSE_ENTRE_REQUETES_SECONDES)

        ecartees = ("setup", "install", "_index", "py_intro")
        retenues = sorted(p.replace(racine, "") for p in pages
                          if not any(motif in p for motif in ecartees))
        logger.info("[%s] opencv — %d tutoriels relevés dans %d sommaires",
                    self.nom, len(retenues), len(sommaires))
        return tuple(retenues)

    def _telecharger(self, url: str) -> str:
        """Télécharge une page, en laissant l'erreur remonter au socle."""
        reponse = self.session.get(url, timeout=DELAI_EXPIRATION_SECONDES)
        reponse.raise_for_status()
        return reponse.text

    def _extraire_page(self, cible: Cible, url: str) -> Iterator[Enregistrement]:
        """
        Télécharge une page et produit un enregistrement par section.

        Compétence visée : C1 (épreuve E1)
        """
        soup = BeautifulSoup(self._telecharger(url), "html.parser")
        for indesirable in soup(["script", "style", "nav", "footer", "header"]):
            indesirable.decompose()

        blocs = self._decouper(soup, cible)
        if not blocs:
            logger.warning("[%s] aucune section trouvée sur %s", self.nom, url)
            return

        for rang, (ancre, titre, fragment) in enumerate(blocs):
            enregistrement = self._convertir(cible, url, rang, ancre, titre, fragment)
            if enregistrement is not None:
                yield enregistrement

    def _decouper(self, soup: Any, cible: Cible) -> list[tuple[str, str, Any]]:
        """
        Découpe une page en sections, selon la structure de la cible.

        Compétence visée : C1 (épreuve E1)

        Choix : deux stratégies, et le choix est déclaré par cible plutôt que
        deviné. Motivation : seules pandas, scikit-learn et PyTorch produisent
        des balises `<section>` — le cadrage initial supposait qu'elles étaient
        quatre. Pour les autres, le titre `h2`/`h3` est l'unité que l'auteur a
        choisie, et un sélecteur qui « marche » par accident produirait un
        contenu tronqué que rien ne signalerait.
        """
        if cible.selecteur is None:
            sections = soup.find_all("section")
            return [(s.get("id", ""), self._titre_de(s), s) for s in sections]

        conteneurs = soup.select(cible.selecteur)
        if not conteneurs:
            return []

        blocs: list[tuple[str, str, Any]] = []
        for conteneur in conteneurs:
            titres = conteneur.find_all(["h2", "h3"])
            if not titres:
                # Page sans sous-titre : elle fait une section à elle seule.
                # C'est le cas des tutoriels OpenCV, courts par construction.
                blocs.append((conteneur.get("id", ""), self._titre_de(conteneur),
                              conteneur))
                continue
            decoupes: list[tuple[str, str, Any]] = []
            for titre in titres:
                morceau = BeautifulSoup("<div></div>", "html.parser").div
                morceau.append(BeautifulSoup(str(titre), "html.parser"))
                for suivant in titre.find_next_siblings():
                    if suivant.name in ("h2", "h3"):
                        break
                    morceau.append(BeautifulSoup(str(suivant), "html.parser"))
                ancre = titre.get("id") or (titre.find("a") or {}).get("id", "")
                decoupes.append((ancre or "",
                                 _nettoyer_titre(titre.get_text(strip=True)), morceau))

            # Un découpage qui perd du texte n'est pas un découpage.
            #
            # Compétence visée : C1 (épreuve E1), C21 (E5)
            # Les titres ne sont pas toujours frères du contenu : chez
            # PostgreSQL, le `h2` vit dans un `div.titlepage` et ses « frères »
            # ne contiennent rien. Le découpage produisait alors des blocs
            # réduits au seul titre, tous écartés pour longueur insuffisante —
            # et la page entière disparaissait du corpus **sans qu'aucune
            # erreur ne soit levée**. C'est exactement le sélecteur qui marche
            # par accident, en produisant un contenu tronqué que rien ne
            # signale.
            #
            # On compare donc ce que le découpage retient au texte du
            # conteneur. S'il en perd le tiers, on ne découpe pas : la page
            # fait une section, ce qui est toujours préférable à une page
            # perdue.
            retenu = sum(len(m.get_text(" ", strip=True)) for _, _, m in decoupes)
            entier = len(conteneur.get_text(" ", strip=True))
            if entier and retenu < entier * 0.66:
                logger.info(
                    "[%s] découpage par titres écarté (%d caractères retenus "
                    "sur %d) — la page fait une section", self.nom, retenu, entier)
                blocs.append((conteneur.get("id", ""), self._titre_de(conteneur),
                              conteneur))
            else:
                blocs.extend(decoupes)
        return blocs

    @staticmethod
    def _titre_de(element: Any) -> str:
        """Rend le premier titre d'un élément, sans le lien d'ancre de Sphinx."""
        balise = element.find(["h1", "h2", "h3"])
        return _nettoyer_titre(balise.get_text(strip=True)) if balise else ""

    def _convertir(self, cible: Cible, url: str, rang: int, ancre: str,
                   titre: str, fragment: Any) -> Enregistrement | None:
        """
        Transforme une section en Enregistrement du contrat commun.

        Compétence visée : C1 (épreuve E1)
        Compétence visée : C4 (épreuve E1) — la licence voyage avec le document

        Choix : le module du référentiel est porté en métadonnée dès
        l'extraction. Motivation : c'est gratuit ici, alors que le reconstituer
        après coup demanderait de déduire un module depuis une URL.
        """
        contenu = ExtracteurPythonDocs._extraire_texte(fragment)
        if len(contenu) < LONGUEUR_MINIMALE:
            return None

        chemin = urlparse(url).path.strip("/").replace("/", "_")
        chemin = re.sub(r"\.html$", "", chemin)
        return Enregistrement(
            identifiant=f"s6_{cible.cle}_{chemin}_{ancre or rang}",
            titre=titre or chemin,
            contenu=contenu,
            source_nom=cible.nom_source,
            source_type=self.type_source,
            source_url=f"{url}#{ancre}" if ancre else url,
            licence=cible.licence,
            langue="en",
            metadonnees={
                "cible": cible.cle,
                "module_referentiel": cible.module,
                "page": urlparse(url).path,
                "section_html": ancre,
                "copyright": cible.copyright,
            },
        )

    # --- 3. Gestion des erreurs : héritée de ExtracteurBase ---
    # --- 4. Sauvegarde des résultats : héritée de ExtracteurBase ---


# --- 5. Point de lancement ---

def main() -> None:
    """
    Point d'entrée du script, exécutable indépendamment du pipeline complet.

    Compétence visée : C1 (épreuve E1)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    bilan = ExtracteurDocumentationBibliotheques().executer()
    logger.info("Bilan : %s", bilan)


if __name__ == "__main__":
    main()
