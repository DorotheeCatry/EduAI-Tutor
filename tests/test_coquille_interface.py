"""
La feuille de style est compilée et servie avec le document.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — déploiement ; C21 (E5)

Tailwind était chargé depuis `cdn.tailwindcss.com`, qui n'est pas une feuille
de style mais un générateur de 407 Kio s'exécutant dans le navigateur. Tant
qu'il n'avait pas tourné — environ 180 ms, cache chaud — aucune classe ne
voulait rien dire : le fond était blanc, la coquille en bloc, la barre latérale
large de 1249 px au lieu de 64. Chaque navigation étant un chargement complet,
le basculement se produisait à chaque changement de page (décision 034).
"""

import re
from pathlib import Path

GABARITS = (
    sorted(Path("templates").rglob("*.html"))
    + sorted(Path("apps").rglob("templates/**/*.html"))
)
FEUILLE = Path("static/css/tailwind.css")

# Pages qui portent leur propre en-tête au lieu d'hériter de `base.html`.
PAGES_AUTONOMES = (
    Path("templates/base.html"),
    Path("apps/users/templates/users/login.html"),
    Path("apps/users/templates/users/register.html"),
)

# Classes présentes dans les gabarits que Tailwind ne produit pas, et qui n'ont
# donc pas à figurer dans la feuille :
#   - accroches de JavaScript, jamais stylées (`tab-button`, `tuteur-dock`…) ;
#   - classes de Prism, posées par la coloration syntaxique ;
#   - `prose` et `prose-invert`, qui viennent du greffon typography — non
#     installé : ces deux-là ne produisent aucun style aujourd'hui (réserve 18).
HORS_TAILWIND = {
    "action-enrichir", "avatar-option", "language-python", "prose", "prose-invert", "python",
    "question-scroll-container", "tab-button", "tab-content",
    "test-actual", "test-result", "test-status", "tuteur-dock",
}


def _echapper(classe):
    """Échappe les caractères qu'un sélecteur CSS protège par une barre oblique."""
    return re.sub(r"([:./\[\]()#%!])", r"\\\1", classe)


def test_aucun_gabarit_ne_charge_le_generateur_a_la_volee():
    """
    Plus aucune page ne fabrique ses styles dans le navigateur.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Les pages de connexion et d'inscription n'héritent pas de `base.html` : les
    oublier aurait laissé le saut d'affichage sur les deux premières pages que
    voit un visiteur.
    """
    fautifs = [str(g) for g in GABARITS
               if "cdn.tailwindcss.com" in g.read_text(encoding="utf-8")
               and "Tailwind était chargé" not in g.read_text(encoding="utf-8")]

    assert fautifs == [], "ces pages chargent encore le générateur : %s" % fautifs


def test_chaque_page_autonome_lie_la_feuille_compilee():
    """
    Les trois pages qui portent leur propre en-tête lient la feuille.

    Compétence visée : C17 (épreuve E4)
    """
    for gabarit in PAGES_AUTONOMES:
        source = gabarit.read_text(encoding="utf-8")
        assert "css/tailwind.css" in source, (
            "%s ne lie pas la feuille compilée" % gabarit
        )


def test_la_reservation_des_icones_ne_prime_sur_aucune_classe():
    """
    La taille par défaut des icônes cède devant une classe explicite.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Écrite `[data-lucide] { … }`, la règle a la même spécificité qu'une classe
    utilitaire et, venant après elle dans la feuille, l'emportait : une icône
    déclarée `w-8 h-8` était ramenée à 20 px. Le défaut a été constaté en
    comparant la géométrie du CDN et de la feuille compilée, pas à la lecture.
    `:where()` annule la spécificité et rend la règle purement supplétive.
    """
    entree = Path("theme/tailwind-v3/entree.css").read_text(encoding="utf-8")

    assert ":where([data-lucide])" in entree
    assert re.search(r"^\[data-lucide\]", entree, re.M) is None, (
        "sans :where(), la réservation écrase les tailles explicites"
    )


def test_toute_classe_des_gabarits_existe_dans_la_feuille():
    """
    La feuille compilée n'a pas pris de retard sur les gabarits.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    C'est le risque propre à une feuille compilée : une classe ajoutée à un
    gabarit sans reconstruction ne produit aucun style, et rien ne le signale —
    la page s'affiche, simplement de travers. Ce test remplace la vigilance par
    une vérification.
    """
    feuille = FEUILLE.read_text(encoding="utf-8")

    # Les classes définies dans un <style> de gabarit sont locales à leur page.
    styles_locaux = ""
    for gabarit in GABARITS:
        source = gabarit.read_text(encoding="utf-8")
        styles_locaux += "".join(re.findall(r"<style[^>]*>(.*?)</style>", source, re.S))

    manquantes = set()
    for gabarit in GABARITS:
        source = gabarit.read_text(encoding="utf-8")
        for attribut in re.findall(r'class="([^"]*)"', source):
            # Une valeur assemblée par le gabarit ou par JavaScript ne se relève
            # pas à la lecture : elle est écartée.
            if "{{" in attribut or "{%" in attribut or "${" in attribut:
                continue
            for classe in attribut.split():
                if not classe or classe in HORS_TAILWIND:
                    continue
                if "." + classe in styles_locaux:
                    continue
                if "." + _echapper(classe) not in feuille:
                    manquantes.add(classe)

    assert manquantes == set(), (
        "classes absentes de la feuille — reconstruire (voir README) : %s"
        % sorted(manquantes)
    )
