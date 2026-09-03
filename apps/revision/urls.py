from django.urls import path
from . import views

app_name = 'revision'

urlpatterns = [
    path('flashcards/', views.flashcards, name='flashcards'),
    path('mes-erreurs/', views.mes_erreurs, name='mes_erreurs'),
    path('review/', views.review, name='review'),
]
