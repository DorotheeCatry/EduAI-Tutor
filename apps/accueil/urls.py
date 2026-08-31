"""
Routes de la page d'accueil.

Compétence visée : C17 (épreuve E4) — application web
"""

from django.urls import path

from . import views

app_name = "accueil"

urlpatterns = [
    path("", views.accueil, name="accueil"),
]
