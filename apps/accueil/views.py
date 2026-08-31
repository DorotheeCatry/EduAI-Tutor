"""
Vue de la page d'accueil.

Compétence visée : C17 (épreuve E4) — application web

Cette page remplace le générateur de cours comme porte d'entrée. Le générateur
reste accessible ; il cesse d'être ce qu'on voit en arrivant.

Elle répond à deux questions, dans cet ordre : **où j'en suis**, et **qu'est-ce
que je fais maintenant**.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import resume_de_l_accueil


@login_required
def accueil(request):
    """
    Affiche les quatre blocs de l'accueil.

    Compétence visée : C17 (épreuve E4)

    Aucune valeur n'est fabriquée : ce que la page montre est ce que la base
    contient. Quand elle ne contient rien, chaque bloc affiche son état vide et
    oriente vers une première action — c'est le premier écran d'un nouvel
    apprenant, et celui d'une démonstration sur une base neuve.
    """
    return render(request, "accueil/accueil.html", resume_de_l_accueil(request.user))
