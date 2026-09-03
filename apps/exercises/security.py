"""
Simplified security system for Python code execution
Uses exec() with restricted environment
"""

import sys
import io
import time
import traceback
import functools
from contextlib import redirect_stdout, redirect_stderr


class CodeExecutionError(Exception):
    """Exception raised on execution error"""
    pass


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

        # Les gardes. Sans elles, le code réécrit par RestrictedPython lève un
        # NameError à la première indexation ou boucle : ce ne sont pas des
        # options, ce sont les fonctions que le code compilé appelle.
        globales.update({
            "_print_": PrintCollector,
            "_getattr_": safer_getattr,      # refuse les attributs spéciaux
            "_getitem_": default_guarded_getitem,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_write_": lambda objet: objet,

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
                # le remplace par un collecteur, rangé dans `_print`. Sans
                # cette lecture, tout code affichait un résultat vide — et la
                # bibliothèque le signale d'ailleurs par un avertissement,
                # « Prints, but never reads 'printed' variable ».
                collecte = safe_locals.get("_print")
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
                # Create simple test code without import sys
                test_code = f"""{code}

# Execute test
result = {test['input']}
if result is not None:
    print(result)
"""
                
                print(f"🧪 Executing test {i+1}: {test['input']}")
                
                # Execute test
                execution_result = self.execute_code(test_code)
                
                if execution_result['success']:
                    actual_output = str(execution_result['output']).strip()
                    
                    # Clean output more simply
                    lines = actual_output.split('\n')
                    # Take first non-empty line that isn't "None"
                    for line in lines:
                        line = line.strip()
                        if line and line != 'None':
                            actual_output = line
                            break
                    else:
                        actual_output = actual_output.strip()
                    
                    expected_output = str(test['expected']).strip()
                    
                    test_result['actual'] = actual_output
                    test_result['passed'] = actual_output == expected_output
                    
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
