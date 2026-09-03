"""
Conversion d'une session interactive Python en script exécutable.

Compétence visée : C17 (épreuve E4) — application web
Compétence concernée : C10 (E3)

Les supports de cours sont écrits comme des sessions au prompt : chaque ligne
de code y est précédée de `>>>` ou de `...`, et le résultat est recopié en
dessous, sans prompt. Ce format se lit très bien et **ne s'exécute pas** : la
première ligne rendue à Python est `>>> furniture = [...]`, soit une erreur de
syntaxe.

Le bouton « Run » posé sur ces blocs échouait donc systématiquement, alors que
la même cellule exécutait sans peine le code tapé à la main. Ce module comble
l'écart, et rien d'autre : il ne modifie pas le code que l'apprenant écrit
lui-même.
"""

import ast

#: Les deux amorces d'une session interactive : la première ligne d'une
#: instruction, et ses lignes de continuation.
PROMPTS = (">>> ", "... ")

#: Les mêmes, pour une ligne vide au prompt — sans l'espace qui suit.
PROMPTS_NUS = (">>>", "...")


def ressemble_a_une_session(code: str) -> bool:
    """
    Dit si un extrait est une session interactive plutôt qu'un script.

    Compétence visée : C17 (épreuve E4)

    Choix : la présence d'au moins une ligne amorcée par `>>>`, et non une
    analyse plus fine. Motivation : un script ordinaire ne commence jamais une
    ligne par `>>>`, qui n'est pas un opérateur Python. Le critère est donc
    sans faux positif, et c'est ce qui compte : convertir à tort un script
    valide le casserait.
    """
    return any(ligne.lstrip().startswith(">>>") for ligne in code.splitlines())


def _lignes_de_code(code: str) -> str:
    """
    Retire les amorces et écarte les lignes de résultat.

    Compétence visée : C17 (épreuve E4)

    Choix : une ligne sans amorce est un RÉSULTAT affiché par le prompt, donc
    elle est écartée. Motivation : la garder produirait du texte libre au
    milieu du script, soit une erreur de syntaxe à la première exécution.
    """
    gardees = []
    for ligne in code.splitlines():
        nue = ligne.lstrip()
        if nue.startswith(PROMPTS):
            decalage = len(ligne) - len(nue)
            gardees.append(ligne[decalage + 4:])
        elif nue in PROMPTS_NUS:
            gardees.append("")
    return "\n".join(gardees)


def _est_un_print(noeud: ast.stmt) -> bool:
    """Dit si une instruction est déjà un appel à `print`."""
    return (
        isinstance(noeud, ast.Expr)
        and isinstance(noeud.value, ast.Call)
        and isinstance(noeud.value.func, ast.Name)
        and noeud.value.func.id == "print"
    )


def _afficher_les_expressions(code: str) -> str:
    """
    Enveloppe dans `print()` les expressions laissées seules.

    Compétence visée : C17 (épreuve E4)

    Au prompt, écrire `furniture[0]` affiche la valeur ; dans un script, cela
    ne montre rien. Sans cette étape, convertir une session donnerait un code
    qui s'exécute sans rien afficher — techniquement réparé, inutile à lire.

    Choix : passer par l'arbre syntaxique plutôt que par une expression
    régulière. Motivation : distinguer une expression d'une affectation ou
    d'un `if` demande de comprendre la syntaxe, pas d'en reconnaître la forme.
    Une expression sur plusieurs lignes, une chaîne triple, un appel imbriqué :
    autant de cas qu'une regex traiterait mal, et en silence.

    Choix : en cas d'erreur de syntaxe, le code est rendu tel quel. Motivation :
    l'exécuteur signalera l'erreur bien mieux que ce module, et avec la ligne
    fautive. Deviner ici masquerait le vrai message.
    """
    try:
        arbre = ast.parse(code)
    except SyntaxError:
        return code

    lignes = code.splitlines()
    # À l'envers : envelopper une instruction décale les lignes suivantes.
    for noeud in reversed(arbre.body):
        if not isinstance(noeud, ast.Expr) or _est_un_print(noeud):
            continue
        debut, fin = noeud.lineno - 1, (noeud.end_lineno or noeud.lineno) - 1
        segment = "\n".join(lignes[debut:fin + 1])
        decalage = len(segment) - len(segment.lstrip())
        marge, corps = segment[:decalage], segment[decalage:]
        lignes[debut:fin + 1] = [f"{marge}print({corps})"]
    return "\n".join(lignes)


def transcrire(code: str) -> str:
    """
    Rend exécutable un extrait copié d'une session interactive.

    Compétence visée : C17 (épreuve E4)

    Un extrait qui n'est pas une session est rendu **inchangé** : c'est la
    garantie qui compte, puisque la même cellule sert au code tapé à la main.
    """
    if not ressemble_a_une_session(code):
        return code
    return _afficher_les_expressions(_lignes_de_code(code))
