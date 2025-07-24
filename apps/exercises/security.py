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
    
    # Forbidden modules (blacklist)
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
        """Creates a secure global environment"""
        # Create restricted builtins dictionary
        restricted_builtins = {}
        for name in self.ALLOWED_BUILTINS:
            if isinstance(__builtins__, dict):
                if name in __builtins__:
                    restricted_builtins[name] = __builtins__[name]
            else:
                if hasattr(__builtins__, name):
                    restricted_builtins[name] = getattr(__builtins__, name)
        
        # Add basic math functions
        import math
        math_functions = {
            'sqrt': math.sqrt, 'pow': pow, 'abs': abs,
            'round': round, 'min': min, 'max': max
        }
        
        # Add functools.wraps directly
        import functools
        functools_functions = {
            'wraps': functools.wraps,
        }
        
        # Add necessary secure modules
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
        
        print(f"🔧 Available builtins: {sorted(restricted_builtins.keys())}")
        print(f"🔧 Available modules: {list(safe_modules.keys())}")
        print(f"🔧 Available functions: {list(functools_functions.keys())}")
        return safe_globals
    
    def _validate_code(self, code):
        """Validates code before execution"""
        # Check forbidden imports
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # Allow secure imports
                if any(safe_module in line for safe_module in ['time', 'functools']):
                    continue
                for forbidden in self.FORBIDDEN_MODULES:
                    if forbidden in line:
                        raise CodeExecutionError(f"Forbidden import detected: {forbidden}")
        
        # Check dangerous keywords
        dangerous_keywords = ['exec', 'eval', 'compile', 'open', 'file']
        for keyword in dangerous_keywords:
            if keyword in code:
                raise CodeExecutionError(f"Forbidden keyword detected: {keyword}")
    
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
                compiled_code = compile(code, '<user_code>', 'exec')
            except SyntaxError as e:
                raise CodeExecutionError(f"Syntax error: {str(e)}")
            
            # Create secure execution environment
            safe_globals = self._create_safe_globals()
            safe_locals = {}
            
            # Capture outputs
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            try:
                with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                    exec(compiled_code, safe_globals, safe_locals)
                
                result['output'] = output_buffer.getvalue()
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
                            print(f"   Expected: Error")
                            print(f"   Got: Error raised correctly")
                            print(f"   Result: ✅")
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