"""
Source 3 — Fichiers de données : corpus pédagogique local (data/contents/).

Compétence visée : C1 (épreuve E1) — extraction depuis des fichiers de données

Type de source : fichier (1 des 5 types exigés par le référentiel)
Licence du contenu : contenu produit par l'autrice du projet — droits détenus.
    Les fichiers tiers éventuels (cheat sheets récupérées) sont signalés par le
    manifeste de provenance, voir plus bas.
Formats traités : .md (Markdown), .pdf, .ipynb (notebooks Jupyter)

Choix : traiter le corpus existant comme une source d'extraction à part entière
plutôt que de le lire directement depuis l'application. Motivation : le
référentiel exige un flux de collecte automatisé et traçable. Un dossier lu au
fil de l'eau par l'application ne constitue pas une extraction documentée.

Choix : un manifeste de provenance (provenance.json) déclarant l'origine et la
licence de chaque fichier. Motivation : le corpus mélange du contenu produit
par l'autrice et des documents récupérés (cheat sheets). C1 exige de documenter
les contraintes de source ; sans manifeste, cette distinction est perdue.
Les fichiers non déclarés sont extraits avec la licence « non documentée »,
ce qui les rend visibles plutôt que silencieusement assimilés.

Choix : découpage des documents longs par titre de niveau 1 et 2 plutôt qu'un
enregistrement par fichier. Motivation : un cours complet dépasse la taille
utile d'un chunk RAG. Le découpage par titre suit la structure voulue par
l'auteur, comme pour la documentation Sphinx en S2.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator

from .base_extractor import Enregistrement, ExtracteurBase

logger = logging.getLogger(__name__)

REPERTOIRE_CORPUS = Path("data/contents")
FICHIER_PROVENANCE = REPERTOIRE_CORPUS / "provenance.json"

EXTENSIONS_TRAITEES = (".md", ".pdf", ".ipynb")

# En dessous de ce seuil, une section est un titre isolé ou un renvoi.
TAILLE_MINIMALE_CARACTERES = 200


class ExtracteurCorpusLocal(ExtracteurBase):
    """
    Extrait le corpus pédagogique local, découpé par section.

    Compétence visée : C1 (épreuve E1)

    Choix : le module d'origine (01_python, 02_data_analysis…) est conservé en
    métadonnée. Motivation : il permet un filtrage thématique du RAG au moment
    de la recherche, et il alimente la génération des index manquants —
    huit modules sur onze n'en ont pas aujourd'hui.
    """

    nom = "s3_corpus_local"
    type_source = "fichier"
    licence = "voir manifeste de provenance"

    def __init__(
        self,
        repertoire_corpus: Path = REPERTOIRE_CORPUS,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.repertoire_corpus = repertoire_corpus
        self.provenance: dict[str, dict[str, str]] = {}
        self.fichiers_a_traiter: list[Path] = []
        self.formats_manquants: set[str] = set()

    # --- 1. Initialisation des dépendances et connexions externes ---

    def initialiser(self) -> None:
        """
        Vérifie le corpus, charge le manifeste et recense les fichiers.

        Compétence visée : C1 (épreuve E1)

        Choix : le manifeste est optionnel mais son absence est journalisée en
        avertissement. Motivation : ne pas bloquer l'extraction, tout en
        rendant visible un manquement documentaire qui serait relevé au jury.
        """
        if not self.repertoire_corpus.exists():
            raise RuntimeError(
                f"Corpus introuvable : {self.repertoire_corpus.resolve()}. "
                "Vérifier le chemin depuis la racine du projet."
            )

        if FICHIER_PROVENANCE.exists():
            with FICHIER_PROVENANCE.open(encoding="utf-8") as flux:
                self.provenance = json.load(flux)
            logger.info(
                "[%s] Manifeste chargé : %d entrées", self.nom, len(self.provenance)
            )
        else:
            logger.warning(
                "[%s] Aucun manifeste (%s). Les licences seront « non documentée ».",
                self.nom, FICHIER_PROVENANCE,
            )

        self.fichiers_a_traiter = sorted(
            chemin
            for chemin in self.repertoire_corpus.rglob("*")
            if chemin.is_file() and chemin.suffix.lower() in EXTENSIONS_TRAITEES
        )

        # Vérification des dépendances de lecture, seulement si nécessaire.
        if any(f.suffix.lower() == ".pdf" for f in self.fichiers_a_traiter):
            try:
                import pypdf  # noqa: F401
            except ImportError:
                self.formats_manquants.add(".pdf")
                logger.warning(
                    "[%s] pypdf absent : les PDF seront ignorés. "
                    "Installer avec « uv add pypdf ».", self.nom,
                )

        logger.info(
            "[%s] %d fichiers recensés dans %s",
            self.nom, len(self.fichiers_a_traiter), self.repertoire_corpus,
        )

    # --- 2. Règles logiques de traitement ---

    def extraire(self) -> Iterator[Enregistrement]:
        """
        Parcourt les fichiers du corpus et produit un enregistrement par section.

        Compétence visée : C1 (épreuve E1)
        """
        for chemin in self.fichiers_a_traiter:
            extension = chemin.suffix.lower()
            if extension in self.formats_manquants:
                continue

            logger.debug("[%s] Lecture de %s", self.nom, chemin)

            if extension == ".md":
                texte = self._lire_markdown(chemin)
            elif extension == ".pdf":
                texte = self._lire_pdf(chemin)
            elif extension == ".ipynb":
                texte = self._lire_notebook(chemin)
            else:
                continue

            if not texte:
                logger.warning("[%s] Contenu vide : %s", self.nom, chemin)
                continue

            yield from self._decouper_en_sections(texte, chemin)

    @staticmethod
    def _lire_markdown(chemin: Path) -> str:
        """
        Lit un fichier Markdown.

        Compétence visée : C1 (épreuve E1)

        Choix : conserver le Markdown brut plutôt que le convertir en texte.
        Motivation : les titres et les blocs de code délimités structurent le
        découpage en sections et l'affichage ultérieur dans l'application.
        """
        return chemin.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _lire_pdf(chemin: Path) -> str:
        """
        Extrait le texte d'un PDF.

        Compétence visée : C1 (épreuve E1)

        Choix : extraction texte simple, sans OCR. Motivation : les cheat
        sheets du corpus sont des PDF générés, non scannés. Un PDF image
        produira un contenu vide, signalé en avertissement plutôt que traité
        par un OCR coûteux et imprécis.
        """
        from pypdf import PdfReader

        lecteur = PdfReader(str(chemin))
        pages = [page.extract_text() or "" for page in lecteur.pages]
        return "\n\n".join(pages).strip()

    @staticmethod
    def _lire_notebook(chemin: Path) -> str:
        """
        Convertit un notebook Jupyter en Markdown.

        Compétence visée : C1 (épreuve E1)

        Choix : conserver les cellules de code dans des blocs délimités et
        ignorer les sorties d'exécution. Motivation : les sorties (tableaux,
        traces d'erreur, images encodées) polluent le corpus RAG sans valeur
        pédagogique propre.
        """
        with chemin.open(encoding="utf-8") as flux:
            notebook = json.load(flux)

        morceaux: list[str] = []
        for cellule in notebook.get("cells", []):
            source = "".join(cellule.get("source", [])).strip()
            if not source:
                continue
            if cellule.get("cell_type") == "code":
                morceaux.append(f"```python\n{source}\n```")
            else:
                morceaux.append(source)

        return "\n\n".join(morceaux)

    def _decouper_en_sections(
        self, texte: str, chemin: Path
    ) -> Iterator[Enregistrement]:
        """
        Découpe un document par titre de niveau 1 ou 2.

        Compétence visée : C1 (épreuve E1)

        Choix : découpage sur les titres Markdown, en préservant les blocs de
        code. Un « # » à l'intérieur d'un bloc de code est un commentaire
        Python, pas un titre — le découpage doit l'ignorer, sans quoi les
        exemples de code sont coupés en deux.
        """
        module = self._identifier_module(chemin)
        licence, origine = self._resoudre_provenance(chemin)

        sections = self._separer_par_titres(texte)

        for index, (titre, contenu) in enumerate(sections):
            if len(contenu) < TAILLE_MINIMALE_CARACTERES:
                continue

            identifiant_relatif = chemin.relative_to(self.repertoire_corpus)
            identifiant = (
                f"corpus_{str(identifiant_relatif).replace('/', '_').replace('.', '_')}"
                f"_{index}"
            )

            yield Enregistrement(
                identifiant=identifiant,
                titre=titre or chemin.stem,
                contenu=contenu,
                source_nom="Corpus pédagogique EduAI Tutor",
                source_type=self.type_source,
                source_url=str(identifiant_relatif),
                licence=licence,
                langue="fr",
                metadonnees={
                    "module": module,
                    "fichier": str(identifiant_relatif),
                    "format": chemin.suffix.lower().lstrip("."),
                    "origine": origine,
                    "section_index": index,
                },
            )

    @staticmethod
    def _separer_par_titres(texte: str) -> list[tuple[str, str]]:
        """
        Sépare un texte Markdown en couples (titre, contenu).

        Compétence visée : C1 (épreuve E1)

        Les blocs de code sont neutralisés avant le découpage puis restaurés,
        pour qu'un commentaire Python commençant par « # » ne soit jamais
        interprété comme un titre.
        """
        blocs_code: list[str] = []

        def mettre_de_cote(correspondance: re.Match[str]) -> str:
            blocs_code.append(correspondance.group(0))
            return f"\x00BLOC{len(blocs_code) - 1}\x00"

        texte_neutralise = re.sub(r"```.*?```", mettre_de_cote, texte, flags=re.DOTALL)

        morceaux = re.split(r"^(#{1,2})\s+(.+)$", texte_neutralise, flags=re.MULTILINE)

        sections: list[tuple[str, str]] = []

        def restaurer(contenu: str) -> str:
            for index, bloc in enumerate(blocs_code):
                contenu = contenu.replace(f"\x00BLOC{index}\x00", bloc)
            return contenu.strip()

        # Le premier morceau est le contenu précédant tout titre.
        preambule = restaurer(morceaux[0])
        if preambule:
            sections.append(("", preambule))

        # Les morceaux suivants vont par trois : niveau, titre, contenu.
        for position in range(1, len(morceaux), 3):
            titre = morceaux[position + 1].strip()
            contenu_brut = morceaux[position + 2] if position + 2 < len(morceaux) else ""
            contenu = restaurer(f"{titre}\n\n{contenu_brut}")
            sections.append((titre, contenu))

        return sections

    def _identifier_module(self, chemin: Path) -> str:
        """
        Déduit le module pédagogique à partir de l'arborescence.

        Compétence visée : C1 (épreuve E1)
        """
        parties = chemin.relative_to(self.repertoire_corpus).parts
        for partie in parties:
            if re.match(r"^\d{2}_", partie):
                return partie
        return parties[0] if len(parties) > 1 else "non_classe"

    def _resoudre_provenance(self, chemin: Path) -> tuple[str, str]:
        """
        Retourne la licence et l'origine déclarées pour un fichier.

        Compétence visée : C1 (épreuve E1)

        Returns:
            Un couple (licence, origine). Valeurs par défaut explicites
            lorsqu'aucune déclaration n'existe, pour que le manque soit visible
            dans les données plutôt que masqué.
        """
        cle = str(chemin.relative_to(self.repertoire_corpus))
        entree = self.provenance.get(cle, {})
        return (
            entree.get("licence", "non documentée"),
            entree.get("origine", "non déclarée"),
        )

    # --- 3. Gestion des erreurs : héritée de ExtracteurBase ---
    # --- 4. Sauvegarde : héritée de ExtracteurBase ---

    def nettoyer(self) -> None:
        """
        Journalise le bilan de lecture.

        Compétence visée : C1 (épreuve E1)
        """
        if self.formats_manquants:
            logger.warning(
                "[%s] Formats ignorés faute de dépendance : %s",
                self.nom, ", ".join(sorted(self.formats_manquants)),
            )


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
    bilan = ExtracteurCorpusLocal().executer()
    logger.info("Bilan : %s", bilan)


if __name__ == "__main__":
    main()
