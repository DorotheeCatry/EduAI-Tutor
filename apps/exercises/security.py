"""
Système de sécurité simplifié pour l'exécution de code Python
Utilise exec() avec un environnement restreint
"""

import sys
import io
import time
import traceback
import functools
from contextlib import redirect_stdout, redirect_stderr


class CodeExecutionError(Exception):
    """Exception levée en cas d'erreur d'exécution"""
    pass


class SecurePythonExecutor:
    """Exécuteur Python simplifié et sécurisé"""
    
    # Fonctions autorisées (whitelist)
    ALLOWED_BUILTINS = {
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod',
        'enumerate', 'filter', 'float', 'format', 'frozenset', 'hex',
        'int', 'len', 'list', 'map', 'max', 'min', 'oct', 'ord',
        'pow', 'range', 'reversed', 'round', 'set', 'sorted', 'str',
        'sum', 'tuple', 'type', 'zip', 'print', 'Exception', 'ValueError',
        'TypeError', 'IndexError', 'KeyError', 'iter', 'next', 'slice',
        'hasattr', 'getattr', 'setattr', 'isinstance', 'issubclass',
        '__import__'
    }
    
    # Modules interdits (blacklist)
    FORBIDDEN_MODULES = {
        'os', 'subprocess', 'socket', 'urllib', 'requests',
        'shutil', 'glob', 'pickle', 'marshal', 'shelve', 'dbm',
        'sqlite3', 'threading', 'multiprocessing', 'ctypes',
        'importlib', 'eval', 'exec', 'compile',
        'open', 'file', 'input', 'raw_input'
    }
    
    def __init__(self, timeout=5):
        self.timeout = timeout
    
    def _create_safe_globals(self):
        """Crée un environnement global sécurisé"""
        # Créer un dictionnaire de builtins restreint
        restricted_builtins = {}
        for name in self.ALLOWED_BUILTINS:
            if isinstance(__builtins__, dict):
                if name in __builtins__:
                    restricted_builtins[name] = __builtins__[name]
            else:
                if hasattr(__builtins__, name):
                    restricted_builtins[name] = getattr(__builtins__, name)
        
        # Ajouter des fonctions mathématiques de base
        import math
        math_functions = {
            'sqrt': math.sqrt, 'pow': pow, 'abs': abs,
            'round': round, 'min': min, 'max': max
        }
        
        # Ajouter functools.wraps directement
        import functools
        functools_functions = {
            'wraps': functools.wraps,
        }
        
        # Ajouter les modules sécurisés nécessaires
        safe_modules = {
            'time': time,
            'functools': functools,
        }
        
        safe_globals = {
            '__builtins__': restricted_builtins,
            **math_functions,
            **functools_functions,
            **safe_modules
        }
        
        print(f"🔧 Builtins disponibles: {sorted(restricted_builtins.keys())}")
        print(f"🔧 Modules disponibles: {list(safe_modules.keys())}")
        print(f"🔧 Fonctions disponibles: {list(functools_functions.keys())}")
        return safe_globals
    
    def _validate_code(self, code):
        """Valide le code avant exécution"""
        # Vérifier les imports interdits
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # Permettre les imports sécurisés
                if any(safe_module in line for safe_module in ['time', 'functools']):
                    continue
                for forbidden in self.FORBIDDEN_MODULES:
                    if forbidden in line:
                        raise CodeExecutionError(f"Import interdit détecté: {forbidden}")
        
        # Vérifier les mots-clés dangereux
        dangerous_keywords = ['exec', 'eval', 'compile', 'open', 'file']
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
            
            # Compiler le code
            try:
                compiled_code = compile(code, '<user_code>', 'exec')
            except SyntaxError as e:
                raise CodeExecutionError(f"Erreur de syntaxe: {str(e)}")
            
            # Créer l'environnement d'exécution sécurisé
            safe_globals = self._create_safe_globals()
            safe_locals = {}
            
            # Capturer les sorties
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            try:
                with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                    exec(compiled_code, safe_globals, safe_locals)
                
                result['output'] = output_buffer.getvalue()
                result['success'] = True
                    
            except Exception as e:
                error_output = error_buffer.getvalue()
                if error_output:
                    result['error'] = f"Erreur d'exécution: {error_output}"
                else:
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
                'expected': str(test.get('expected', '')),
                'actual': '',
                'passed': False,
                'error': ''
            }
            
            try:
                # Créer le code de test simple sans import sys
                test_code = f"""{code}

# Exécuter le test
result = {test['input']}
if result is not None:
    print(result)
"""
                
                print(f"🧪 Exécution du test {i+1}: {test['input']}")
                
                # Exécuter le test
                execution_result = self.execute_code(test_code)
                
                if execution_result['success']:
                    actual_output = str(execution_result['output']).strip()
                    
                    # Nettoyer la sortie plus simplement
                    lines = actual_output.split('\n')
                    # Pour les décorateurs qui affichent plusieurs lignes, garder tout
                    actual_output = actual_output.strip()
                    
                    # Si on a plusieurs lignes, les rejoindre avec des espaces pour comparaison
                    if '\n' in actual_output:
                        # Remplacer les retours à la ligne par des espaces pour la comparaison
                        actual_output_for_comparison = actual_output.replace('\n', ' ')
                    else:
                        actual_output_for_comparison = actual_output
                    
                    expected_output = str(test['expected']).strip()
                    # Même traitement pour l'attendu
                    if '\n' in expected_output:
                        expected_output_for_comparison = expected_output.replace('\n', ' ')
                    else:
                        expected_output_for_comparison = expected_output
                    
                    test_result['actual'] = actual_output
                    test_result['passed'] = actual_output_for_comparison == expected_output_for_comparison
                    
                    print(f"   Attendu: {expected_output_for_comparison}")
                    print(f"   Obtenu: {actual_output_for_comparison}")
                    print(f"   Résultat: {'✅' if test_result['passed'] else '❌'}")
                    
                    if not test_result['passed']:
                        test_result['error'] = f"Attendu: {expected_output_for_comparison}, Obtenu: {actual_output_for_comparison}"
                else:
                    test_result['error'] = execution_result['error']
                    print(f"   Erreur: {execution_result['error']}")
                    
            except Exception as e:
                test_result['error'] = f"Erreur lors du test: {str(e)}"
                print(f"   Exception: {str(e)}")
            
            test_results.append(test_result)
        
        return test_results


# Instance globale de l'exécuteur
secure_executor = SecurePythonExecutor()