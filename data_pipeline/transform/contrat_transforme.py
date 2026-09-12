"""
Contrat de sortie de la couche de transformation.

Compétence visée : C3 (épreuve E1)

Choix : un contrat explicite entre la transformation et le chargement, comme
`Enregistrement` en est un entre l'extraction et la transformation. Motivation :
le chargeur écrit dans une base contrainte — clés étrangères vers les
nomenclatures `type_source` et `licence`, colonnes non nulles. Sans contrat, il
découvrirait les écarts au moment de l'insertion, une ligne à la fois.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentTransforme:
    """
    Document normalisé, prêt pour le chargement dans `eduai_data`.

    Compétence visée : C3 (épreuve E1)

    Choix : séparer `mots_cles` et `metriques` du reste des métadonnées.
    Motivation : ces deux ensembles ont une destination propre dans le schéma
    physique — la table des mots-clés d'un côté, des colonnes typées de
    l'autre. Les laisser noyés dans un dictionnaire fourre-tout obligerait le
    chargeur à les en extraire, donc à connaître la structure interne de
    chaque source. C'est précisément ce que cette couche doit lui épargner.
    """

    identifiant: str
    titre: str
    contenu: str

    #: Code de la nomenclature `type_source` : api_rest, scraping, fichier,
    #: base_donnees, big_data.
    code_type_source: str

    #: Code de l'EXTRACTEUR (`s1` … `s6`), tiré du nom du fichier brut.
    #:
    #: Il ne fait pas double emploi avec `code_type_source`. Le chargeur
    #: rattachait un document à sa source par son type, ce qui supposait une
    #: source par type ; la sixième source est un second scraping, deux sources
    #: partagent donc le type et le rattachement devenait ambigu (incident du
    #: 02/09/2026). Ce champ manquait à ce contrat, qui a dérivé de la
    #: transformation réelle sans que rien ne le dise — c'est précisément ce
    #: que `depuis_dict` empêche désormais.
    code_source: str

    source_nom: str
    source_url: str | None

    #: Code de la nomenclature `licence`, ou None si la licence déclarée n'a
    #: pas de correspondance. Le chargement tranchera ; la transformation
    #: signale sans écraser.
    code_licence: str | None
    licence_declaree: str

    langue: str

    #: ISO 8601 avec fuseau, UTC. Toujours renseigné.
    extrait_le: str

    #: ISO 8601 avec fuseau, UTC. None si la source ne le fournit pas.
    cree_le: str | None

    mots_cles: list[str] = field(default_factory=list)
    metriques: dict[str, Any] = field(default_factory=dict)
    metadonnees: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def depuis_dict(cls, document: dict[str, Any]) -> "DocumentTransforme":
        """
        Vérifie qu'un document transformé respecte ce contrat, et le construit.

        Compétence visée : C3 (épreuve E1), C4 (E1)

        Choix : une vérification au passage plutôt qu'un contrat déclaratif.
        **Motivation constatée.** Ce contrat était écrit, documenté, présenté en
        en-tête comme « le contrat de sortie de la couche de transformation » —
        et importé par personne. `transformer.py` manipulait des dictionnaires,
        `chargeur.py` aussi. Le contrat n'était donc pas un contrat : c'était un
        commentaire dans un fichier à part.

        Il avait d'ailleurs déjà dérivé. Le champ `code_source`, ajouté au
        corpus réel lors de l'arrivée de la sixième source, n'y figurait pas.
        Personne ne pouvait le voir, puisque rien ne comparait les deux.

        Choix : lever plutôt que journaliser. Motivation : le chargeur écrit
        dans une base contrainte — clés étrangères vers les nomenclatures,
        colonnes non nulles. Un corpus qui ne respecte pas ce contrat le fera
        échouer une ligne à la fois, à l'insertion, après avoir déjà écrit les
        précédentes. Mieux vaut s'arrêter avant d'écrire le fichier.

        Raises:
            TypeError: un champ obligatoire manque, ou un champ inconnu est
                présent — les deux signalent une dérive entre les deux couches.
        """
        return cls(**document)
