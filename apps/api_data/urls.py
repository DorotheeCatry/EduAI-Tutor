"""
Routage de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données

Choix : un préfixe `/api/dataset/` distinct de celui que prendra l'API du
service IA. Motivation : le référentiel évalue séparément l'API du jeu de
données (C5, Bloc 1) et celle du service IA (C9, Bloc 2). Deux préfixes
distincts rendent la séparation lisible dans l'URL elle-même, avant même
d'ouvrir le code.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentViewSet,
    ExtractionViewSet,
    SourceViewSet,
    StatistiquesView,
)

app_name = "api_data"

routeur = DefaultRouter()
routeur.register("documents", DocumentViewSet, basename="document")
routeur.register("sources", SourceViewSet, basename="source")
routeur.register("extractions", ExtractionViewSet, basename="extraction")

urlpatterns = [
    path("statistiques/", StatistiquesView.as_view(), name="statistiques"),
    path("", include(routeur.urls)),
]
