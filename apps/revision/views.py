"""
Pages de révision.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C20 (E5) ; C21 (E5)

Cette page affichait une séance de révision entièrement inventée — « Python
Decorators, 8 flashcards, ~5 minutes », 24 cartes maîtrisées, 92 % de réussite,
7 jours de série — sur un compte qui n'avait jamais rien révisé, et sa vue ne
passait aucune donnée au gabarit (incident 011).

Le produit n'a pas de système de cartes ni de répétition espacée : il n'y a
donc pas de séance à proposer. Ce qu'il a, ce sont les notions qui ont résisté,
et c'est ce que la page montre désormais — les mêmes données que le bloc
« à revoir » de l'accueil, avec le même critère affiché.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accueil.services import erreurs_de_quiz, notions_a_revoir


@login_required
def flashcards(request):
    """
    Liste les notions à revoir, la plus résistante en tête.

    Compétence visée : C17 (épreuve E4)
    """
    return render(request, 'revision/flashcards.html', {
        'a_revoir': notions_a_revoir(request.user, limite=20),
        'erreurs_de_quiz': erreurs_de_quiz(request.user, limite=20),
    })


@login_required
def review(request):
    return render(request, 'revision/review.html')
