"""
Système de sécurité pour l'exécution de code Python
Utilise RestrictedPython pour créer un environnement d'exécution sécurisé
"""

import sys
import io
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_globals, safe_builtins
from RestrictedPython.transformer import RestrictingNodeTransformer


class TimeoutException(Exception):
    """Exception levée en cas de timeout"""
    pass


class CodeExecutionError(Exception):
    """Exception levée en cas d'erreur d'exécution"""
    pass


class SecurePythonExecutor:
    """Exécuteur Python sécurisé utilisant RestrictedPython"""
    
    # Timeout par défaut (5 secondes)
    DEFAULT_TIMEOUT = 5
    
    # Fonctions autorisées (whitelist)
    ALLOWED_BUILTINS = {
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod',
        'enumerate', 'filter', 'float', 'format', 'frozenset', 'hex',
        'int', 'len', 'list', 'map', 'max', 'min', 'oct', 'ord',
        'pow', 'range', 'reversed', 'round', 'set', 'sorted', 'str',
        'sum', 'tuple', 'type', 'zip', 'print'
    }
    
    # Modules interdits (blacklist)
    FORBIDDEN_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
        'shutil', 'glob', 'pickle', 'marshal', 'shelve', 'dbm',
        'sqlite3', 'threading', 'multiprocessing', 'ctypes',
        'importlib', '__import__', 'eval', 'exec', 'compile',
        'open', 'file', 'input', 'raw_input'
    }
    
    def __init__(self, timeout=None):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
    
    def _safe_print(self, *args, **kwargs):
        """Fonction print sécurisée pour RestrictedPython"""
        # Convertir tous les arguments en string et les joindre
        output = ' '.join(str(arg) for arg in args)
        # Ajouter un retour à la ligne si end n'est pas spécifié
        if kwargs.get('end', '\n') == '\n':
            output += '\n'
        return output
    
    def _create_safe_globals(self):
        """Crée un environnement global sécurisé"""
        # Commencer avec les globals sécurisés de RestrictedPython
        safe_globals_dict = safe_globals.copy()
        
        # Ajouter les builtins autorisés
        restricted_builtins = {}
        for name in self.ALLOWED_BUILTINS:
            if name in safe_builtins:
                restricted_builtins[name] = safe_builtins[name]
            elif hasattr(__builtins__, name):
                restricted_builtins[name] = getattr(__builtins__, name)
        
        safe_globals_dict['__builtins__'] = restricted_builtins
        
        # Ajouter la fonction print sécurisée pour RestrictedPython
        safe_globals_dict['_print_'] = self._safe_print
        safe_globals_dict['_getattr_'] = getattr
        safe_globals_dict['_getitem_'] = lambda obj, key: obj[key]
        safe_globals_dict['_getiter_'] = iter
        safe_globals_dict['_write_'] = lambda x: x
        
        # Ajouter des fonctions mathématiques de base
        import math
        math_functions = {
            'sqrt': math.sqrt, 'pow': math.pow, 'abs': abs,
            'round': round, 'min': min, 'max': max
        }
        safe_globals_dict.update(math_functions)
        
        return safe_globals_dict
    
    def _validate_code(self, code):
        """Valide le code avant exécution"""
        # Vérifier les imports interdits
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                for forbidden in self.FORBIDDEN_MODULES:
                    if forbidden in line:
                        raise CodeExecutionError(f"Import interdit détecté: {forbidden}")
        
        # Vérifier les mots-clés dangereux
        dangerous_keywords = ['exec', 'eval', 'compile', '__import__', 'open', 'file']
        for keyword in dangerous_keywords:
            if keyword in code:
                raise CodeExecutionError(f"Mot-clé interdit détecté: {keyword}")
    
    def execute_code(self, code, test_input=None):
        """
        Exécute le code de manière sécurisée
        
        Args:
            code (str): Code Python à exécuter
            test_input (str): Input optionnel pour le code
            
        Returns:
            dict: Résultat de l'exécution avec output, erreurs, etc.
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
            # Valider le code
            self._validate_code(code)
            
            # Compiler le code avec RestrictedPython
            compiled_code = compile_restricted(code, '<user_code>', 'exec')
            
            if compiled_code is None:
                raise CodeExecutionError("Erreur de compilation du code")
            
            # Créer l'environnement d'exécution sécurisé
            safe_globals_dict = self._create_safe_globals()
            safe_locals = {}
            
            # Pour RestrictedPython, on doit capturer les prints différemment
            printed_output = []
            
            def capture_print(*args, **kwargs):
                output = self._safe_print(*args, **kwargs)
                printed_output.append(output)
                return output
            
            # Remplacer la fonction print dans l'environnement
            safe_globals_dict['_print_'] = capture_print
            
            try:
                # Exécuter le code
                exec(compiled_code, safe_globals_dict, safe_locals)
                
                # Récupérer les sorties des prints
                result['output'] = ''.join(printed_output)
                
                result['success'] = True
                    
            except Exception as e:
                result['error'] = f"Erreur d'exécution: {str(e)}"
                
        except CodeExecutionError as e:
            result['error'] = str(e)
            
        except Exception as e:
            result['error'] = f"Erreur inattendue: {str(e)}"
            
        finally:
            result['execution_time'] = time.time() - start_time
            
        return result
    
    def run_tests(self, code, tests):
        """
        Exécute une série de tests sur le code
        
        Args:
            code (str): Code Python à tester
            tests (list): Liste des tests à exécuter
            
        Returns:
            list: Résultats des tests
        """
        test_results = []
        
        for i, test in enumerate(tests):
            test_result = {
                'test_number': i + 1,
                'input': test.get('input', ''),
                'expected': test.get('expected', ''),
                'actual': '',
                'passed': False,
                'error': ''
            }
            
            try:
                # Créer le code de test complet avec gestion des erreurs
                test_code = f"""
{code}

# Exécuter le test et capturer le résultat
result = {test['input']}
print(result)
"""
                
                # Exécuter le test
                execution_result = self.execute_code(test_code)
                
                if execution_result['success']:
                    actual_output = execution_result['output'].strip()
                    expected_output = str(test['expected']).strip()
                    test_result['actual'] = actual_output
                    test_result['passed'] = actual_output == expected_output
                
                    if not test_result['passed']:
                        test_result['error'] = f"Attendu: {expected_output}, Obtenu: {actual_output}"
                else:
                    test_result['error'] = execution_result['error']
                    
            except Exception as e:
                test_result['error'] = f"Erreur lors du test: {str(e)}"
            
            test_results.append(test_result)
        
        return test_results


# Instance globale de l'exécuteur
secure_executor = SecurePythonExecutor()