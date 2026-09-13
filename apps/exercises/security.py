"""
Simplified security system for Python code execution
Uses exec() with restricted environment
"""

import ast
import sys
import io
import operator
import time
import traceback
import functools
from contextlib import redirect_stdout, redirect_stderr


class CodeExecutionError(Exception):
    """Exception raised on execution error"""
    pass


#: Préfixe de la ligne qui porte le résultat d'un test, dans la sortie du code.
#:
#: Compétence visée : C17 (épreuve E4), C21 (E5)
#:
#: Il sépare ce que le code de l'apprenant a AFFICHÉ de ce que sa fonction a
#: RENDU. Avant lui, le lanceur prenait « la première ligne non vide qui ne vaut
#: pas None » : un exercice qui appelle `print` dans son corps voyait donc sa
#: propre sortie comparée au résultat attendu, et une fonction rendant `None`
#: n'était pas distinguable d'une fonction qui n'avait rien produit.
#:
#: Le nom est volontairement improbable dans du code d'apprenant. S'il venait
#: malgré tout à être imprimé par la soumission, la conséquence serait un test
#: faussement réussi ou faussement échoué — jamais une faille : la marque ne
#: sert qu'à lire une sortie, elle n'accorde aucun droit.
MARQUE_RESULTAT = "__RESULT__="

#: Clé sous laquelle l'exécuteur range le collecteur de sorties partagé.
#:
#: Compétence visée : C13 (épreuve E3), C17 (E4)
#:
#: Elle commence par un tiret bas, et c'est délibéré : RestrictedPython refuse
#: à la compilation tout identifiant qui en porte un, si bien qu'aucun code
#: d'apprenant ne peut désigner ce nom — ni le lire, ni l'écraser.
CLE_COLLECTEUR = "_collecteur_de_sorties_"

#: Nom de la variable qui porte le résultat dans le code de test assemblé.
#:
#: **Il ne peut pas commencer par un tiret bas.** RestrictedPython refuse à la
#: compilation tout identifiant qui en porte un — « is an invalid variable name
#: because it starts with "_" » — et cette règle vaut aussi pour le code que le
#: lanceur assemble lui-même. Un nom en `__resultat__` faisait donc échouer
#: TOUS les tests, sur un message parlant d'une variable que l'apprenant n'a
#: jamais écrite.
#:
#: Le préfixe `eduai_` suffit à écarter la collision : un apprenant qui nomme
#: ainsi sa propre variable l'a cherché, et la conséquence serait un résultat
#: faux, jamais une faille.
VARIABLE_RESULTAT = "eduai_resultat_du_test"


#: Les opérateurs qu'une affectation augmentée peut employer dans la cellule.
#:
#: Compétence visée : C13 (épreuve E3) — sécurité
#: Compétence concernée : C17 (E4)
#:
#: Choix : une table explicite plutôt que `eval` ou `getattr(operator, ...)` sur
#: le symbole reçu. Motivation : le symbole vient du code réécrit, donc
#: indirectement de l'apprenant. Une table close ne peut rendre que ces
#: treize fonctions ; une résolution dynamique sur `operator` exposerait tout ce
#: que ce module contient.
#:
#: Ce qui est dedans : l'arithmétique et la concaténation, c'est-à-dire ce
#: qu'un exercice de programmation demande. Ce qui reste dehors : `@=`, le
#: produit matriciel, sans objet ici.
#:
#: === ÉCART DE COMPORTEMENT À CONNAÎTRE AVANT D'ÉCRIRE UN EXERCICE ===
#:
#: La table emploie les formes **non mutantes** d'`operator` — `add` et non
#: `iadd`. Une affectation augmentée sur un conteneur mutable **rend donc un
#: nouvel objet au lieu de modifier l'original**, et l'aliasing ne se comporte
#: pas comme en Python réel. Mesuré :
#:
#:     a = [1]; b = a; b += [2]
#:
#:     Python réel   →  a == [1, 2]   b == [1, 2]   a is b  →  True
#:     Bac à sable   →  a == [1]      b == [1, 2]   a is b  →  False
#:
#: L'écart vaut pour `+=` sur une liste, `|=` sur un dictionnaire ou un
#: ensemble, et toute autre affectation augmentée sur un objet mutable. Il ne
#: vaut PAS pour les méthodes mutantes : `b.append(2)` et `b.extend([2])`
#: modifient bien l'objet partagé, ici comme ailleurs.
#:
#: **Conséquence pratique : ne pas écrire d'exercice qui enseigne ou éprouve
#: l'aliasing par affectation augmentée.** Il donnerait, dans cette cellule,
#: une réponse contraire à celle qu'un apprenant obtiendrait dans son propre
#: interpréteur — c'est-à-dire qu'il enseignerait le faux. Pour montrer
#: l'aliasing, employer `append` ou `extend`, qui sont fidèles.
#:
#: Ce choix n'est pas corrigé aujourd'hui, et c'est assumé : les formes
#: mutantes d'`operator` modifient un objet en place, ce qui demande d'examiner
#: ce qu'on accepte de laisser muter dans un bac à sable. La question mérite
#: d'être traitée pour elle-même plutôt qu'en marge d'un correctif. Voir
#: l'incident 021, section 7.
OPERATEURS_AUGMENTES = {
    "+=": operator.add,
    "-=": operator.sub,
    "*=": operator.mul,
    "/=": operator.truediv,
    "//=": operator.floordiv,
    "%=": operator.mod,
    "**=": operator.pow,
    "<<=": operator.lshift,
    ">>=": operator.rshift,
    "|=": operator.or_,
    "&=": operator.and_,
    "^=": operator.xor,
}


def garde_affectation_augmentee(symbole, cible, valeur):
    """
    Applique une affectation augmentée — la garde `_inplacevar_`.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    **Pourquoi elle est écrite ici et non importée.** RestrictedPython réécrit
    `total += 1` en `total = _inplacevar_('+=', total, 1)`, mais **ne fournit
    aucune implémentation de ce nom** : vérifié dans la version 8.1 installée,
    `_inplacevar_` n'apparaît que dans `transformer.py`, à l'endroit qui l'émet.
    Ni `Guards`, ni `Utilities`, ni `Eval` ne le définissent. La bibliothèque
    laisse délibérément cette fonction à l'hôte — Zope a la sienne.

    **Le défaut que son absence produisait.** Toute affectation augmentée levait
    `NameError: name '_inplacevar_' is not defined`, sur un nom que l'apprenant
    n'a jamais écrit. `t += 1`, `s += 'a'`, `n *= 2` : aucun ne fonctionnait,
    dans un cours de programmation où c'est la construction la plus courante
    après l'affectation simple. Voir l'incident 021.

    Choix : lever `ValueError` sur un symbole absent de la table, plutôt que de
    retomber sur une valeur par défaut. Motivation : un symbole inconnu signifie
    que la bibliothèque a évolué et émet un opérateur que cette table ignore.
    Échouer bruyamment le dit ; rendre `valeur` silencieusement produirait un
    résultat faux que rien ne signalerait.
    """
    fonction = OPERATEURS_AUGMENTES.get(symbole)
    if fonction is None:
        raise ValueError(
            f"Opérateur d'affectation augmentée non autorisé : {symbole}"
        )
    return fonction(cible, valeur)


class SecurePythonExecutor:
    """Simplified and secure Python executor"""
    
    # Allowed functions (whitelist)
    # Les deux listes qui vivaient ici — fonctions autorisées et modules
    # interdits — sont supprimées avec le filtre textuel qu'elles servaient.
    # Les conserver aurait laissé croire à une défense qui ne s'exécute plus
    # (incident 018). La liste blanche des modules vit désormais dans
    # `MODULES_AUTORISES`, et elle est consultée à l'import, pas à la lecture
    # du source.

    def __init__(self, timeout=5):
        self.timeout = timeout
    
    #: Modules autorisés à l'import, par leur nom exact. Une liste blanche de
    #: modules reste nécessaire — RestrictedPython encadre le langage, pas le
    #: choix des bibliothèques.
    MODULES_AUTORISES = {
        "math", "random", "statistics", "string", "datetime",
        "itertools", "functools", "collections", "re", "json", "decimal",
    }

    def _importateur_sur(self, nom, globales=None, locales=None,
                         depuis=(), niveau=0):
        """
        Remplace `__import__` par une liste blanche de modules.

        Compétence visée : C13 (épreuve E3) — sécurité

        Choix : filtrer le NOM DU MODULE au moment de l'import, et non le texte
        du code. Motivation : le filtre précédent lisait les lignes du source à
        la recherche de « import os ». `__import__('o' + 's')` le traversait
        sans être vu, et rendait le répertoire de travail du serveur — vérifié.
        Un nom concaténé arrive ici déjà assemblé : il n'y a plus rien à
        contourner.
        """
        racine = nom.split(".")[0]
        if racine not in self.MODULES_AUTORISES:
            raise CodeExecutionError(
                f"Module non autorisé : {racine}. "
                f"Disponibles : {', '.join(sorted(self.MODULES_AUTORISES))}."
            )
        return __import__(nom, globales, locales, depuis, niveau)

    def _create_safe_globals(self):
        """
        Construit l'environnement d'exécution, sur RestrictedPython.

        Compétence visée : C13 (épreuve E3) — sécurité

        Choix : RestrictedPython plutôt qu'une liste blanche maison.
        Motivation : la liste maison était contournable, et deux évasions ont
        été constatées avant de la remplacer —

            __import__('o' + 's').getcwd()          → chemin du serveur
            (1).__class__.__base__.__subclasses__() → chaîne d'évasion classique

        La première passait parce que le filtre lisait le TEXTE du code ; la
        seconde parce que rien n'encadrait l'accès aux attributs. RestrictedPython
        traite les deux à la racine : il réécrit l'arbre syntaxique avant
        compilation et fait passer chaque accès par une garde.

        C'est une bibliothèque de la Zope Foundation, employée depuis vingt ans
        et auditée — là où une liste blanche maison n'est éprouvée que par les
        contournements auxquels son auteur a pensé.
        """
        import builtins

        from RestrictedPython import safe_globals, utility_builtins
        from RestrictedPython.Eval import (
            default_guarded_getitem,
            default_guarded_getiter,
        )
        from RestrictedPython.Guards import (
            guarded_iter_unpack_sequence,
            guarded_unpack_sequence,
            safer_getattr,
        )
        from RestrictedPython.PrintCollector import PrintCollector

        globales = dict(safe_globals)
        globales["__builtins__"] = dict(globales.get("__builtins__", {}))
        globales["__builtins__"].update(utility_builtins)
        globales["__builtins__"]["__import__"] = self._importateur_sur

        # Le vocabulaire ordinaire de Python, absent de `safe_globals`.
        #
        # Compétence visée : C13 (épreuve E3)
        # Compétence concernée : C17 (E4)
        #
        # Motivation mesurée : `list`, `dict`, `sum`, `min`, `max`, `enumerate`,
        # `map`, `filter`, `any`, `all`, `reversed` et `type` ne répondaient pas.
        # Un cours sur les collections dont `print(list(...))` échoue n'apprend
        # rien, et l'apprenant conclut que c'est son code qui est faux.
        #
        # Ce que ces noms ne donnent pas : ni accès au disque, ni introspection.
        # Ils construisent et parcourent des valeurs, rien d'autre. Restent
        # dehors, et le restent :
        #   `open` et `input`   — l'un ouvre le système de fichiers, l'autre
        #                         attendrait une saisie que personne ne peut
        #                         fournir et bloquerait jusqu'au délai ;
        #   `eval`, `exec`, `compile` — ils rouvriraient un chemin que
        #                         `compile_restricted` vient de fermer ;
        #   `getattr`, `setattr`, `dir`, `vars`, `globals` — l'accès aux
        #                         attributs passe par `safer_getattr`, qui
        #                         refuse les attributs spéciaux. Les rendre
        #                         directement rendrait cette garde inutile.
        for nom in ("list", "dict", "sum", "min", "max", "enumerate", "map",
                    "filter", "any", "all", "reversed", "type", "iter", "next",
                    "frozenset", "divmod", "pow", "format", "repr", "ascii",
                    "bin", "oct", "hex", "chr", "ord", "id", "callable"):
            valeur = getattr(builtins, nom, None)
            if valeur is not None:
                globales["__builtins__"][nom] = valeur

        # UN SEUL collecteur de sorties, partagé par toutes les portées.
        #
        # Compétence visée : C17 (épreuve E4), C21 (E5)
        #
        # **Le défaut que cela corrige.** RestrictedPython injecte
        # `_print = _print_(_getattr_)` en tête de CHAQUE portée qui emploie
        # `print` — le module, mais aussi chaque fonction. Avec `PrintCollector`
        # pour fabrique, chacune recevait donc son propre collecteur, et
        # l'exécuteur ne lisait que celui du module. **Tout `print` appelé
        # depuis une fonction était perdu**, et l'apprenant lisait « Exécuté
        # sans rien afficher, pensez à print() » pour un code qui affichait
        # bien (incident 022).
        #
        # La fabrique rend ici toujours la même instance. Les portées
        # imbriquées écrivent dans le même tampon, dans l'ordre des appels, et
        # l'exécuteur n'a plus qu'un endroit à lire.
        #
        # L'instance est créée à chaque appel de cette méthode, donc à chaque
        # exécution : deux exécutions successives ne partagent rien.
        collecteur = PrintCollector(safer_getattr)

        # Les gardes. Sans elles, le code réécrit par RestrictedPython lève un
        # NameError à la première indexation ou boucle : ce ne sont pas des
        # options, ce sont les fonctions que le code compilé appelle.
        globales.update({
            CLE_COLLECTEUR: collecteur,
            # La fabrique ignore le `_getattr_` que le code réécrit lui passe :
            # le collecteur a déjà le sien, et c'est le même.
            "_print_": lambda _getattr_=None: collecteur,
            "_getattr_": safer_getattr,      # refuse les attributs spéciaux
            "_getitem_": default_guarded_getitem,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_write_": lambda objet: objet,

            # `_inplacevar_` : la garde des affectations augmentées.
            #
            # Compétence visée : C13 (épreuve E3), C21 (E5)
            # Elle manquait, et c'était la SEULE des dix que cette version de
            # RestrictedPython peut émettre. Relevé fait sur le transformeur
            # installé plutôt qu'au jugé : `_apply_`, `_getattr_`, `_getitem_`,
            # `_getiter_`, `_inplacevar_`, `_iter_unpack_sequence_`, `_print_`,
            # `_unpack_sequence_`, `_write_` et `__metaclass__`. Neuf étaient
            # définies ici, la dixième non — et son absence faisait échouer
            # `total += 1` (incident 021).
            #
            # Elle n'est pas importée : la bibliothèque émet l'appel et laisse
            # l'implémentation à l'hôte. Voir `garde_affectation_augmentee`.
            "_inplacevar_": garde_affectation_augmentee,

            # Deux noms que RestrictedPython attend dans les globales, sans
            # lesquels des constructions parfaitement ordinaires échouent.
            #
            # Compétence visée : C13 (épreuve E3)
            # Compétence concernée : C17 (E4)
            #
            # `__metaclass__` : sans lui, TOUTE définition de classe échoue sur
            # « name '__metaclass__' is not defined ». Un cours sur les objets
            # devenait inexécutable en entier — et le message ne désignait rien
            # que l'apprenant puisse comprendre ni corriger.
            #
            # `_apply_` : le code réécrit y passe pour tout appel à arguments
            # dépliés, `f(*args)` ou `f(**kwargs)`. Sans lui, ces appels lèvent
            # un NameError sur un nom que l'apprenant n'a jamais écrit.
            #
            # Ni l'un ni l'autre n'élargit ce qui est joignable : le premier
            # nomme la métaclasse par défaut, le second rappelle la fonction
            # que le code désignait déjà.
            "__metaclass__": type,
            # Le code compilé lit `__name__` au moment de créer une classe : il
            # y range le module d'origine. La cellule n'est pas un module, on y
            # met donc un nom qui le dit.
            "__name__": "cellule",
            "_apply_": lambda fonction, *args, **kwargs: fonction(*args, **kwargs),
        })
        return globales

    def _validate_code(self, code):
        """
        Conservée pour l'interface, la validation se fait à la compilation.

        Compétence visée : C13 (épreuve E3)

        Le contrôle textuel qui vivait ici est supprimé : il donnait une
        impression de protection que deux lignes suffisaient à démentir. Ce qui
        protège désormais est `compile_restricted`, dont le refus est une
        erreur de compilation, et l'importateur ci-dessus.
        """
        return None

    def execute_code(self, code, test_input=None):
        """
        Executes code securely
        
        Args:
            code (str): Python code to execute
            test_input (str): Optional input for code
            
        Returns:
            dict: Execution result with output, errors, etc.
        """
        result = {
            'success': False,
            'output': '',
            'error': '',
            'execution_time': 0,
            'timeout': False
        }
        
        start_time = time.time()
        
        try:
            # Validate code
            self._validate_code(code)
            
            # Compile code
            try:
                from RestrictedPython import compile_restricted
                compiled_code = compile_restricted(
                    code, '<code apprenant>', 'exec')
            except SyntaxError as e:
                # RestrictedPython refuse par une SyntaxError : un accès à un
                # attribut spécial ou une construction interdite n'atteint
                # jamais l'exécution.
                raise CodeExecutionError(f"Code refusé : {str(e)}")
            
            # Create secure execution environment
            safe_globals = self._create_safe_globals()
            # Choix : UN SEUL espace de noms, passé à la fois en globales et en
            # locales.
            #
            # Compétence visée : C13 (épreuve E3)
            # Motivation mesurée : avec deux espaces distincts, un `import re`
            # écrit au niveau du bloc atterrit dans les LOCALES, tandis qu'un
            # corps de fonction ne résout que les GLOBALES. Le module était donc
            # importé et introuvable dès qu'on s'en servait dans une fonction —
            # `name 're' is not defined` sur un code parfaitement valide. Le
            # relevé du 3 septembre comptait 54 blocs de cours perdus par ce
            # seul mécanisme. Un module Python s'exécute dans un espace unique ;
            # l'exécuteur fait désormais de même.
            safe_locals = safe_globals
            
            # Capture outputs
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            try:
                with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                    exec(compiled_code, safe_globals, safe_locals)
                
                # `print` ne va pas sur la sortie standard : RestrictedPython
                # le remplace par un collecteur. Sans cette lecture, tout code
                # affichait un résultat vide — et la bibliothèque le signale
                # d'ailleurs par un avertissement, « Prints, but never reads
                # 'printed' variable ».
                #
                # On lit le collecteur PARTAGÉ, et non la variable `_print` de
                # l'espace de noms du module.
                #
                # Compétence visée : C17 (épreuve E4), C21 (E5)
                # Motivation constatée : `_print` est injecté par portée. Celui
                # du module ne porte que les `print` écrits au premier niveau ;
                # ceux d'une fonction vivaient dans une variable locale que
                # rien ne lisait. Et quand un code n'imprime QUE depuis des
                # fonctions, le module n'a même pas de `_print` — la lecture
                # rendait alors `None` sur un code qui avait tout affiché.
                # Voir `_create_safe_globals` et l'incident 022.
                collecte = safe_globals.get(CLE_COLLECTEUR)
                imprime = collecte() if collecte is not None else ""
                result['output'] = output_buffer.getvalue() + imprime
                result['success'] = True
                    
            except Exception as e:
                # Capture actual exception type
                result['exception_type'] = type(e).__name__
                
                error_output = error_buffer.getvalue()
                if error_output:
                    result['error'] = f"Execution error: {error_output}"
                else:
                    result['error'] = f"Execution error: {str(e)}"
                
        except CodeExecutionError as e:
            result['error'] = str(e)
            
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
            
        finally:
            result['execution_time'] = time.time() - start_time
            
        return result
    
    @staticmethod
    def _extraire_le_resultat(sortie: str) -> tuple[str, bool]:
        """
        Rend le résultat porté par la ligne marquée, et dit s'il a été trouvé.

        Compétence visée : C17 (épreuve E4), C21 (E5)

        Choix : la DERNIÈRE ligne marquée, pas la première. Motivation : le code
        de l'apprenant est exécuté avant l'appel de test ; s'il imprimait
        lui-même quelque chose portant la marque, c'est tout de même le résultat
        du test qui doit primer, et il est imprimé en dernier.

        Choix : rendre un couple plutôt qu'une chaîne vide. Motivation :
        « la fonction a rendu la chaîne vide » et « aucun résultat n'a été
        produit » sont deux états différents, et les confondre est exactement le
        défaut que ce chantier corrige. Le drapeau les sépare.
        """
        for ligne in reversed(sortie.splitlines()):
            ligne = ligne.strip()
            if ligne.startswith(MARQUE_RESULTAT):
                return ligne[len(MARQUE_RESULTAT):].strip(), True
        return "", False

    @staticmethod
    def _concorde(obtenu: str, attendu: str) -> bool:
        """
        Dit si le résultat obtenu correspond à celui qu'annonce le test.

        Compétence visée : C17 (épreuve E4)

        `obtenu` est un `repr`, `attendu` est écrit à la main dans l'énoncé de
        l'exercice. Les deux ne s'écrivent donc pas pareil : un exercice qui
        attend `55` sera comparé à `'55'`, et un qui attend `Hello` à
        `"'Hello'"`.

        Choix : comparer d'abord les `repr`, et retomber sur le texte brut.
        Motivation : la comparaison sur `repr` est celle qui distingue `None` de
        `'None'` et `1` de `'1'` — c'est elle qui rend le dispositif juste. Mais
        les énoncés existants écrivent `55`, pas `'55'` : exiger le `repr` des
        deux côtés ferait échouer tous les exercices déjà en base. On accepte
        donc les deux écritures, et l'on documente que la forme `repr` est celle
        qui tranche les cas ambigus.
        """
        obtenu, attendu = obtenu.strip(), attendu.strip()
        if obtenu == attendu:
            return True
        # `attendu` écrit sans guillemets : on le compare à sa forme `repr`.
        try:
            return obtenu == repr(ast.literal_eval(attendu))
        except (ValueError, SyntaxError):
            # `attendu` n'est pas un littéral Python — un texte libre. On le
            # compare alors au résultat débarrassé de ses guillemets.
            try:
                return ast.literal_eval(obtenu) == attendu
            except (ValueError, SyntaxError):
                return False

    def run_tests(self, code, tests):
        """
        Executes a series of tests on the code
        
        Args:
            code (str): Python code to test
            tests (list): List of tests to execute
            
        Returns:
            list: Test results
        """
        test_results = []
        
        for i, test in enumerate(tests):
            test_result = {
                'test_number': i + 1,
                'input': test.get('input', ''),
                'expected': str(test.get('expected', '')),
                'actual': '',
                'passed': False,
                'error': ''
            }
            
            try:
                # Le résultat est imprimé sur une LIGNE MARQUÉE, toujours.
                #
                # Compétence visée : C17 (épreuve E4), C21 (E5)
                #
                # Le code posé ici était `if result is not None: print(result)`.
                # Une fonction qui rend `None` n'imprimait donc rien, et le
                # nettoyage de sortie écartait par ailleurs toute ligne valant
                # « None ». Double verrou : **un test attendant `None` ne
                # pouvait jamais passer**, et l'apprenant lisait « Aucune
                # sortie » pour une fonction qui avait pourtant répondu.
                #
                # La marque sépare ce que le code de l'apprenant a AFFICHÉ de ce
                # que sa fonction a RENDU. Un exercice qui appelle `print` dans
                # son corps — ce qui est fréquent, et légitime — brouillait
                # sinon la lecture : la première ligne non vide était la
                # sienne, pas le résultat.
                test_code = f"""{code}

# Execute test
{VARIABLE_RESULTAT} = {test['input']}
print({MARQUE_RESULTAT!r} + repr({VARIABLE_RESULTAT}))
"""

                print(f"🧪 Executing test {i+1}: {test['input']}")
                
                # Execute test
                execution_result = self.execute_code(test_code)
                
                if execution_result['success']:
                    actual_output, trouve = self._extraire_le_resultat(
                        str(execution_result['output']))

                    if not trouve:
                        # La marque manque : le code a été exécuté mais n'a
                        # produit aucun résultat — une soumission qui ne
                        # définit pas la fonction appelée, par exemple.
                        test_result['error'] = (
                            "Le test n'a produit aucun résultat : la fonction "
                            "attendue est-elle bien définie ?"
                        )
                        test_results.append(test_result)
                        continue

                    expected_output = str(test['expected']).strip()

                    test_result['actual'] = actual_output
                    test_result['passed'] = self._concorde(
                        actual_output, expected_output)
                    
                    print(f"   Expected: {expected_output}")
                    print(f"   Got: {actual_output}")
                    print(f"   Result: {'✅' if test_result['passed'] else '❌'}")
                    
                    if not test_result['passed']:
                        test_result['error'] = f"Attendu: {expected_output}, Obtenu: {actual_output}"
                else:
                    # Handle expected errors (like TypeError, ValueError)
                    error_msg = execution_result['error']
                    expected_output = str(test['expected']).strip()
                    
                    # If expected error is in expected result, it's a success
                    if any(error_type in expected_output for error_type in ['TypeError', 'ValueError', 'Exception']):
                        # Extract real exception type from execution_result
                        actual_exception_type = execution_result.get('exception_type', '')
                        
                        # Check if error type matches
                        if ('TypeError' in expected_output and actual_exception_type == 'TypeError') or \
                           ('ValueError' in expected_output and actual_exception_type == 'ValueError') or \
                           ('Exception' in expected_output and actual_exception_type in ['TypeError', 'ValueError', 'Exception']):
                            test_result['passed'] = True
                            test_result['actual'] = expected_output
                            print("   Expected: Error")
                            print("   Got: Error raised correctly")
                            print("   Result: ✅")
                        else:
                            test_result['error'] = f"Expected error ({expected_output}) but got: {actual_exception_type or 'unknown error'}"
                            print(f"   Error: Expected error but got: {error_msg}")
                    else:
                        test_result['error'] = error_msg
                    print(f"   Erreur: {execution_result['error']}")
                    
            except Exception as e:
                test_result['error'] = f"Error during test: {str(e)}"
                print(f"   Exception: {str(e)}")
            
            test_results.append(test_result)
        
        return test_results


# Global executor instance
secure_executor = SecurePythonExecutor()
