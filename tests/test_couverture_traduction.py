"""
La couverture du catalogue anglais.

Compétence visée : C10 (épreuve E3) — intégration respectant l'accessibilité
Compétences concernées : C17 (E4) — application web ; C13 (E3)

L'interface est écrite en français et servie en anglais aux comptes qui l'ont
choisi. Le mécanisme — sélecteur de langue, attribut `lang` dynamique,
catalogues compilés — est éprouvé par `tests/test_i18n.py`. Ce fichier-ci
éprouve autre chose : la **couverture**. Un mécanisme parfait sur un catalogue
à moitié rempli sert la moitié de l'écran en français.

Ce contrôle existe parce que le rapport E3 annonçait « 330 chaînes traduites »
alors que le catalogue n'en portait que 156 sur 327 chaînes de source
française. Rien ne signalait l'écart : une chaîne non traduite ne provoque
aucune erreur, elle retombe silencieusement sur le français.
"""

import re
from pathlib import Path

CATALOGUE_ANGLAIS = Path("locale/en/LC_MESSAGES/django.po")
CATALOGUE_FRANCAIS = Path("locale/fr/LC_MESSAGES/django.po")

# Chaînes de source française dont la traduction anglaise est le mot lui-même.
# Leur `msgstr` vide n'est pas un oubli : le repli de Django rend le `msgid`,
# qui est déjà la forme anglaise. Toute chaîne ajoutée ici doit l'être
# sciemment — c'est ce qui distingue « identique » de « pas encore traduit ».
IDENTIQUES_EN_ANGLAIS = {
    "Sources",
    "Pages",
    "Licence",
    "Correct",
    "Incorrect",
    "Source",
    "Module",
    "Modules",
    "Code",
    "Description",
    "Version",
    # Chaînes déjà rédigées en anglais dans le code, que le catalogue français
    # ne traduit pas non plus. Elles relèvent du même repli.
    "e.g.: How do Python decorators work? Explain Python classes with examples...",
    'AI generated a malformed response. Basic exercise created on \\"%(sujet)s\\".',
    "Compete with friends in real-time",
    "Koda waving",
}


def _entrees_approximatives(chemin: Path) -> set[str]:
    """
    Les entrées que `gettext` a devinées et marquées « fuzzy ».

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Quand une chaîne nouvelle ressemble à une chaîne disparue, `makemessages`
    recopie l'ancienne traduction et pose le marqueur `fuzzy`. La devinette est
    presque toujours fausse — « Créé le » est devenu « Imported on », « À
    revoir » est devenu « Worth knowing: ».

    Le piège est double. `msgfmt` **exclut** ces entrées du catalogue compilé :
    la chaîne retombe donc sur sa langue source, et un décompte des `msgstr`
    non vides les compte pourtant comme traduites. Une entrée approximative est
    donc une chaîne non traduite qui se présente comme traduite.

    L'en-tête du catalogue porte le même marqueur sans que cela signifie quoi
    que ce soit : son `msgid` est vide, et il est écarté ici.
    """
    approximatives = set()
    for bloc in chemin.read_text(encoding="utf-8").split("\n\n"):
        if "#, fuzzy" not in bloc:
            continue
        identifiant = re.search(r'^msgid ((?:".*"\n?)+)', bloc, re.M)
        if not identifiant:
            continue
        cle = "".join(re.findall(r'"(.*)"', identifiant.group(1)))
        if cle:
            approximatives.add(cle)
    return approximatives


def _catalogue(chemin: Path) -> dict[str, str]:
    """
    Lit un fichier `.po` et rend `{msgid: msgstr}`, forme échappée comprise.

    Compétence visée : C10 (épreuve E3)

    Choix : une lecture directe du fichier plutôt que `polib` ou le compilateur
    de Django. Motivation : le test doit porter sur ce qui est versionné et
    relu, pas sur le binaire `.mo` qui en dérive — c'est le fichier `.po` qu'une
    contribution modifie, et c'est donc lui qu'il faut garder.
    """
    catalogue: dict[str, str] = {}
    for bloc in chemin.read_text(encoding="utf-8").split("\n\n"):
        identifiant = re.search(r'^msgid ((?:".*"\n?)+)', bloc, re.M)
        traduction = re.search(r'^msgstr ((?:".*"\n?)+)', bloc, re.M)
        if not identifiant or not traduction:
            continue
        cle = "".join(re.findall(r'"(.*)"', identifiant.group(1)))
        valeur = "".join(re.findall(r'"(.*)"', traduction.group(1)))
        if cle:  # l'en-tête du catalogue porte un msgid vide
            catalogue[cle] = valeur
    return catalogue


def _chaines_de_source_francaise() -> set[str]:
    """
    Les chaînes que le catalogue anglais doit traduire.

    Compétence visée : C10 (épreuve E3)

    Le projet mélange deux langues à la source : une partie des chaînes est
    écrite en anglais dans le code, une autre en français. Une chaîne écrite en
    anglais n'a rien à faire dans le décompte des traductions manquantes — son
    `msgstr` anglais vide est le bon comportement.

    Le départage ne se devine pas, il se lit : **une chaîne de source anglaise
    est celle que le catalogue français traduit.** C'est un fait du dépôt, pas
    une heuristique sur le texte.
    """
    anglais = _catalogue(CATALOGUE_ANGLAIS)
    francais = _catalogue(CATALOGUE_FRANCAIS)
    return {cle for cle in anglais if not francais.get(cle)}


def test_toute_chaine_francaise_a_une_forme_anglaise():
    """
    Aucune chaîne de source française n'est servie telle quelle à un anglophone.

    Compétence visée : C10 (épreuve E3), C17 (E4)

    Une chaîne non traduite ne lève aucune erreur : elle retombe sur le
    français, et l'écran se remplit de deux langues sans que rien ne le dise.
    Ce test est le seul endroit où cet oubli devient visible.
    """
    anglais = _catalogue(CATALOGUE_ANGLAIS)
    approximatives = _entrees_approximatives(CATALOGUE_ANGLAIS)
    manquantes = sorted(
        cle for cle in _chaines_de_source_francaise()
        if (not anglais[cle] or cle in approximatives)
        and cle not in IDENTIQUES_EN_ANGLAIS
    )

    assert not manquantes, (
        f"{len(manquantes)} chaîne(s) française(s) seraient servies en français "
        f"à un compte anglophone. Traduisez-les dans locale/en/, ou "
        f"inscrivez-les dans IDENTIQUES_EN_ANGLAIS si le mot est le même :\n  - "
        + "\n  - ".join(manquantes[:20])
    )


def test_la_liste_des_identiques_ne_couvre_aucune_chaine_deja_traduite():
    """
    La liste d'exemption ne sert pas à masquer une traduction existante.

    Compétence visée : C10 (épreuve E3)

    Une entrée d'exemption qui porte en réalité une traduction serait une
    dérogation devenue sans objet, laissée là par inadvertance. La liste doit
    dire la vérité sur elle-même, sans quoi elle cesse d'être lisible.
    """
    anglais = _catalogue(CATALOGUE_ANGLAIS)
    superflues = sorted(
        cle for cle in IDENTIQUES_EN_ANGLAIS if anglais.get(cle)
    )

    assert not superflues, (
        "Ces chaînes portent une traduction et n'ont donc plus à figurer "
        f"dans IDENTIQUES_EN_ANGLAIS : {superflues}"
    )


def test_les_marqueurs_de_variable_survivent_a_la_traduction():
    """
    Une traduction qui perd un `%(nom)s` casse la page à l'exécution.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Django interpole les chaînes après traduction. Un marqueur oublié ou
    renommé ne se voit pas à la relecture du catalogue : il lève un
    `KeyError` sur la page, en anglais seulement, donc jamais pendant un essai
    en français. `msgfmt --check` fait cette vérification pour les formats de
    type `printf` ; ce test la refait ici pour qu'elle échoue dans la suite du
    projet et non dans la chaîne de compilation.
    """
    marqueur = re.compile(r"%\([a-zA-Z_]+\)s")
    incoherentes = []

    for cle, valeur in _catalogue(CATALOGUE_ANGLAIS).items():
        if not valeur:
            continue
        if set(marqueur.findall(cle)) != set(marqueur.findall(valeur)):
            incoherentes.append(cle)

    assert not incoherentes, (
        "La traduction anglaise ne porte pas les mêmes marqueurs de variable "
        f"que la source : {incoherentes}"
    )


def test_aucune_entree_approximative_ne_subsiste():
    """
    Les deux catalogues sont exempts d'entrées devinées par `gettext`.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    Une entrée approximative n'échoue nulle part : elle est simplement absente
    du catalogue compilé, et la chaîne s'affiche dans sa langue source. Le
    dépôt en a porté trente-quatre côté anglais et trente-cinq côté français,
    avec des rapprochements comme « Créé le » vers « Imported on ». Aucun outil
    de la chaîne ne les signalait.

    Corriger une entrée approximative, c'est soit écrire la vraie traduction,
    soit vider le `msgstr` quand la source suffit — dans les deux cas, retirer
    le marqueur.
    """
    for chemin in (CATALOGUE_ANGLAIS, CATALOGUE_FRANCAIS):
        approximatives = sorted(_entrees_approximatives(chemin))
        assert not approximatives, (
            f"{chemin} porte {len(approximatives)} entrée(s) approximative(s), "
            f"écartées du catalogue compilé sans que rien ne le dise :\n  - "
            + "\n  - ".join(approximatives[:20])
        )
