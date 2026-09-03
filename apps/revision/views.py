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
from apps.revision.services import (
    corriger,
    erreurs_a_rejouer,
    repartition_des_erreurs,
)


@login_required
def flashcards(request):
    """
    Liste les notions à revoir, la plus résistante en tête.

    Compétence visée : C17 (épreuve E4)
    """
    return render(request, 'revision/flashcards.html', {
        'a_revoir': notions_a_revoir(request.user, limite=20),
        'erreurs_de_quiz': erreurs_de_quiz(request.user, limite=20),
        'repartition': repartition_des_erreurs(request.user),
    })


@login_required
def mes_erreurs(request):
    """
    Repose les questions réellement manquées, et corrige.

    Compétence visée : C17 (épreuve E4)
    Compétences concernées : C13 (E3) — quotas ; C20 (E5)

    Choix : les VRAIES questions, et non un quiz engendré sur la notion.
    Motivation : l'apprenant qui vient ici veut revoir ce qu'il a manqué. Un
    quiz sur le thème mesure la notion ; reposer la question mesure l'erreur.

    Choix : aucune génération. Motivation : tout ce qu'il faut est en base — la
    question, la bonne réponse, et celle qui avait été donnée. Cette révision
    ne consomme donc aucun quota, et reste disponible quand il est épuisé,
    c'est-à-dire quand l'apprenant a beaucoup travaillé.
    """
    if request.method == 'POST':
        # Les réponses arrivent par `reponse-<id>` : un identifiant inconnu ou
        # non numérique est ignoré, il ne correspond à rien en base.
        reponses = {}
        for cle, valeur in request.POST.items():
            if not cle.startswith('reponse-'):
                continue
            try:
                reponses[int(cle.removeprefix('reponse-'))] = valeur
            except ValueError:
                continue
        return render(request, 'revision/mes_erreurs.html', {
            'resultat': corriger(request.user, reponses),
        })

    notions = [n for n in request.GET.getlist('notion') if n.strip()]
    return render(request, 'revision/mes_erreurs.html', {
        'questions': erreurs_a_rejouer(request.user, notions=notions),
        'notions_choisies': notions,
    })


@login_required
def review(request):
    return render(request, 'revision/review.html')
