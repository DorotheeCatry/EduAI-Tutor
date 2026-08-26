"""
Socle commun aux extracteurs de sources.

Compétence visée : C1 (épreuve E1) — automatisation de l'extraction de données

Le critère C1 exige que chaque script comprenne « un point de lancement,
l'initialisation des dépendances et des connexions externes, les règles
logiques de traitement, la gestion des erreurs et des exceptions, la fin du
traitement et la sauvegarde des résultats ».

Choix : une classe de base abstraite plutôt que cinq scripts entièrement
indépendants. Motivation : garantir que les cinq types de sources exposent la
même structure en cinq étapes, donc que le critère soit vérifiable de la même
manière sur chacun. L'abstraction s'arrête là — chaque extracteur garde son
fichier, son nom explicite et sa logique propre, pour que la couverture des
cinq types reste lisible.

Choix : sortie en JSON Lines plutôt qu'en CSV. Motivation : les sources
produisent des enregistrements de structures hétérogènes (un article scrapé
n'a pas les mêmes champs qu'une ligne SQL). JSONL accepte cette hétérogénéité
sans imposer de schéma prématuré, l'homogénéisation étant traitée en aval (C3).

Choix : chaque enregistrement porte ses métadonnées de provenance
(source, type, licence, date d'extraction). Motivation : la traçabilité des
données est exigée par C1 et par le RGPD (C4), et un corpus RAG sans provenance
ne permet pas de citer ses sources à l'utilisateur.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Racine de la couche « brute » : données telles qu'extraites, jamais modifiées.
# Choix : conserver le brut intact permet de rejouer les transformations (C3)
# sans relancer les extractions, qui sont lentes et parfois limitées en débit.
REPERTOIRE_BRUT = Path("data_pipeline/data/raw")


@dataclass
class Enregistrement:
    """
    Unité de données produite par un extracteur, quelle que soit la source.

    Compétence visée : C1 (épreuve E1)

    Choix : un contrat de données commun aux cinq sources, défini avant
    d'écrire les extracteurs. Sans lui, l'agrégation (C3) devient un travail de
    réconciliation manuelle entre cinq formats différents.
    """

    identifiant: str            # identifiant stable, sert à l'idempotence
    titre: str
    contenu: str
    source_nom: str             # ex. « Wikiversité »
    source_type: str            # api_rest | scraping | fichier | base_donnees | big_data
    source_url: str | None = None
    licence: str | None = None
    langue: str = "fr"
    extrait_le: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadonnees: dict[str, Any] = field(default_factory=dict)


class ExtracteurBase(ABC):
    """
    Classe de base imposant la structure en cinq étapes exigée par C1.

    Compétence visée : C1 (épreuve E1)

    Les sous-classes implémentent `initialiser`, `extraire` et `nettoyer`.
    La méthode `executer` orchestre les cinq étapes et n'a pas à être
    redéfinie : c'est elle qui garantit que le critère est satisfait de façon
    identique sur les cinq sources.
    """

    #: Nom lisible de la source, affiché dans les logs et le rapport.
    nom: str = "source_sans_nom"

    #: Type de source au sens du référentiel. L'un des cinq types exigés.
    type_source: str = "non_defini"

    #: Licence ou conditions d'utilisation. Documenté car C1 exige la
    #: consultation des règles de confidentialité et des contraintes de source.
    licence: str = "non documentée"

    def __init__(self, repertoire_sortie: Path | None = None) -> None:
        self.repertoire_sortie = repertoire_sortie or REPERTOIRE_BRUT
        self.fichier_sortie = self.repertoire_sortie / f"{self.nom}.jsonl"
        self.compteur_extraits = 0
        self.compteur_erreurs = 0

    # --- 1. Initialisation des dépendances et connexions externes ---

    @abstractmethod
    def initialiser(self) -> None:
        """
        Ouvre les connexions et vérifie les prérequis avant extraction.

        Compétence visée : C1 (épreuve E1)

        Doit échouer explicitement si un prérequis manque (clé API absente,
        base injoignable, fichier source introuvable). Échouer tôt et
        bruyamment vaut mieux qu'extraire un jeu de données partiel sans le
        savoir.
        """

    # --- 2. Règles logiques de traitement ---

    @abstractmethod
    def extraire(self) -> Iterator[Enregistrement]:
        """
        Produit les enregistrements un à un.

        Compétence visée : C1 (épreuve E1)

        Choix : un générateur plutôt qu'une liste. Motivation : la source big
        data peut dépasser la mémoire disponible (31 Go sur la machine de
        développement, mais rien ne le garantit ailleurs). Un générateur permet
        d'écrire au fil de l'eau.
        """

    # --- 3. Gestion des erreurs et exceptions ---

    def gerer_erreur(self, exception: Exception, contexte: str) -> bool:
        """
        Traite une erreur survenue pendant l'extraction d'un enregistrement.

        Compétence visée : C1 (épreuve E1)

        Choix : une erreur sur un enregistrement n'interrompt pas l'extraction
        complète, mais elle est comptée et journalisée. Motivation : sur des
        sources externes, quelques enregistrements malformés sont attendus ;
        perdre une extraction entière pour un cas isolé serait coûteux. En
        revanche un taux d'erreur élevé doit être visible dans le bilan final.

        Returns:
            True pour poursuivre l'extraction, False pour l'interrompre.
        """
        self.compteur_erreurs += 1
        logger.warning(
            "[%s] Erreur sur %s : %s — %s",
            self.nom, contexte, type(exception).__name__, exception,
        )
        # Interruption au-delà de 50 erreurs : le problème est systémique,
        # pas ponctuel (schéma changé, API en panne, sélecteur CSS obsolète).
        if self.compteur_erreurs > 50:
            logger.error("[%s] Trop d'erreurs, extraction interrompue.", self.nom)
            return False
        return True

    # --- 4. Sauvegarde des résultats ---

    def sauvegarder(self, enregistrements: Iterator[Enregistrement]) -> Path:
        """
        Écrit les enregistrements au format JSON Lines.

        Compétence visée : C1 (épreuve E1)

        Choix : écriture dans un fichier temporaire puis renommage atomique.
        Motivation : idempotence. Une extraction interrompue ne doit pas
        laisser un fichier partiel que le pipeline aval prendrait pour complet.
        """
        self.repertoire_sortie.mkdir(parents=True, exist_ok=True)
        fichier_temporaire = self.fichier_sortie.with_suffix(".jsonl.tmp")

        with fichier_temporaire.open("w", encoding="utf-8") as flux:
            for enregistrement in enregistrements:
                flux.write(
                    json.dumps(asdict(enregistrement), ensure_ascii=False) + "\n"
                )
                self.compteur_extraits += 1

        fichier_temporaire.replace(self.fichier_sortie)
        logger.info(
            "[%s] %d enregistrements écrits dans %s",
            self.nom, self.compteur_extraits, self.fichier_sortie,
        )
        return self.fichier_sortie

    def nettoyer(self) -> None:
        """
        Ferme les connexions ouvertes par `initialiser`.

        Compétence visée : C1 (épreuve E1)

        Implémentation par défaut vide : toutes les sources n'ouvrent pas de
        connexion persistante. Redéfinie par les extracteurs SQL et Spark.
        """

    # --- 5. Point de lancement ---

    def executer(self) -> dict[str, Any]:
        """
        Orchestre les cinq étapes et retourne un bilan d'exécution.

        Compétence visée : C1 (épreuve E1)

        Le bilan retourné alimente le rapport d'exécution du flux complet et
        sert de preuve chiffrée dans le rapport E1.
        """
        debut = datetime.now(timezone.utc)
        logger.info("[%s] Début de l'extraction (type : %s)", self.nom, self.type_source)

        statut = "succes"
        try:
            self.initialiser()
            self.sauvegarder(self._extraire_avec_gestion_erreurs())
        except Exception as exception:
            statut = "echec"
            logger.exception("[%s] Extraction échouée : %s", self.nom, exception)
            raise
        finally:
            self.nettoyer()

        duree = (datetime.now(timezone.utc) - debut).total_seconds()
        bilan = {
            "source": self.nom,
            "type_source": self.type_source,
            "licence": self.licence,
            "statut": statut,
            "enregistrements": self.compteur_extraits,
            "erreurs": self.compteur_erreurs,
            "duree_secondes": round(duree, 2),
            "fichier": str(self.fichier_sortie),
            "horodatage": debut.isoformat(),
        }
        logger.info("[%s] Terminé en %.2f s — %s", self.nom, duree, bilan)
        return bilan

    def _extraire_avec_gestion_erreurs(self) -> Iterator[Enregistrement]:
        """
        Enveloppe `extraire` pour appliquer la politique de gestion d'erreurs.

        Compétence visée : C1 (épreuve E1)
        """
        iterateur = self.extraire()
        while True:
            try:
                yield next(iterateur)
            except StopIteration:
                return
            except Exception as exception:
                if not self.gerer_erreur(exception, contexte="extraction"):
                    return
