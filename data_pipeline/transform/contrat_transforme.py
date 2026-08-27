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
