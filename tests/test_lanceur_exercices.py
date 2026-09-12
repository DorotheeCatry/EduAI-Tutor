"""
Le lanceur de tests des exercices exécute, compare et dit ce qui a échoué.

Compétence visée : C21 (épreuve E5) — traitement des anomalies
Compétences concernées : C13 (E3) — bac à sable ; C17 (E4) ; C18 (E4)

Une soumission correcte échouait sur trois tests sur quatre, avec pour seule
explication « Aucune sortie ». Trois défauts distincts se cumulaient, et ce
sont les trois que ces tests défendent :

1. La garde `_inplacevar_` manquait, donc **toute affectation augmentée**
   levait une `NameError` sur un nom que l'apprenant n'a jamais écrit.
2. Le résultat n'était imprimé que `if result is not None`, et le nettoyage de
   sortie écartait les lignes valant « None » : **un test attendant `None` ne
   pouvait jamais passer**.
3. Le message d'erreur était calculé et jamais affiché, si bien qu'une erreur
   d'exécution se lisait comme une absence de sortie.

Voir l'incident 021.
"""

from pathlib import Path

import pytest

from apps.exercises.security import (
    MARQUE_RESULTAT,
    OPERATEURS_AUGMENTES,
    SecurePythonExecutor,
    garde_affectation_augmentee,
)

GABARIT = Path("apps/exercises/templates/exercises/exercise_detail.html")


@pytest.fixture
def executeur():
    return SecurePythonExecutor()


# --- 1. Les affectations augmentées fonctionnent ---------------------------


@pytest.mark.parametrize("code, attendu", [
    ("t = 0\nfor i in [1, 2, 3]:\n    t += i\nprint(t)", "6"),
    ("t = 10\nt -= 4\nprint(t)", "6"),
    ("t = 2\nt *= 3\nprint(t)", "6"),
    ("t = 7\nt //= 2\nprint(t)", "3"),
    ("s = 'a'\ns += 'b'\nprint(s)", "ab"),
])
def test_les_affectations_augmentees_s_executent(executeur, code, attendu):
    """
    `+=` et ses semblables fonctionnent dans le bac à sable.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    RestrictedPython réécrit `t += 1` en `t = _inplacevar_('+=', t, 1)` mais ne
    fournit aucune implémentation de ce nom — vérifié dans la version 8.1
    installée, où `_inplacevar_` n'apparaît que dans le transformeur qui
    l'émet. La garde manquait, et c'était la seule des dix que cette version
    peut émettre.

    Conséquence : la construction la plus courante après l'affectation simple
    échouait, dans une plateforme d'apprentissage de la programmation.
    """
    resultat = executeur.execute_code(code)

    assert resultat["success"], resultat["error"]
    assert str(resultat["output"]).strip() == attendu


def test_toutes_les_gardes_attendues_sont_definies(executeur):
    """
    Aucune des gardes que RestrictedPython peut émettre ne manque.

    Compétence visée : C13 (épreuve E3), C18 (E4)

    Le projet a découvert ces gardes une par une, au fil des pannes :
    `__metaclass__` sur une définition de classe, `_apply_` sur un appel à
    arguments dépliés, `_inplacevar_` sur un `+=`. Chacune levait une
    `NameError` portant un nom que l'apprenant n'a jamais écrit.

    La liste ci-dessous est le relevé fait sur le transformeur installé, et non
    une énumération de mémoire. Ce test échouera si une montée de version en
    ajoute une — ce qui est précisément le moment où il faut le savoir.
    """
    globales = executeur._create_safe_globals()

    for garde in ("_apply_", "_getattr_", "_getitem_", "_getiter_",
                  "_inplacevar_", "_iter_unpack_sequence_", "_print_",
                  "_unpack_sequence_", "_write_", "__metaclass__"):
        assert garde in globales, f"garde absente : {garde}"


def test_un_operateur_inconnu_leve_au_lieu_de_rendre_un_faux_resultat():
    """
    La garde échoue bruyamment sur un symbole qu'elle ne connaît pas.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    Un symbole absent de la table signifie que la bibliothèque a évolué.
    Retomber sur une valeur par défaut produirait un résultat faux que rien ne
    signalerait — exactement le motif des incidents de ce projet.
    """
    assert garde_affectation_augmentee("+=", 2, 3) == 5
    assert garde_affectation_augmentee("+=", "a", "b") == "ab"

    with pytest.raises(ValueError):
        garde_affectation_augmentee("@=", 2, 3)

    assert "@=" not in OPERATEURS_AUGMENTES, (
        "le produit matriciel n'a pas d'objet ici et reste dehors"
    )


def test_l_ecart_d_aliasing_par_affectation_augmentee_est_documente(executeur):
    """
    L'affectation augmentée sur un conteneur mutable ne mute PAS en place.

    Compétence visée : C13 (épreuve E3), C17 (E4), C21 (E5)

    **Ce test ne défend pas un comportement souhaitable : il épingle un écart
    connu**, pour qu'aucun exercice ne soit écrit qui le contredise.

    La garde emploie les formes non mutantes d'`operator` (`add`, pas `iadd`).
    Une affectation augmentée rend donc un nouvel objet :

        a = [1]; b = a; b += [2]

        Python réel   →  a == [1, 2]   a is b  →  True
        Bac à sable   →  a == [1]      a is b  →  False

    Un exercice qui enseignerait l'aliasing par `+=` donnerait ici une réponse
    contraire à celle qu'un apprenant obtient dans son propre interpréteur —
    c'est-à-dire qu'il enseignerait le faux. Pour montrer l'aliasing, employer
    `append` ou `extend`, qui sont fidèles, et que les deux dernières
    assertions vérifient.

    Si l'implémentation passe un jour aux formes mutantes, ce test échouera :
    c'est exactement le moment où la documentation du module et cette consigne
    d'écriture d'exercices devront être reprises.
    """
    # L'écart, sur les trois conteneurs concernés.
    ecart = executeur.execute_code(
        "a = [1]\nb = a\nb += [2]\nprint(a, b, a is b)")
    assert ecart["success"], ecart["error"]
    assert str(ecart["output"]).strip() == "[1] [1, 2] False", (
        "écart connu : `+=` sur une liste ne mute pas l'objet partagé"
    )

    dictionnaire = executeur.execute_code(
        "a = {'x': 1}\nb = a\nb |= {'y': 2}\nprint(a, a is b)")
    assert str(dictionnaire["output"]).strip() == "{'x': 1} False"

    # Ce qui reste FIDÈLE à Python : les méthodes mutantes.
    for methode, appel in (("append", "b.append(2)"), ("extend", "b.extend([2])")):
        fidele = executeur.execute_code(
            f"a = [1]\nb = a\n{appel}\nprint(a, a is b)")
        assert str(fidele["output"]).strip() == "[1, 2] True", (
            f"`{methode}` doit muter l'objet partagé, comme en Python réel"
        )


def test_l_ecart_d_aliasing_est_ecrit_dans_le_module():
    """
    L'écart est signalé là où on écrit un exercice, pas seulement dans un test.

    Compétence visée : C17 (épreuve E4), C19 (E5)

    Un écart connu de personne est un piège ; un écart écrit à côté du code qui
    le produit est une contrainte de conception. Quelqu'un qui ouvre le module
    pour comprendre le bac à sable doit le lire sans avoir à exécuter quoi que
    ce soit.
    """
    source = Path("apps/exercises/security.py").read_text(encoding="utf-8")

    assert "aliasing" in source.lower(), (
        "l'écart doit être nommé dans le module qui le produit"
    )
    assert "a is b" in source, "avec le cas mesuré qui le montre"
    assert "append" in source, "et l'alternative fidèle à employer"


# --- 2. Un test attendant None passe ---------------------------------------


def test_un_test_attendant_none_peut_passer(executeur):
    """
    Une fonction qui rend `None` est distinguée d'une absence de résultat.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le code de test posait `if result is not None: print(result)`, et le
    nettoyage de sortie écartait par ailleurs toute ligne valant « None ».
    Double verrou : un test attendant `None` ne pouvait pas passer, et
    l'apprenant lisait « Aucune sortie » pour une fonction qui avait répondu.
    """
    code = "def f(n):\n    if n < 0:\n        return None\n    return n\n"

    resultats = executeur.run_tests(code, [
        {"input": "f(-3)", "expected": "None"},
        {"input": "f(2)", "expected": "2"},
    ])

    assert resultats[0]["actual"] == "None", "le None rendu est visible"
    assert resultats[0]["passed"], "un test attendant None doit pouvoir passer"
    assert resultats[1]["passed"]


def test_le_resultat_est_lu_sur_sa_ligne_marquee_et_non_sur_un_print(executeur):
    """
    Ce que la fonction affiche ne se confond pas avec ce qu'elle rend.

    Compétence visée : C17 (épreuve E4)

    Le lanceur prenait « la première ligne non vide qui ne vaut pas None ». Un
    exercice dont la fonction appelle `print` — ce qui est fréquent et
    légitime — voyait donc sa propre trace comparée au résultat attendu.
    """
    code = "def f():\n    print('trace de l apprenant')\n    return 42\n"

    resultat = executeur.run_tests(code, [{"input": "f()", "expected": "42"}])[0]

    assert resultat["actual"] == "42"
    assert resultat["passed"]

    # La marque est bien ce qui porte le résultat, et non une convention tacite.
    assert MARQUE_RESULTAT.startswith("__"), "la marque doit être improbable"


@pytest.mark.parametrize("rendu, attendu", [
    ("'Hello'", "Hello"),      # l'énoncé écrit la chaîne sans guillemets
    ("'Hello'", "'Hello'"),    # ou avec, les deux sont acceptés
    ("[1, 2]", "[1, 2]"),
    ("''", "''"),
    ("True", "True"),
    ("2.0", "2.0"),
])
def test_la_comparaison_accepte_les_deux_ecritures(executeur, rendu, attendu):
    """
    Le `repr` tranche, sans faire échouer les énoncés déjà écrits.

    Compétence visée : C17 (épreuve E4)

    La comparaison sur `repr` est celle qui distingue `None` de `'None'` et `1`
    de `'1'`. Mais les énoncés en base écrivent `55`, pas `'55'` : exiger le
    `repr` des deux côtés les ferait tous échouer.
    """
    code = f"def f():\n    return {rendu}\n"

    resultat = executeur.run_tests(code, [{"input": "f()", "expected": attendu}])[0]

    assert resultat["passed"], f"{rendu} devrait concorder avec {attendu}"


# --- 3. Une erreur d'exécution remonte jusqu'à l'affichage ------------------


def test_une_erreur_d_execution_remonte_dans_le_resultat(executeur):
    """
    Le message dit ce qui a échoué, au lieu de laisser une case vide.

    Compétence visée : C21 (épreuve E5), C17 (E4)

    C'est ce défaut qui a coûté le plus cher au diagnostic : la cause était
    calculée, rangée dans `error`, et jamais lue. L'apprenant voyait « Aucune
    sortie » — c'est-à-dire rien — pour une `NameError` que le serveur
    connaissait.
    """
    resultats = executeur.run_tests("x = 1\n", [{"input": "g()", "expected": "3"}])

    resultat = resultats[0]
    assert not resultat["passed"]
    assert resultat["error"], "l'échec doit porter un message"
    assert "g" in resultat["error"], (
        "le message doit désigner la cause, pas une formule générale"
    )

    division = executeur.run_tests(
        "def f():\n    return 1 / 0\n", [{"input": "f()", "expected": "1"}])[0]
    assert "division" in division["error"].lower()


def test_le_gabarit_affiche_le_message_d_erreur():
    """
    L'erreur transmise par le serveur est rendue à l'écran.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Le lanceur remplissait `error` pour chaque test depuis l'origine, et le
    gabarit ne lisait que `result.actual`. Ce test tient sur la source du
    gabarit : c'est le seul endroit du dépôt où l'oubli se verrait.
    """
    source = GABARIT.read_text(encoding="utf-8")

    assert "result.error" in source, (
        "le message d'erreur du test doit être lu par le gabarit"
    )
    assert "test-error-message" in source, "et rendu dans un élément dédié"
    assert "result.actual || 'Aucune sortie'" not in source, (
        "l'ancien repli masquait l'erreur derrière une absence de sortie"
    )


# --- Le cas signalé, de bout en bout ---------------------------------------


def test_l_exercice_de_la_somme_des_chiffres_passe_entierement(executeur):
    """
    La soumission signalée le 12/09/2026 passe ses quatre tests.

    Compétence visée : C21 (épreuve E5)

    Elle en échouait trois sur quatre, avec « Aucune sortie » pour seule
    explication. Le seul qui passait — `n = 0` — était le seul où le corps de
    boucle ne s'exécute pas, donc le seul qui n'atteignait jamais le `+=`.
    """
    code = (
        "def total_digit_sum(n):\n"
        "    if n < 0:\n"
        "        return None\n"
        "    total = 0\n"
        "    for nombre in range(1, n + 1):\n"
        "        for chiffre in str(nombre):\n"
        "            total += int(chiffre)\n"
        "    return total\n"
    )

    resultats = executeur.run_tests(code, [
        {"input": "total_digit_sum(13)", "expected": "55"},
        {"input": "total_digit_sum(5)", "expected": "15"},
        {"input": "total_digit_sum(0)", "expected": "0"},
        {"input": "total_digit_sum(-3)", "expected": "None"},
    ])

    echecs = [r for r in resultats if not r["passed"]]
    assert not echecs, f"tests encore en échec : {echecs}"
