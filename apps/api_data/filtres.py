"""
Filtres et recherche de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données
Compétence visée : C2 (épreuve E1) — requête de recherche optimisée
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchQuery, SearchVector
from django_filters import rest_framework as filtres
from rest_framework.filters import BaseFilterBackend

from .models import Document

#: Configuration de recherche PostgreSQL.
#:
#: « simple » ne racinise pas. Le corpus étant bilingue — environ 6 500
#: documents anglais et 380 français — une configuration à racinisation ne
#: vaudrait que pour la langue qu'elle connaît. Traiter les deux également vaut
#: mieux que bien traiter l'une et mal l'autre.
#:
#: Cette valeur doit rester identique à celle de l'index `idx_document_recherche`
#: défini dans data_pipeline/load/sql/02_index.sql : un écart suffirait à ce que
#: le planificateur cesse de reconnaître l'index et retombe sur un balayage
#: complet des 6 800 documents, contenu compris.
CONFIGURATION_RECHERCHE = "simple"


class RecherchePleinTexte(BaseFilterBackend):
    """
    Recherche plein texte PostgreSQL sur le titre et le contenu.

    Compétence visée : C5 (épreuve E1)
    Compétence visée : C2 (épreuve E1)

    Choix : `to_tsvector` plutôt que le `SearchFilter` de DRF. Motivation : ce
    dernier produit une suite de `ILIKE '%terme%'`, qui ne peut utiliser aucun
    index et relit le contenu entier de chaque document à chaque appel. La
    recherche plein texte s'appuie sur l'index GIN `idx_document_recherche`,
    vérifié par `EXPLAIN` : `Bitmap Index Scan`, et non `Seq Scan`.

    Choix : `plainto_tsquery`, c'est-à-dire l'opérateur ET entre les termes.
    Motivation : un utilisateur qui tape « pandas dataframe » cherche les
    documents traitant des deux, pas la réunion de tout ce qui parle de l'un ou
    de l'autre — qui ramènerait ici la moitié du corpus.
    """

    #: Nom du paramètre de requête.
    parametre = "recherche"

    def filter_queryset(self, request, queryset, view):
        terme = (request.query_params.get(self.parametre) or "").strip()
        if not terme:
            return queryset

        vecteur = SearchVector("titre", "contenu", config=CONFIGURATION_RECHERCHE)
        requete = SearchQuery(terme, config=CONFIGURATION_RECHERCHE)
        return queryset.annotate(vecteur=vecteur).filter(vecteur=requete)

    def get_schema_operation_parameters(self, view):
        """
        Décrit le paramètre dans la documentation OpenAPI.

        Compétence visée : C5 (épreuve E1) — documentation de l'API
        """
        return [{
            "name": self.parametre,
            "required": False,
            "in": "query",
            "description": (
                "Recherche plein texte sur le titre et le contenu. Les termes "
                "sont combinés par ET. Exemple : « pandas dataframe »."
            ),
            "schema": {"type": "string"},
        }]


class FiltreDocument(filtres.FilterSet):
    """
    Filtres du point de terminaison des documents.

    Compétence visée : C5 (épreuve E1)

    Choix : des filtres nommés d'après ce que le consommateur cherche —
    `source`, `langue`, `licence`, `mot_cle` — et non d'après les colonnes.
    Motivation : le nom de colonne `code_source` est une contrainte du schéma,
    pas un vocabulaire d'API.

    Choix : aucun filtre sur `redistribution_autorisee`. Motivation : le
    gestionnaire par défaut du modèle a déjà écarté les documents non
    diffusables. Exposer le champ laisserait croire qu'on peut demander à voir
    les autres, et un filtre `redistribution_autorisee=false` renverrait une
    liste vide sans expliquer pourquoi.
    """

    # Les deux filtres ci-dessous traversent la clé étrangère jusqu'à la
    # colonne de code. `source_id` désignerait la clé étrangère elle-même, sur
    # laquelle Django refuse le `iexact` — « Unsupported lookup 'iexact' for
    # ForeignKey ». Il faut nommer la colonne cible.
    source = filtres.CharFilter(
        field_name="source__code_source", lookup_expr="iexact",
        label="Code de la source (s1 à s5)",
    )
    licence = filtres.CharFilter(
        field_name="licence__code_licence", lookup_expr="iexact",
        label="Code de la licence",
    )
    type_source = filtres.CharFilter(field_name="code_type_source", lookup_expr="iexact")
    langue = filtres.CharFilter(field_name="langue", lookup_expr="iexact")
    mot_cle = filtres.CharFilter(
        field_name="mots_cles__code_mot_cle", lookup_expr="iexact",
        label="Mot-clé exact",
    )
    extrait_apres = filtres.IsoDateTimeFilter(
        field_name="extrait_le", lookup_expr="gte",
        label="Extrait à partir de cette date (ISO 8601)",
    )
    extrait_avant = filtres.IsoDateTimeFilter(
        field_name="extrait_le", lookup_expr="lte",
        label="Extrait jusqu'à cette date (ISO 8601)",
    )

    class Meta:
        model = Document
        fields = [
            "source", "type_source", "langue", "licence", "mot_cle",
            "extrait_apres", "extrait_avant",
        ]
