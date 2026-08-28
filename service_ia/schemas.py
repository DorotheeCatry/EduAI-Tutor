"""
Contrats d'entrée et de sortie de l'API du service IA.

Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA

Choix : une validation Pydantic en entrée ET en sortie. Motivation : valider
l'entrée protège le service ; valider la sortie protège le client. Un agent
appelle un modèle de langage, dont la réponse n'est pas garantie — un JSON
tronqué, un champ absent, une liste vide. Sans contrat de sortie, ces cas
traversent l'API et deviennent l'erreur du consommateur, loin de leur cause.

Choix : des bornes explicites sur toutes les chaînes libres. Motivation : ces
champs alimentent un prompt facturé au jeton. Une requête de dix mégaoctets
n'est pas une erreur de saisie, c'est une attaque bon marché — OWASP API4,
« Unrestricted Resource Consumption ».
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

#: Longueur maximale d'un sujet ou d'une question.
#:
#: Cinq cents caractères : au-delà, ce n'est plus une question mais un document,
#: et le service n'est pas fait pour résumer des documents fournis par l'appelant.
LONGUEUR_SUJET_MAX = 500

#: Longueur maximale d'un extrait de code soumis pour retour.
#:
#: Vingt mille caractères, soit environ six cents lignes. Un exercice de
#: formation n'atteint pas cette taille ; au-delà, l'appelant soumet un projet.
LONGUEUR_CODE_MAX = 20_000


class Difficulte(str, Enum):
    """
    Niveaux de difficulté reconnus.

    Compétence visée : C9 (épreuve E2)

    Choix : une énumération plutôt qu'une chaîne libre. Motivation : les valeurs
    acceptées apparaissent dans la documentation OpenAPI, et une valeur inconnue
    est refusée avec un message utile au lieu d'atteindre le prompt et de
    produire un cours au niveau imprévisible.
    """

    DEBUTANT = "debutant"
    INTERMEDIAIRE = "intermediaire"
    AVANCE = "avance"


class Langue(str, Enum):
    """Langues de rédaction proposées."""

    FR = "fr"
    EN = "en"


# --- Entrées ---

class DemandeCours(BaseModel):
    """
    Demande de génération d'un cours.

    Compétence visée : C9 (épreuve E2)
    """

    sujet: str = Field(
        ..., min_length=3, max_length=LONGUEUR_SUJET_MAX,
        description="Sujet du cours à produire.",
        examples=["les décorateurs en Python"],
    )
    difficulte: Difficulte = Field(
        default=Difficulte.INTERMEDIAIRE,
        description="Niveau visé. Détermine la profondeur et le vocabulaire.",
    )
    langue: Langue = Field(default=Langue.FR, description="Langue de rédaction.")

    @field_validator("sujet")
    @classmethod
    def sujet_non_vide(cls, valeur: str) -> str:
        """
        Refuse un sujet composé uniquement d'espaces.

        Compétence visée : C9 (épreuve E2)

        `min_length` compte les caractères, espaces compris : « ␣␣␣ » passe la
        contrainte de longueur et produit un prompt vide. Le contrôle porte donc
        sur la chaîne nettoyée.
        """
        nettoye = valeur.strip()
        if len(nettoye) < 3:
            raise ValueError("Le sujet doit comporter au moins trois caractères utiles.")
        return nettoye


class DemandeExplication(BaseModel):
    """
    Demande de réexplication adaptée d'une notion, servie par le Pédagogue.

    Compétence visée : C9 (épreuve E2)
    """

    notion: str = Field(
        ..., min_length=3, max_length=LONGUEUR_SUJET_MAX,
        description="Notion à réexpliquer.",
        examples=["la différence entre une liste et un tuple"],
    )
    niveau_apprenant: Difficulte = Field(
        default=Difficulte.DEBUTANT,
        description=(
            "Niveau de l'apprenant, non du contenu. C'est lui qui décide de "
            "l'angle de la réexplication."
        ),
    )
    langue: Langue = Field(default=Langue.FR)

    @field_validator("notion")
    @classmethod
    def notion_non_vide(cls, valeur: str) -> str:
        nettoye = valeur.strip()
        if len(nettoye) < 3:
            raise ValueError("La notion doit comporter au moins trois caractères utiles.")
        return nettoye


class DemandeExercice(BaseModel):
    """
    Demande de génération d'un exercice de code.

    Compétence visée : C9 (épreuve E2)
    """

    sujet: str = Field(..., min_length=3, max_length=LONGUEUR_SUJET_MAX)
    difficulte: Difficulte = Field(default=Difficulte.INTERMEDIAIRE)
    nombre_questions: int = Field(
        default=1, ge=1, le=10,
        description=(
            "Nombre d'exercices demandés. Plafonné à dix : chaque unité est un "
            "appel facturé au fournisseur."
        ),
    )


class DemandeFeedback(BaseModel):
    """
    Demande de retour sur une soumission de code, servie par le Coach.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C4 (épreuve E1) — minimisation

    Choix : aucun identifiant d'apprenant dans ce contrat. Motivation : le
    retour porte sur du code, pas sur une personne. Le service n'a pas besoin
    de savoir qui a écrit la soumission pour la corriger, et ce qu'il ne reçoit
    pas ne peut ni fuiter ni être conservé par erreur.
    """

    enonce: str = Field(
        ..., min_length=3, max_length=LONGUEUR_SUJET_MAX,
        description="Énoncé de l'exercice auquel le code répond.",
    )
    code_soumis: str = Field(
        ..., min_length=1, max_length=LONGUEUR_CODE_MAX,
        description="Code de l'apprenant, tel que soumis.",
    )
    message_erreur: str | None = Field(
        default=None, max_length=4000,
        description="Message d'erreur obtenu à l'exécution, s'il y en a un.",
    )
    langue: Langue = Field(default=Langue.FR)


class DemandeRecherche(BaseModel):
    """
    Recherche dans le corpus, sans génération.

    Compétence visée : C9 (épreuve E2)

    Choix : un point de terminaison de recherche seule, distinct des points de
    génération. Motivation : il permet de vérifier ce que le RAG remonte
    indépendamment de ce que le modèle en fait. Quand une réponse est mauvaise,
    c'est la première question à trancher — mauvais contexte, ou mauvaise
    synthèse ? Sans ce point de terminaison, les deux causes se confondent.
    """

    requete: str = Field(
        ..., min_length=2, max_length=LONGUEUR_SUJET_MAX,
        description="Texte recherché dans le corpus.",
    )
    nombre_fragments: int = Field(
        default=5, ge=1, le=20,
        description="Nombre de fragments demandés. Le nombre RENDU peut être inférieur.",
    )


# --- Sorties ---

class FragmentRAG(BaseModel):
    """
    Un fragment du corpus remonté par la recherche.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C4 (épreuve E1) — traçabilité des sources
    """

    extrait: str = Field(description="Contenu du fragment.")
    source: str | None = Field(
        default=None,
        description=(
            "Provenance déclarée du fragment. Un tuteur qui cite doit pouvoir "
            "renvoyer vers l'origine — plusieurs licences du corpus l'exigent."
        ),
    )
    metadonnees: dict[str, Any] = Field(default_factory=dict)


class ReponseRecherche(BaseModel):
    """
    Résultat d'une recherche dans le corpus.

    Compétence visée : C9 (épreuve E2)
    """

    requete: str
    fragments_demandes: int = Field(
        description="Nombre demandé par l'appelant — une intention.",
    )
    fragments_rendus: int = Field(
        description=(
            "Nombre réellement rendu — un effet. L'écart avec le nombre demandé "
            "signale un corpus trop pauvre sur le sujet, et il est visible "
            "plutôt que déduit."
        ),
    )
    fragments: list[FragmentRAG]
    latence_secondes: float


class ReponseGeneration(BaseModel):
    """
    Réponse d'un point de terminaison de génération.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C20 (épreuve E5)

    Choix : la réponse porte le modèle utilisé et la latence. Motivation : le
    routage par agent peut changer sans que le consommateur en soit informé. Un
    client qui constate une dégradation doit pouvoir dire lequel des quatre
    modèles a produit la réponse, sans accès aux journaux du service.
    """

    agent: str = Field(description="Agent ayant produit la réponse.")
    modele: str = Field(description="Modèle effectivement appelé.")
    contenu: str = Field(min_length=1, description="Texte produit.")
    fragments_utilises: int = Field(
        default=0,
        description="Fragments du corpus versés au contexte. Zéro signifie sans RAG.",
    )
    latence_secondes: float
    tronquee: bool = Field(
        default=False,
        description=(
            "Vrai si la réponse du modèle semble incomplète. Un JSON non "
            "refermé ou une phrase coupée signalent une limite de jetons "
            "atteinte, non une erreur du service."
        ),
    )


class EtatFournisseur(BaseModel):
    """État d'un fournisseur de modèles."""

    nom: str
    configure: bool = Field(description="Une clé ou une adresse est renseignée.")
    detail: str


class ReponseSante(BaseModel):
    """
    État du service, tel qu'il peut être constaté sans appeler le fournisseur.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C20 (épreuve E5)

    Choix : la sonde de santé n'appelle PAS le fournisseur. Motivation : un
    appel réel serait facturé, et une sonde interrogée toutes les quinze
    secondes par un orchestrateur coûterait plus que le service lui-même. Elle
    constate ce qui est vérifiable localement — configuration, corpus, sonde de
    monitorage — et renvoie vers les métriques pour le reste.

    Le champ `disponibilite_fournisseur` est donc explicitement déclaratif : il
    dit si le fournisseur est configuré, pas s'il répond. Prétendre le contraire
    reproduirait le motif des incidents du projet — un rapport de succès qui ne
    correspond à rien.
    """

    statut: str = Field(description="operationnel, degrade ou indisponible.")
    version_api: str
    agents_disponibles: list[str]
    routage_modeles: dict[str, str] = Field(
        description="Modèle affecté à chaque agent, tel que résolu maintenant.",
    )
    disponibilite_fournisseur: list[EtatFournisseur] = Field(
        description=(
            "Configuration constatée localement, PAS un appel de vérification. "
            "L'état réel du fournisseur se lit dans les métriques, où les codes "
            "de retour des appels effectifs sont comptés."
        ),
    )
    corpus_rag: dict[str, Any]
    monitorage: dict[str, Any]


class ErreurAPI(BaseModel):
    """
    Corps d'erreur uniforme.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C13 (épreuve E3) — OWASP API

    Choix : un message stable et un identifiant de corrélation, jamais la trace
    de l'exception. Motivation : une trace renvoyée au client expose les chemins
    du serveur, les versions des bibliothèques et parfois des valeurs de
    configuration. L'identifiant permet de retrouver la trace complète dans le
    journal de monitorage, où elle est conservée.
    """

    detail: str = Field(description="Message destiné à l'appelant.")
    code: str = Field(description="Code stable, exploitable par un programme.")
    identifiant_incident: str | None = Field(
        default=None,
        description="À citer pour retrouver la trace complète dans le journal.",
    )
