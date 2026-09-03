"""
L'exécuteur de code des exercices et de la cellule d'essai.

Compétence visée : C13 (épreuve E3) — sécurité
Compétences concernées : C17 (E4) ; C21 (E5)

Ces tests portent le motif de l'incident 018 : une liste blanche écrite à la
main n'est éprouvée que par les contournements auxquels son auteur a pensé.
Chacune des évasions ci-dessous **passait** avant le remplacement par
RestrictedPython, et deux d'entre elles rendaient des informations du serveur.
"""

import pytest

from apps.exercises.security import SecurePythonExecutor


@pytest.fixture
def executeur():
    return SecurePythonExecutor()


# --- Ce qui doit continuer de fonctionner ---------------------------------


@pytest.mark.parametrize("code,attendu", [
    ("print('bonjour')", "bonjour"),
    ("d = {'a': 1}\nfor k in sorted(d):\n    print(k, d[k])", "a 1"),
    ("print([x * x for x in range(4)])", "[0, 1, 4, 9]"),
    ("def double(n):\n    return n * 2\nprint(double(21))", "42"),
    ("import math\nprint(round(math.sqrt(16)))", "4"),
])
def test_le_code_legitime_s_execute_et_affiche(executeur, code, attendu):
    """
    Un apprenant doit pouvoir écrire du Python ordinaire.

    Compétence visée : C17 (épreuve E4)

    `print` ne va pas sur la sortie standard : RestrictedPython le remplace par
    un collecteur. Sans le lire, tout code affichait un résultat vide — et la
    bibliothèque le signalait par un avertissement que rien ne regardait.
    """
    resultat = executeur.execute_code(code)
    assert resultat["success"] is True, resultat["error"]
    assert attendu in resultat["output"]


# --- Ce qui ne doit pas passer --------------------------------------------


@pytest.mark.parametrize("nom,code", [
    ("import direct", "import os\nprint(os.getcwd())"),
    # Traversait le filtre textuel : il cherchait « import os » dans le source,
    # et un nom concaténé ne s'y trouve pas. Rendait le répertoire du serveur.
    ("import concaténé", "m = __import__('o' + 's')\nprint(m.getcwd())"),
    ("ouverture de fichier", "print(open('/etc/hostname').read())"),
    # Chaîne d'évasion classique : remonter aux sous-classes de `object` pour
    # y trouver de quoi lancer un processus.
    ("sous-classes", "print(().__class__.__base__.__subclasses__())"),
    ("attribut spécial", "print((1).__class__)"),
    ("exec", "exec('import os')"),
    ("eval", "eval('1+1')"),
])
def test_les_evasions_sont_refusees(executeur, nom, code):
    """
    Aucune de ces sept lignes ne doit s'exécuter.

    Compétence visée : C13 (épreuve E3) — sécurité

    Deux d'entre elles passaient avant le remplacement de la liste blanche
    maison. Le filtre lisait le **texte** du code ; RestrictedPython réécrit
    l'arbre syntaxique et fait passer chaque accès d'attribut par une garde.
    """
    resultat = executeur.execute_code(code)

    assert resultat["success"] is False, (
        "« %s » s'est exécuté : %r" % (nom, resultat["output"])
    )
    assert resultat["error"], "un refus doit être motivé"


def test_le_filtre_porte_sur_le_nom_du_module_pas_sur_le_texte(executeur):
    """
    C'est le point qui distingue les deux approches.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    Un nom de module concaténé arrive à l'importateur **déjà assemblé** : il
    n'y a plus rien à contourner. Un filtre qui lit le source, lui, ne voit que
    ce qui y est écrit.
    """
    from apps.exercises.security import CodeExecutionError

    with pytest.raises(CodeExecutionError):
        executeur._importateur_sur("os")
    with pytest.raises(CodeExecutionError):
        executeur._importateur_sur("subprocess")

    # Un module de la liste blanche passe, et c'est bien le vrai module.
    assert executeur._importateur_sur("math").sqrt(9) == 3


def test_aucun_filtre_textuel_ne_subsiste():
    """
    Le contrôle par lecture du source est retiré, pas doublé.

    Compétence visée : C21 (épreuve E5)

    Le laisser en place aurait donné une impression de défense supplémentaire
    là où il n'apportait rien : ce qui protège est la compilation restreinte.
    """
    from pathlib import Path

    source = Path("apps/exercises/security.py").read_text(encoding="utf-8")
    assert "Forbidden keyword detected" not in source
    assert "FORBIDDEN_MODULES" not in source
    assert "compile_restricted" in source


# --- Le vocabulaire ordinaire de Python, et ce qui reste dehors -----------

@pytest.mark.parametrize("nom", [
    "list", "dict", "sum", "min", "max", "enumerate", "map", "filter",
    "any", "all", "reversed", "type", "sorted", "zip", "range", "len",
])
def test_le_vocabulaire_ordinaire_repond(nom):
    """
    Les fonctions de base de Python sont disponibles dans la cellule.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3)

    Elles manquaient au 3 septembre : `print(list(...))` échouait sur
    « name 'list' is not defined ». Un cours sur les collections dont la
    cellule refuse `list` n'apprend rien, et l'apprenant conclut que c'est son
    code qui est faux. Aucune de ces fonctions ne donne accès au disque ni à
    l'introspection : elles construisent et parcourent des valeurs.
    """
    resultat = SecurePythonExecutor().execute_code(f"print({nom})")

    assert resultat["success"], resultat.get("error")


@pytest.mark.parametrize("nom", ["open", "input", "getattr",
                                 "globals", "vars", "dir", "eval", "exec"])
def test_ce_qui_ouvre_une_porte_reste_dehors(nom):
    """
    Élargir le vocabulaire ne rouvre pas ce qui était fermé.

    Compétence visée : C13 (épreuve E3) — sécurité

    `open` ouvre le système de fichiers ; `input` attendrait une saisie que
    personne ne peut fournir et bloquerait jusqu'au délai ; `eval`, `exec` et
    `compile` rouvriraient le chemin que `compile_restricted` ferme ;
    `getattr`, `dir` et `vars` contourneraient `safer_getattr`, la garde qui
    refuse les attributs spéciaux.

    `setattr` n'est pas dans cette liste : le nom RÉPOND, mais toute écriture
    d'attribut passe par la garde `_write_` du code compilé, qui refuse les
    objets intégrés (« attribute-less object »). Vérifié sur quatre tentatives,
    dont la réécriture de `__class__`. C'est une propriété de
    RestrictedPython, pas un choix de ce projet — l'inscrire ici ferait
    échouer un test sur un comportement que nous ne pilotons pas.
    """
    resultat = SecurePythonExecutor().execute_code(f"print({nom})")

    assert not resultat["success"], f"{nom} ne doit pas être joignable"


def test_un_module_importe_reste_visible_dans_une_fonction():
    """
    Un module importé dans le bloc est utilisable partout dans ce bloc.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    L'exécuteur passait deux espaces de noms distincts à `exec`. Un `import re`
    écrit au niveau du bloc atterrissait donc dans les locales, tandis qu'un
    corps de fonction ne résout que les globales : le module était importé et
    introuvable dès qu'on s'en servait. Un module Python s'exécute dans un
    espace unique ; l'exécuteur fait de même.
    """
    resultat = SecurePythonExecutor().execute_code(
        "import re\n"
        "def compter(texte):\n"
        "    return len(re.findall('a', texte))\n"
        "print(compter('banana'))"
    )

    assert resultat["success"], resultat.get("error")
    assert resultat["output"].strip() == "3"


def test_une_variable_du_bloc_reste_visible_dans_une_fonction():
    """
    Même cause, autre symptôme : une variable du bloc vue depuis une fonction.

    Compétence visée : C17 (épreuve E4)
    """
    resultat = SecurePythonExecutor().execute_code(
        "facteur = 3\n"
        "def multiplier(x):\n"
        "    return x * facteur\n"
        "print(multiplier(4))"
    )

    assert resultat["success"], resultat.get("error")
    assert resultat["output"].strip() == "12"
