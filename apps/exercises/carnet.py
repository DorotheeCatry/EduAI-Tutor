"""
Le carnet : plusieurs exercices à la suite, et son export en `.ipynb`.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) ; C10 (E3)

Un exercice à la fois convient pour vérifier une notion. Une séance de travail,
elle, en enchaîne plusieurs : on lit, on essaie, on revient en arrière. C'est
la forme du carnet, et c'est celle que les apprenants connaissent déjà par
Jupyter.

L'export produit un vrai fichier `nbformat` 4.5, ouvrable dans Jupyter, VS Code
ou Colab. Il porte ce que l'apprenant a écrit — pas la solution, qui n'est
jamais transmise (décision 029) : un carnet qui contiendrait la réponse cesse
d'être un exercice.

Choix : construire le JSON ici plutôt qu'ajouter la dépendance `nbformat`.
Motivation : la structure d'un carnet tient en trois clés, elle est stable
depuis 2015, et l'écrire nous évite d'embarquer une bibliothèque — avec ses
mises à jour et sa surface — pour produire un dictionnaire.
"""

import json
from uuid import uuid4

#: La version du format. 4.5 est celle qui impose un identifiant par cellule.
NBFORMAT, NBFORMAT_MINOR = 4, 5


def _identifiant():
    """Rend un identifiant de cellule conforme : lettres, chiffres, tirets."""
    return uuid4().hex[:12]


def _lignes(texte):
    """
    Découpe un texte comme `nbformat` l'attend : une entrée par ligne, saut
    de ligne compris, sauf la dernière.

    Compétence visée : C17 (épreuve E4)

    Choix : respecter cette forme plutôt que de poser le texte en un bloc.
    Motivation : les deux s'ouvrent, mais seule la première produit un `diff`
    lisible quand le carnet est versionné — et c'est ce que les outils
    écrivent, donc ce qu'un jury reconnaîtra.
    """
    if not texte:
        return []
    lignes = texte.splitlines(keepends=True)
    return lignes


def cellule_markdown(texte):
    """Une cellule de texte."""
    return {
        "cell_type": "markdown",
        "id": _identifiant(),
        "metadata": {},
        "source": _lignes(texte),
    }


def cellule_code(code):
    """Une cellule de code, jamais exécutée : le carnet part vierge de sorties."""
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": _identifiant(),
        "metadata": {},
        "outputs": [],
        "source": _lignes(code),
    }


def composer(titre, exercices):
    """
    Compose le carnet à partir des exercices et du code saisi.

    Compétence visée : C17 (épreuve E4)

    `exercices` est une suite de dictionnaires portant `titre`, `enonce`,
    `code` et, s'il existe, `competence`.

    Choix : l'énoncé en cellule de texte, le code en cellule de code, et rien
    d'autre. Motivation : un carnet doit s'ouvrir et s'exécuter tel quel. Y
    glisser des consignes de la plateforme, des identifiants ou des liens
    ferait un document qui ne sert plus qu'à l'intérieur de l'application.
    """
    cellules = [cellule_markdown(f"# {titre}\n")]
    for rang, exercice in enumerate(exercices, start=1):
        entete = f"## {rang}. {exercice['titre']}\n"
        if exercice.get("competence"):
            entete += f"\n*{exercice['competence']}*\n"
        cellules.append(cellule_markdown(f"{entete}\n{exercice.get('enonce') or ''}\n"))
        cellules.append(cellule_code(exercice.get("code") or ""))

    return {
        "cells": cellules,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": NBFORMAT,
        "nbformat_minor": NBFORMAT_MINOR,
    }


def en_json(carnet):
    """
    Rend le carnet sous la forme qu'attend un fichier `.ipynb`.

    Compétence visée : C17 (épreuve E4)

    `ensure_ascii=False` : un énoncé français contient des accents, et les
    échapper produirait un fichier illisible à l'ouverture dans un éditeur de
    texte, pour aucun gain.
    """
    return json.dumps(carnet, ensure_ascii=False, indent=1) + "\n"
