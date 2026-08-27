"""
Source 2 — Scraping : documentation officielle Python (docs.python.org).

Compétence visée : C1 (épreuve E1) — extraction par scraping

Type de source : scraping (1 des 5 types exigés par le référentiel)
Licence du contenu : PSF License Agreement — redistribution autorisée avec
    conservation de la notice de copyright. Copyright (c) 2001-2026 Python
    Software Foundation. Voir https://docs.python.org/3/license.html
Robots.txt : https://docs.python.org/robots.txt — vérifié à l'exécution par
    urllib.robotparser, et non par lecture manuelle. Le respect du robots.txt
    est donc une contrainte appliquée par le code, pas une déclaration.

Choix : docs.python.org plutôt qu'un site de tutoriels. Motivation triple —
la licence PSF autorise explicitement la redistribution (beaucoup de sites de
tutoriels l'interdisent dans leurs CGU), le contenu fait autorité, et il couvre
directement le module 01_python du corpus existant.

Choix : scraping limité aux sections tutorial/ et library/ plutôt qu'au site
entier. Motivation : la référence du langage (reference/) et les notes de
version (whatsnew/) sont trop techniques pour des apprenants et dilueraient la
pertinence du RAG.

Choix : pause de 2 secondes entre requêtes, supérieure au strict nécessaire.
Motivation : C1 exige le respect des contraintes de la source. docs.python.org
est un service gratuit financé par une fondation ; le charger pour gagner
quelques minutes serait indéfendable devant un jury comme en pratique.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .base_extractor import Enregistrement, ExtracteurBase

logger = logging.getLogger(__name__)

URL_BASE = "https://docs.python.org/3/"
URL_ROBOTS = "https://docs.python.org/robots.txt"

USER_AGENT = "EduAI-Tutor/1.0 (projet pedagogique RNCP 37827)"

# Pages de départ. Le tutoriel couvre les fondamentaux, les pages de
# bibliothèque couvrent les modules effectivement utilisés dans le corpus.
PAGES_DEPART = (
    "tutorial/introduction.html",
    "tutorial/controlflow.html",
    "tutorial/datastructures.html",
    "tutorial/modules.html",
    "tutorial/inputoutput.html",
    "tutorial/errors.html",
    "tutorial/classes.html",
    "library/stdtypes.html",
    "library/functions.html",
    "library/datetime.html",
    "library/json.html",
    "library/csv.html",
    "library/pathlib.html",
    "library/re.html",
    "library/collections.html",
    "library/itertools.html",
)

PAUSE_ENTRE_REQUETES_SECONDES = 2.0
DELAI_EXPIRATION_SECONDES = 30


class ExtracteurPythonDocs(ExtracteurBase):
    """
    Extrait les sections de la documentation Python officielle.

    Compétence visée : C1 (épreuve E1)

    Choix : découpage par section (balises <section> du HTML généré par Sphinx)
    plutôt qu'une page entière par enregistrement. Motivation : une page de
    documentation peut dépasser 50 000 caractères, ce qui produirait des chunks
    RAG incohérents. Une section correspond à une unité de sens — c'est le
    découpage que l'auteur a lui-même choisi.
    """

    nom = "s2_python_docs"
    type_source = "scraping"
    licence = "PSF License Agreement"
    code_source = "s2"

    def __init__(self, pages: tuple[str, ...] = PAGES_DEPART, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pages = pages
        self.session: requests.Session | None = None
        self.robots: RobotFileParser | None = None
        self.pages_visitees: set[str] = set()

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Ouvre la session HTTP et charge le robots.txt de la source.

        Compétence visée : C1 (épreuve E1)

        Choix : échouer si le robots.txt est inaccessible, plutôt que de
        supposer l'autorisation. Motivation : en cas de doute sur les
        conditions d'accès, ne pas scraper est la seule position défendable.
        """
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.robots = RobotFileParser()
        self.robots.set_url(URL_ROBOTS)
        try:
            self.robots.read()
        except Exception as exception:
            raise RuntimeError(
                f"robots.txt inaccessible ({URL_ROBOTS}) : {exception}. "
                "Extraction annulée — les conditions d'accès ne peuvent être vérifiées."
            ) from exception

        logger.info("[%s] robots.txt chargé depuis %s", self.nom, URL_ROBOTS)

        # Vérification que la première page est autorisée avant de commencer.
        premiere_url = urljoin(URL_BASE, self.pages[0])
        if not self._est_autorise(premiere_url):
            raise RuntimeError(
                f"Le robots.txt interdit l'accès à {premiere_url}. Extraction annulée."
            )

    def _est_autorise(self, url: str) -> bool:
        """
        Indique si le robots.txt autorise l'accès à une URL pour notre agent.

        Compétence visée : C1 (épreuve E1)
        """
        if self.robots is None:
            return False
        return self.robots.can_fetch(USER_AGENT, url)

    # --- 2. Règles logiques de traitement ---

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Parcourt les pages de départ et produit un enregistrement par section.

        Compétence visée : C1 (épreuve E1)
        """
        for chemin_page in self.pages:
            url = urljoin(URL_BASE, chemin_page)

            if url in self.pages_visitees:
                continue
            self.pages_visitees.add(url)

            if not self._est_autorise(url):
                logger.warning("[%s] robots.txt interdit %s — page ignorée", self.nom, url)
                continue

            time.sleep(PAUSE_ENTRE_REQUETES_SECONDES)
            logger.info("[%s] Récupération de %s", self.nom, url)
            yield from self._extraire_page(url)

    def _extraire_page(self, url: str) -> Iterator[Enregistrement]:
        """
        Télécharge une page et produit un enregistrement par section.

        Compétence visée : C1 (épreuve E1)
        """
        assert self.session is not None

        reponse = self.session.get(url, timeout=DELAI_EXPIRATION_SECONDES)
        reponse.raise_for_status()
        reponse.encoding = "utf-8"

        soupe = BeautifulSoup(reponse.text, "html.parser")
        corps = soupe.find("div", class_="body") or soupe.find("main") or soupe

        sections = corps.find_all("section")
        if not sections:
            logger.warning("[%s] Aucune section trouvée sur %s", self.nom, url)
            return

        for section in sections:
            enregistrement = self._convertir_section(section, url)
            if enregistrement is not None:
                yield enregistrement

    def _convertir_section(self, section: Any, url_page: str) -> Enregistrement | None:
        """
        Transforme une balise <section> en Enregistrement du contrat commun.

        Compétence visée : C1 (épreuve E1)

        Choix : ignorer les sections de moins de 200 caractères. Motivation :
        les sections très courtes de la documentation Sphinx sont des sommaires
        ou des renvois, sans contenu propre exploitable par le RAG.

        Returns:
            None si la section est inexploitable.
        """
        titre_balise = section.find(["h1", "h2", "h3"], recursive=False)
        titre = titre_balise.get_text(strip=True).rstrip("¶") if titre_balise else ""

        contenu = self._extraire_texte(section)
        if len(contenu) < 200:
            return None

        identifiant_section = section.get("id", "")
        url_section = f"{url_page}#{identifiant_section}" if identifiant_section else url_page

        chemin = urlparse(url_page).path
        return Enregistrement(
            identifiant=f"pydoc_{chemin.strip('/').replace('/', '_')}_{identifiant_section}",
            titre=titre or chemin,
            contenu=contenu,
            source_nom="Documentation Python officielle",
            source_type=self.type_source,
            source_url=url_section,
            licence=self.licence,
            langue="en",
            metadonnees={
                "section_html": identifiant_section,
                "page": chemin,
                "copyright": "Copyright (c) 2001-2026 Python Software Foundation",
            },
        )

    @staticmethod
    def _extraire_texte(section: Any) -> str:
        """
        Convertit une section HTML en texte, en préservant les blocs de code.

        Compétence visée : C1 (épreuve E1)

        Choix : normaliser les espaces du texte courant mais jamais ceux des
        blocs de code. Motivation : l'indentation est syntaxique en Python.
        Une normalisation appliquée globalement produirait du code
        syntaxiquement invalide dans le corpus — l'erreur exacte identifiée et
        corrigée sur l'extracteur S1 (voir docs/decisions/003).

        Les blocs sont donc mis de côté, le texte est normalisé, puis les blocs
        sont réinsérés intacts.
        """
        # Copie de travail : on ne modifie pas l'arbre d'origine.
        section_copie = BeautifulSoup(str(section), "html.parser")

        # Retrait des sous-sections imbriquées. Sphinx emboîte les <section>,
        # et `find_all("section")` renvoie aussi bien la section mère que ses
        # filles : sans ce retrait, le texte d'une sous-section est extrait
        # deux fois — une fois seul, une fois dans le contenu de sa mère.
        # Mesuré sur tutorial/errors.html : 44 741 caractères produits pour une
        # page qui en compte 22 503, soit exactement le double. Chaque section
        # ne conserve donc que son contenu propre.
        while True:
            sections_du_document = section_copie.find_all("section")
            if len(sections_du_document) <= 1:
                break
            sections_du_document[1].decompose()

        # Retrait des éléments de navigation propres à Sphinx.
        for indesirable in section_copie.find_all(
            ["nav"], class_=["headerlink", "sphinxsidebar"]
        ):
            indesirable.decompose()
        for lien_ancre in section_copie.find_all("a", class_="headerlink"):
            lien_ancre.decompose()

        blocs_code: list[str] = []

        def remplacer_par_marqueur(balise: Any) -> None:
            """Remplace un bloc de code par un marqueur unique et le met de côté."""
            code = balise.get_text()
            blocs_code.append(code)
            balise.replace_with(f"\x00BLOC{len(blocs_code) - 1}\x00")

        for bloc in section_copie.find_all(["pre"]):
            remplacer_par_marqueur(bloc)

        texte = section_copie.get_text(separator="\n")

        # Normalisation — s'applique uniquement au texte courant, les blocs
        # de code étant à ce stade remplacés par des marqueurs.
        texte = re.sub(r"[ \t]+", " ", texte)
        texte = re.sub(r"\n{3,}", "\n\n", texte)
        texte = texte.strip()

        # Réinsertion des blocs de code, indentation intacte.
        for index, code in enumerate(blocs_code):
            texte = texte.replace(
                f"\x00BLOC{index}\x00", f"\n```python\n{code.strip()}\n```\n"
            )

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
        logger.info("[%s] %d pages visitées", self.nom, len(self.pages_visitees))


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
    bilan = ExtracteurPythonDocs().executer()
    logger.info("Bilan : %s", bilan)


if __name__ == "__main__":
    main()
