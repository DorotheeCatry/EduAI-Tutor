"""
Vues de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données

Choix : `ReadOnlyModelViewSet` partout. Motivation : le jeu de données est
alimenté par le pipeline, jamais par l'API. Un `ModelViewSet` complet
exposerait POST, PUT, PATCH et DELETE, que le routeur de base et le rôle
PostgreSQL rejetteraient — mais les routes existeraient, seraient documentées
dans l'OpenAPI, et un client les tenterait. Mieux vaut qu'elles n'existent pas.

Choix : `select_related` et `prefetch_related` systématiques. Motivation : sans
eux, une page de vingt documents déclenche une requête par document pour la
source, une par document pour la licence, et une par document pour les
mots-clés — soixante et une requêtes au lieu de trois. Le problème est
invisible sur un jeu de test et bien réel sur 6 800 documents.
"""

from __future__ import annotations

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from .filtres import FiltreDocument, RecherchePleinTexte
from .models import (
    Document,
    Extraction,
    Source,
    condition_exposable_depuis_source,
)
from .serializers import (
    DocumentDetailSerializer,
    DocumentListeSerializer,
    ExtractionSerializer,
    SourceSerializer,
    StatistiquesSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="Lister les documents du corpus",
        description=(
            "Liste paginée des documents collectés par le pipeline.\n\n"
            "Seuls les documents dont la licence autorise la redistribution "
            "sont exposés. Les documents d'origine non vérifiée et les "
            "productions d'apprenants en sont exclus par construction, quel "
            "que soit le filtre appliqué."
        ),
    ),
    retrieve=extend_schema(
        summary="Consulter un document",
        description=(
            "Détail d'un document, contenu intégral compris, avec les "
            "attributs propres à son type de source dans l'objet `detail`."
        ),
    ),
)
class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Documents du corpus collecté.

    Compétence visée : C5 (épreuve E1)
    """

    # Clé de recherche explicite : la clé primaire s'appelle `id_document` et
    # non `id`. Sans cette déclaration, la documentation OpenAPI décrit le
    # paramètre d'URL comme une chaîne de type indéterminé, faute de trouver un
    # champ `id` sur le modèle.
    lookup_field = "id_document"
    filter_backends = [DjangoFilterBackend, RecherchePleinTexte, OrderingFilter]
    filterset_class = FiltreDocument
    ordering_fields = ["extrait_le", "titre", "id_document"]
    ordering = ["-extrait_le", "id_document"]

    def get_queryset(self):
        """
        Renvoie les documents exposables, avec leurs relations préchargées.

        Compétence visée : C5 (épreuve E1)
        Compétence visée : C4 (épreuve E1)

        Le filtrage par licence n'apparaît pas ici : il est porté par le
        gestionnaire par défaut du modèle. C'est délibéré — une exigence qu'on
        peut oublier vue par vue n'est pas une garantie. Voir
        `DocumentExposableManager` dans models.py.
        """
        jeu = Document.objects.select_related("source", "source__type_source", "licence")

        if self.action == "retrieve":
            # Le détail expose les attributs de la table fille : les cinq
            # relations sont préchargées, une seule existera pour un document
            # donné, la spécialisation étant exclusive.
            return jeu.prefetch_related("mots_cles").select_related(
                "detail_api_rest", "detail_web", "detail_fichier",
                "detail_big_data", "detail_base_donnees",
            )
        return jeu.prefetch_related("mots_cles")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DocumentDetailSerializer
        return DocumentListeSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Lister les cinq sources du corpus",
        description=(
            "Les cinq types de sources exigés par le référentiel, avec leurs "
            "contraintes d'accès et leur durée de conservation.\n\n"
            "Le décompte `nb_documents` ne porte que sur les documents "
            "exposables par l'API."
        ),
    ),
    retrieve=extend_schema(summary="Consulter une source"),
)
class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Les cinq sources du corpus.

    Compétence visée : C1 (épreuve E1) — couverture des cinq types
    Compétence visée : C5 (épreuve E1)
    """

    serializer_class = SourceSerializer
    # /api/dataset/sources/s3/ se lit mieux qu'un identifiant technique, et le
    # code de source EST la clé primaire de la table.
    lookup_field = "code_source"
    filter_backends = [OrderingFilter]
    ordering_fields = ["code_source", "nom"]
    ordering = ["code_source"]

    def get_queryset(self):
        """
        Renvoie les sources, comptant leurs documents exposables.

        Compétence visée : C5 (épreuve E1)

        Choix : le décompte est restreint aux documents diffusables, par le
        même critère que le gestionnaire du modèle Document. Motivation :
        annoncer 380 documents pour le corpus local quand l'API n'en sert que
        298 ferait passer un filtrage voulu pour une défaillance.
        """
        return Source.objects.select_related("type_source").annotate(
            nb_documents=Count(
                "documents",
                filter=condition_exposable_depuis_source(),
                distinct=True,
            ),
        )


@extend_schema_view(
    list=extend_schema(
        summary="Historique des campagnes d'extraction",
        description=(
            "Une ligne par exécution d'extracteur : durée, statut, volumétrie, "
            "nombre d'erreurs.\n\n"
            "Le statut vaut `succes`, `echec`, ou `vide` lorsqu'une source "
            "n'avait légitimement rien à ramener — cas de la base applicative "
            "sans production d'apprenant. La distinction vient d'un incident "
            "documenté : une extraction qui réussit en ne produisant rien est "
            "presque toujours une panne silencieuse."
        ),
    ),
    retrieve=extend_schema(summary="Consulter une campagne d'extraction"),
)
class ExtractionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Historique des campagnes d'extraction.

    Compétence visée : C1 (épreuve E1) — traçabilité
    Compétence visée : C20 (épreuve E5) — suivi d'un traitement
    """

    serializer_class = ExtractionSerializer
    lookup_field = "id_extraction"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {"statut": ["exact"], "source": ["exact"]}
    ordering_fields = ["horodatage_debut", "duree_secondes", "nb_enregistrements"]
    ordering = ["-horodatage_debut"]

    def get_queryset(self):
        return Extraction.objects.select_related("source")


class StatistiquesView(APIView):
    """
    Volumétrie du corpus, par source, type, licence et langue.

    Compétence visée : C5 (épreuve E1)

    Choix : une vue simple plutôt qu'une action d'un jeu de vues. Motivation :
    la réponse n'est pas une collection de ressources et ne se pagine pas. La
    forcer dans un `ViewSet` produirait une documentation OpenAPI trompeuse.
    """

    @extend_schema(
        summary="Volumétrie du corpus",
        description=(
            "Décomptes du jeu de données exposé : par source, par type de "
            "source, par licence et par langue.\n\n"
            "Tous les décomptes portent sur les documents diffusables. Un "
            "total incluant les documents non redistribuables annoncerait un "
            "corpus que l'API ne sait pas servir."
        ),
        responses=StatistiquesSerializer,
    )
    def get(self, request):
        """
        Calcule et renvoie la volumétrie.

        Compétence visée : C5 (épreuve E1)

        Choix : quatre agrégations en base plutôt qu'un parcours en Python.
        Motivation : compter 6 800 documents en mémoire pour en tirer quatre
        décomptes ferait transiter le contenu intégral du corpus — plusieurs
        dizaines de mégaoctets — pour produire une réponse d'un kilooctet.
        """
        documents = Document.objects.all()

        par_source = list(
            documents.values("source_id", "source__nom", "code_type_source")
            .annotate(documents=Count("id_document"))
            .order_by("source_id")
        )
        par_type = list(
            documents.values("code_type_source")
            .annotate(documents=Count("id_document"))
            .order_by("code_type_source")
        )
        par_licence = list(
            documents.values("licence_id", "licence__libelle")
            .annotate(documents=Count("id_document"))
            .order_by("licence_id")
        )
        par_langue = list(
            documents.values("langue")
            .annotate(documents=Count("id_document"))
            .order_by("langue")
        )

        derniere = (
            Extraction.objects.order_by("-horodatage_debut")
            .values_list("horodatage_debut", flat=True)
            .first()
        )

        donnees = {
            "documents_exposes": documents.count(),
            "par_source": [
                {
                    "source": ligne["source_id"],
                    "nom": ligne["source__nom"],
                    "type_source": ligne["code_type_source"],
                    "documents": ligne["documents"],
                }
                for ligne in par_source
            ],
            "par_type_source": [
                {"type_source": ligne["code_type_source"], "documents": ligne["documents"]}
                for ligne in par_type
            ],
            "par_licence": [
                {
                    "licence": ligne["licence_id"],
                    "libelle": ligne["licence__libelle"],
                    "documents": ligne["documents"],
                }
                for ligne in par_licence
            ],
            "par_langue": [
                {"langue": ligne["langue"], "documents": ligne["documents"]}
                for ligne in par_langue
            ],
            "mots_cles_distincts": (
                documents.values("mots_cles__code_mot_cle")
                .exclude(mots_cles__code_mot_cle=None)
                .distinct().count()
            ),
            "derniere_extraction": derniere,
        }
        return Response(StatistiquesSerializer(donnees).data)
