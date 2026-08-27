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

    #: Code de la source dans `eduai_data` : s1 à s5. Sert à rattacher le
    #: bilan d'exécution à la table `extraction`.
    #:
    #: Choix : un attribut explicite plutôt qu'une déduction depuis `nom`.
    #: Motivation : renommer un extracteur ne doit pas déplacer silencieusement
    #: ses exécutions passées sous une autre source.
    code_source: str = ""

    #: Une extraction sans aucun enregistrement est-elle un état légitime ?
    #:
    #: Compétence visée : C21 (épreuve E5)
    #:
    #: Choix : la réponse dépend de la source, pas du socle. Motivation : une
    #: API qui ne renvoie rien signale une panne, une clé expirée ou un filtre
    #: inadapté — c'est exactement l'incident qu'a connu S1 le 26/08, dont le
    #: bilan annonçait « succes, 0 enregistrement ». Une base applicative sans
    #: production d'apprenant, elle, est simplement une base neuve. Par défaut
    #: le vide est traité comme un échec : c'est le cas le plus fréquent et le
    #: plus dangereux, et une source qui fait exception doit le déclarer.
    zero_est_valide: bool = False

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
                ligne = json.dumps(asdict(enregistrement), ensure_ascii=False)
                flux.write(self._neutraliser_separateurs(ligne) + "\n")
                self.compteur_extraits += 1

        # Une extraction stérile ne doit pas détruire la précédente.
        #
        # Compétence visée : C21 (épreuve E5)
        #
        # Le renommage atomique protège d'une écriture interrompue, pas d'une
        # exécution qui se termine normalement en ne produisant rien. Or c'est
        # l'état qu'a connu S1 le 26/08 : un filtre d'API inadapté, zéro
        # enregistrement, et une sortie valide remplacée par un fichier vide.
        # La perte serait passée inaperçue, le fichier existant toujours.
        #
        # La protection ne s'applique pas aux sources qui déclarent le vide
        # légitime : pour S4, une base applicative dont toutes les productions
        # ont dépassé la fenêtre de conservation doit bel et bien produire une
        # sortie vide, et la figer serait un autre mensonge.
        precedente_non_vide = (
            self.fichier_sortie.is_file() and self.fichier_sortie.stat().st_size > 0
        )
        if self.compteur_extraits == 0 and precedente_non_vide and not self.zero_est_valide:
            fichier_temporaire.unlink()
            logger.error(
                "[%s] Aucun enregistrement produit alors qu'une sortie "
                "précédente existe : %s est CONSERVÉ et n'a pas été écrasé. "
                "Traiter la cause avant de relancer — le corpus n'a pas été "
                "modifié.",
                self.nom, self.fichier_sortie,
            )
            return self.fichier_sortie

        fichier_temporaire.replace(self.fichier_sortie)
        logger.info(
            "[%s] %d enregistrements écrits dans %s",
            self.nom, self.compteur_extraits, self.fichier_sortie,
        )
        return self.fichier_sortie

    @staticmethod
    def _neutraliser_separateurs(ligne: str) -> str:
        """
        Échappe les caractères que JSON accepte mais qui coupent une ligne.

        Compétence visée : C1 (épreuve E1)

        Choix : échapper U+2028, U+2029 et U+0085 alors que `json.dumps` les
        laisse tels quels. Motivation : le format JSON Lines repose sur
        l'équivalence « une ligne = un enregistrement ». Or ces trois
        caractères sont des séparateurs de ligne Unicode : `str.splitlines()`
        en Python, `JSON.parse` en JavaScript avant ES2019 et plusieurs
        lecteurs de flux coupent dessus, ce qui scinde un enregistrement en
        deux fragments illisibles.

        Le cas n'est pas théorique : l'extraction des PDF du corpus (S3) a
        produit 331 occurrences d'U+2028, pour 380 enregistrements. Sans cet
        échappement, un fichier de 380 lignes en compte 711 selon la
        définition retenue par le lecteur. Le contrat de sortie doit tenir
        quelle que soit la manière dont l'aval découpe les lignes.

        Les autres caractères de contrôle (U+000B, U+000C, U+001C à U+001F)
        n'ont pas besoin de ce traitement : `json.dumps` les échappe déjà,
        comme tout caractère inférieur à U+0020.
        """
        return (
            ligne.replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
            .replace("\u0085", "\\u0085")
        )

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

        # Une extraction qui ne produit rien n'est pas un succès par défaut.
        #
        # Compétence visée : C21 (épreuve E5)
        #
        # Le socle ne rendait jusqu'ici que « succes » ou « echec », et « aucune
        # exception levée » valait succès. C'est ce raisonnement qui a produit
        # le bilan « succes, 0 enregistrement » de S1 le 26/08 : un filtre d'API
        # inadapté ne ramenait rien, aucune étape n'échouait, le programme
        # concluait à la réussite. Il rendait compte de son intention, pas de
        # son effet.
        if statut == "succes" and self.compteur_extraits == 0:
            if self.zero_est_valide:
                statut = "vide"
                logger.info(
                    "[%s] Aucun enregistrement, et cette source déclare le vide "
                    "comme état légitime : statut « vide ».", self.nom,
                )
            else:
                statut = "echec"
                logger.error(
                    "[%s] Aucun enregistrement produit alors que cette source "
                    "devrait en fournir. Statut « echec » : une extraction ne "
                    "réussit pas en ne produisant rien. Pistes : filtre ou "
                    "requête inadaptés, quota atteint, source indisponible.",
                    self.nom,
                )

        duree = (datetime.now(timezone.utc) - debut).total_seconds()
        bilan = {
            "source": self.nom,
            "code_source": self.code_source,
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
        self.ecrire_bilan(bilan)
        return bilan

    def ecrire_bilan(self, bilan: dict[str, Any]) -> Path:
        """
        Persiste le bilan d'exécution à côté du fichier de sortie.

        Compétence visée : C1 (épreuve E1) — traçabilité de l'extraction
        Compétence visée : C4 (épreuve E1) — alimentation de la table extraction

        Choix : un fichier de bilan par extracteur, écrit systématiquement.
        Motivation : la table `extraction` de `eduai_data` porte la traçabilité
        des campagnes — durée, statut, volumétrie, nombre d'erreurs. Le chargeur
        ne peut pas la reconstituer depuis le corpus : il verrait le nombre de
        documents, mais ni la durée réelle, ni les erreurs rencontrées, ni les
        enregistrements écartés en chemin. Les inventer serait fabriquer une
        mesure. Le seul qui les connaisse est l'extracteur lui-même, au moment
        où il termine.

        Choix : un fichier distinct du JSONL plutôt qu'un en-tête dans celui-ci.
        Motivation : le format JSON Lines repose sur l'équivalence « une ligne =
        un enregistrement ». Y glisser une ligne de métadonnées la romprait, et
        tout lecteur du corpus devrait connaître l'exception.
        """
        chemin = self.repertoire_sortie / f"{self.nom}.bilan.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(bilan, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("[%s] Bilan écrit dans %s", self.nom, chemin)
        return chemin

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
