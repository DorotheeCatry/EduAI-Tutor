"""
La coquille de l'application est stylée avant l'arrivée du CDN.

Compétence visée : C17 (épreuve E4) — application web
Compétence concernée : C21 (E5) — non-régression d'un défaut constaté

Tailwind est chargé depuis un CDN sous la forme d'un générateur qui s'exécute
dans le navigateur, et non d'une feuille de style. Tant qu'il n'a pas tourné —
environ 180 ms, cache chaud — aucune classe utilitaire ne veut dire quoi que ce
soit. Mesuré sur la page du tableau de bord, Tailwind rendu injoignable :

| | fond | disposition | barre latérale |
|---|---|---|---|
| sans squelette | transparent, donc blanc | `block` | 1249 px |
| avec squelette | `#111827` | `flex` | 64 px |

Chaque navigation étant un chargement complet, ce basculement se produisait à
chaque changement de page.
"""

from pathlib import Path

BASE = Path("templates/base.html")


def _source():
    return BASE.read_text(encoding="utf-8")


def test_le_squelette_precede_le_chargement_du_cdn():
    """
    Les règles de la coquille arrivent avec le document, pas après.

    Compétence visée : C17 (épreuve E4)

    Placées après le script, elles ne changeraient rien : le premier affichage
    a lieu bien avant que le générateur ait produit sa feuille.
    """
    source = _source()

    debut_style = source.index("<style>")
    chargement_cdn = source.index("cdn.tailwindcss.com")

    assert debut_style < chargement_cdn, (
        "le squelette doit être servi avec le document, avant le CDN"
    )


def test_le_fond_ne_depend_d_aucune_classe_utilitaire():
    """
    Le fond sombre est posé en clair, jamais par la seule classe Tailwind.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    `bg-gray-900` sur le `body` ne veut rien dire tant que Tailwind n'a pas
    tourné : le navigateur peint alors sa couleur par défaut, blanche. Sur une
    application sombre, c'est le défaut le plus visible des deux.
    """
    source = _source()
    squelette = source[source.index("<style>"):source.index("</style>")]

    assert "background: #111827" in squelette, (
        "le fond sombre doit être écrit en clair dans le squelette"
    )


def test_le_squelette_couvre_les_classes_de_structure():
    """
    Les classes qui portent la disposition de la coquille sont toutes définies.

    Compétence visée : C17 (épreuve E4)

    Il en manque une, et la coquille saute encore — sur une dimension moins
    voyante, donc plus difficile à rattacher à sa cause.
    """
    source = _source()
    squelette = source[source.index("<style>"):source.index("</style>")]

    # Relevées sur les éléments racines de base.html et de ses composants :
    # barre latérale (w-16), barre d'onglets (h-10), barre d'état (h-6).
    for classe in (".flex", ".flex-col", ".flex-1", ".flex-shrink-0",
                   ".h-screen", ".min-w-0", ".w-16", ".h-10", ".h-6"):
        assert classe + " {" in squelette, (
            "la classe %s porte la disposition de la coquille" % classe
        )


def test_la_place_des_icones_est_reservee():
    """
    Les icônes n'ajoutent pas un second décalage en apparaissant.

    Compétence visée : C17 (épreuve E4)

    Les éléments `<i data-lucide>` sont vides jusqu'à ce que Lucide les
    remplace par des SVG dimensionnés. Sans réservation, leur apparition
    décale la mise en page une deuxième fois, après celle de Tailwind.
    """
    source = _source()
    squelette = source[source.index("<style>"):source.index("</style>")]

    assert "[data-lucide]" in squelette
