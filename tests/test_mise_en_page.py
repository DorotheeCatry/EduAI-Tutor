"""
Les pages tiennent dans l'écran, et rien n'y devient inatteignable.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — accessibilité ; C21 (E5)

`<main>` est en `overflow-hidden`. Un conteneur de contenu qui n'a pas de
hauteur contrainte grandit donc librement et se fait **couper**, sans barre de
défilement pour atteindre le reste. Mesuré sur la page Référentiel avant
correction : 593 px visibles pour 2090 px de contenu — mille cinq cents pixels
de progression que rien ne permettait d'atteindre.

`overflow-y-auto` seul ne suffit pas : sans hauteur, il n'y a rien à faire
défiler. C'est `h-full` qui manquait.
"""

import re
from pathlib import Path

import pytest

# Gabarits de page dont le contenu est rendu dans `<main>`.
PAGES = (
    Path("apps/accueil/templates/accueil/accueil.html"),
    Path("apps/tracker/templates/tracker/dashboard.html"),
    Path("apps/quiz/templates/quiz/room_detail.html"),
    Path("apps/quiz/templates/quiz/multiplayer_game.html"),
)


def _conteneur_racine(gabarit):
    """Rend les classes du premier élément du bloc de contenu."""
    source = gabarit.read_text(encoding="utf-8")
    apres = source[source.index("{% block content %}"):]
    # On saute les commentaires de gabarit, qui précèdent souvent la balise.
    apres = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", apres, flags=re.S)
    trouve = re.search(r"<div class=\"([^\"]+)\"", apres)
    assert trouve, "conteneur racine introuvable dans %s" % gabarit
    return trouve.group(1)


@pytest.mark.parametrize("gabarit", PAGES, ids=lambda p: p.stem)
def test_le_conteneur_de_page_a_une_hauteur(gabarit):
    """
    Le contenu d'une page ne peut pas être coupé sans recours.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Sans `h-full`, le conteneur grandit et `<main>` le coupe : ce qui dépasse
    n'est ni visible ni atteignable. Avec, soit tout tient, soit ce qui dépasse
    défile.
    """
    classes = _conteneur_racine(gabarit)

    assert "h-full" in classes, (
        "%s : le conteneur de page doit porter `h-full`, sinon `<main>` le "
        "coupe silencieusement (classes : %s)" % (gabarit.name, classes)
    )


@pytest.mark.parametrize("gabarit", PAGES, ids=lambda p: p.stem)
def test_le_debordement_est_traite_explicitement(gabarit):
    """
    Chaque page dit ce qu'elle fait de ce qui dépasse.

    Compétence visée : C17 (épreuve E4)

    Deux réponses sont acceptables et elles sont différentes : `overflow-y-auto`
    fait défiler le conteneur, `overflow-hidden` fige l'ossature et confie le
    défilement aux cartes qu'elle contient. Ne rien dire est la seule réponse
    qui coupe le contenu.
    """
    classes = _conteneur_racine(gabarit)

    assert "overflow-y-auto" in classes or "overflow-hidden" in classes, (
        "%s : le débordement doit être traité (classes : %s)"
        % (gabarit.name, classes)
    )


def test_l_ossature_figee_laisse_ses_cartes_retrecir():
    """
    Une ossature figée s'accompagne toujours de `min-h-0`.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Sans `min-h-0`, un enfant de conteneur flexible refuse de rétrécir sous la
    taille de son contenu : le débordement remonte alors à la page entière, et
    l'ossature figée ne fige plus rien. C'est le piège classique de cette mise
    en page, et il ne se voit qu'à l'écran.
    """
    for gabarit in PAGES:
        source = gabarit.read_text(encoding="utf-8")
        classes = _conteneur_racine(gabarit)
        if "flex" in classes and "overflow-hidden" in classes:
            assert "min-h-0" in source, (
                "%s fige son ossature sans laisser ses enfants rétrécir"
                % gabarit.name
            )


def test_les_mots_cles_ressortent_et_gardent_leur_gras():
    """
    Le gras des supports est jaune vif, et reste gras.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — accessibilité

    Ce sont les mots-clés d'un cours : ils doivent être ce qu'on repère en
    premier. En blanc, ils avaient la couleur du texte courant et s'y
    confondaient dès qu'un paragraphe en comptait plusieurs.

    Le gras est conservé délibérément : la couleur seule ne doit jamais porter
    une information (WCAG 1.4.1). Un mot-clé doit rester reconnaissable sur une
    impression en noir et blanc, ou pour qui ne distingue pas ce jaune du texte
    qui l'entoure. Ce test échoue donc si l'on retire le `font-weight`.
    """
    feuille = Path("static/css/tailwind.css").read_text(encoding="utf-8")

    regles = [r for r in re.findall(r"strong\{[^}]*\}", feuille)
              if "color" in r]
    assert regles, "le gras des supports doit porter une couleur explicite"

    for regle in regles:
        assert "#ffd60a" in regle.lower(), (
            "un jaune franc, saturé à 96 % pour se repérer d'un coup d'œil, et "
            "à 10,4:1 sur le fond du panneau — plus du double du seuil AA"
        )
        assert "font-weight" in regle, (
            "la couleur seule ne doit pas porter l'information (WCAG 1.4.1)"
        )
