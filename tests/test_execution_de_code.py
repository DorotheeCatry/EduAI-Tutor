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
