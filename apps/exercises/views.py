from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from apps.agents.agent_orchestrator import get_orchestrator
from .models import Exercise, ExerciseSubmission, UserExerciseProgress
from .security import secure_executor
import json
import time

@login_required
def exercise_list(request):
    """Liste des exercices disponibles"""
    
    # Filtres
    difficulty = request.GET.get('difficulty', '')
    topic = request.GET.get('topic', '')
    search = request.GET.get('search', '')
    
    exercises = Exercise.objects.filter(is_active=True)
    
    if difficulty:
        exercises = exercises.filter(difficulty=difficulty)
    if topic:
        exercises = exercises.filter(topic__icontains=topic)
    if search:
        exercises = exercises.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    
    # Ordonner par date de création (plus récents en premier)
    exercises = exercises.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(exercises, 12)
    page_number = request.GET.get('page')
    exercises_page = paginator.get_page(page_number)
    
    # Statistiques utilisateur
    user_progress = {}
    if request.user.is_authenticated:
        progress_qs = UserExerciseProgress.objects.filter(
            user=request.user,
            exercise__in=exercises_page
        ).select_related('exercise')
        
        for progress in progress_qs:
            user_progress[progress.exercise_id] = progress
    
    # Topics disponibles pour le filtre
    topics = Exercise.objects.filter(is_active=True).values_list('topic', flat=True).distinct()
    
    # Ajouter la progression à chaque exercice de la page pour simplifier le template
    for exercise in exercises_page:
        exercise.user_progress = user_progress.get(exercise.id)
    
    context = {
        'exercises': exercises_page,
        'topics': topics,
        'current_difficulty': difficulty,
        'current_topic': topic,
        'current_search': search,
        'difficulty_choices': Exercise.DIFFICULTY_CHOICES,
    }
    
    return render(request, 'exercises/exercise_list.html', context)

@login_required
def exercise_detail(request, exercise_id):
    """Page de détail d'un exercice avec interface de code"""
    
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    
    # Récupérer ou créer la progression utilisateur
    progress, created = UserExerciseProgress.objects.get_or_create(
        user=request.user,
        exercise=exercise
    )
    
    # Récupérer les dernières soumissions
    recent_submissions = ExerciseSubmission.objects.filter(
        user=request.user,
        exercise=exercise
    ).order_by('-submitted_at')[:2]
    
    context = {
        'exercise': exercise,
        'progress': progress,
        'recent_submissions': recent_submissions,
    }
    
    return render(request, 'exercises/exercise_detail.html', context)

@csrf_exempt
@login_required
def submit_code(request, exercise_id):
    """API endpoint pour soumettre et exécuter du code"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    
    try:
        data = json.loads(request.body)
        submitted_code = data.get('code', '').strip()
        
        if not submitted_code:
            return JsonResponse({'error': 'Empty code'}, status=400)
        
        # Create submission
        submission = ExerciseSubmission.objects.create(
            exercise=exercise,
            user=request.user,
            submitted_code=submitted_code,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Execute tests
        start_time = time.time()
        
        # Debug: display tests
        print(f"🧪 Tests à exécuter pour {exercise.title}:")
        for i, test in enumerate(exercise.tests):
            print(f"  Test {i+1}: {test}")
        
        # Check that tests are properly formatted
        if not exercise.tests:
            return JsonResponse({'error': 'No tests defined for this exercise'}, status=400)
        
        test_results = secure_executor.run_tests(submitted_code, exercise.tests)
        
        # Debug: display results
        print(f"📊 Résultats des tests:")
        for result in test_results:
            print(f"  Test {result['test_number']}: {'✅' if result['passed'] else '❌'} - {result.get('error', 'OK')}")
        
        execution_time = time.time() - start_time
        
        # Analyze results
        passed_tests = sum(1 for result in test_results if result['passed'])
        total_tests = len(test_results)
        all_passed = passed_tests == total_tests
        
        # Update submission
        submission.test_results = test_results
        submission.execution_time = execution_time
        submission.status = 'success' if all_passed else 'failed'
        
        # Create error summary
        if not all_passed:
            errors = [result['error'] for result in test_results if result['error']]
            submission.error_message = '\n'.join(errors)
        
        submission.save()
        
        # Update exercise statistics
        exercise.attempts_count += 1
        if all_passed:
            exercise.success_count += 1
        exercise.save()
        
        # Update user progress
        progress = UserExerciseProgress.objects.get(
            user=request.user,
            exercise=exercise
        )
        progress.attempts_count += 1
        
        if all_passed and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = submission.submitted_at
            progress.best_submission = submission
            
            # Add XP for success
            xp_gained = 20 + (exercise.difficulty == 'advanced' and 10 or 0)
            xp_result = request.user.add_xp(xp_gained, 'exercise_completion')
            
        elif all_passed and (not progress.best_submission or 
                           submission.execution_time < progress.best_submission.execution_time):
            progress.best_submission = submission
        
        progress.save()
        
        # Prepare response
        response_data = {
            'success': all_passed,
            'submission_id': submission.id,
            'test_results': test_results,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'execution_time': round(execution_time, 3),
            'message': 'Congratulations! All tests passed!' if all_passed else f'{passed_tests}/{total_tests} tests passed'
        }
        
        # Add XP info if exercise completed
        if all_passed and 'xp_result' in locals():
            response_data['xp_result'] = xp_result
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

@login_required
def generate_exercise(request):
    """Generate a new exercise with AI"""
    
    if request.method == 'POST':
        topic = request.POST.get('topic', '').strip()
        difficulty = request.POST.get('difficulty', 'beginner')
        
        if not topic:
            messages.error(request, 'Please specify a topic for the exercise.')
            return redirect('exercises:list')
        
        try:
            # Use AI orchestrator to generate exercise
            orchestrator = get_orchestrator(request.user)
            
            # Create specialized prompt for exercises
            prompt = f"""
            Generate a Python programming exercise on the topic "{topic}" at {difficulty} level.
            
            MANDATORY STEPS:
            1. Define ONE clear main function (e.g.: calculate_average, decorator_timer, etc.)
            2. Write the complete working solution
            3. Create starter_code with # TODO to complete
            4. Generate tests that call EXACTLY this function with the right parameters
            5. Verify that expected results match your solution's behavior
            
            CRITICAL RULES:
            - Tests must call the SAME function as defined in the solution
            - "expected" values must be the REAL result of your function
            - Test varied cases: normal, edge, error
            - ALWAYS use f-strings (f"") for string formatting, never concatenation
            - Example: f"Result: {{value}}" instead of "Result: " + str(value)
            
            CONSISTENCY EXAMPLE:
            If your solution defines "def calculate_average(list):", 
            then your tests should be "calculate_average([1,2,3])" with expected "2.0"
            
            STRICT JSON Format:
            {{
                "title": "Exercise title",
                "description": "Detailed description",
                "starter_code": "Starting code with # TODO",
                "solution": "Complete solution code",
                "tests": [
                    {{"input": "my_function(2, 3)", "expected": "5"}},
                    {{"input": "my_function(-1, 1)", "expected": "0"}},
                    {{"input": "my_function(0, 0)", "expected": "0"}}
                ]
            }}
            
            FINAL VERIFICATION: Make sure that if I execute your solution then your tests, 
            the results exactly match the "expected" values.
            IMPORTANT: Use f-strings in all generated Python code!
            """
            
            result = orchestrator.answer_question(prompt)
            
            if result['success']:
                try:
                    # Parse JSON response with robust cleaning
                    answer = result['answer'].strip()
                    print(f"🔍 Raw response received: {answer[:500]}...")
                    
                    # Clean response from markdown code blocks
                    if '```json' in answer:
                        # Extract content between ```json and ```
                        start_marker = answer.find('```json') + 7
                        end_marker = answer.find('```', start_marker)
                        if end_marker != -1:
                            json_content = answer[start_marker:end_marker].strip()
                        else:
                            json_content = answer[start_marker:].strip()
                    else:
                        # Extract JSON if there's text before/after
                        start_idx = answer.find('{')
                        end_idx = answer.rfind('}') + 1
                        if start_idx != -1 and end_idx != -1:
                            json_content = answer[start_idx:end_idx]
                        else:
                            raise json.JSONDecodeError("No JSON found", answer, 0)
                    
                    print(f"🧹 Extracted JSON: {json_content[:300]}...")
                    
                    # Clean Python triple quotes in JSON
                    json_content = json_content.replace('"""', '"')
                    json_content = json_content.replace("'''", '"')
                    
                    # Clean line breaks and control characters in JSON strings
                    import re
                    
                    # Function to clean a JSON string
                    def clean_json_string(match):
                        key = match.group(1)
                        value = match.group(2)
                        # Replace line breaks with \n and escape quotes
                        cleaned_value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"')
                        return f'"{key}": "{cleaned_value}"'
                    
                    # Apply cleaning to multiline JSON strings
                    json_content = re.sub(r'"([^"]+)":\s*"([^"]*(?:\n[^"]*)*)"', clean_json_string, json_content, flags=re.MULTILINE | re.DOTALL)
                    # Function to clean a JSON string
                    def clean_json_string(match):
                        key = match.group(1)
                        value = match.group(2)
                        # Replace line breaks with \n and escape quotes
                        cleaned_value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"')
                        return f'"{key}": "{cleaned_value}"'
                    
                    # Apply cleaning to multiline JSON strings
                    json_content = re.sub(r'"([^"]+)":\s*"([^"]*(?:\n[^"]*)*)"', clean_json_string, json_content, flags=re.MULTILINE | re.DOTALL)
                    
                    print(f"🔧 Cleaned JSON: {json_content[:300]}...")
                    
                    # Parse cleaned JSON
                    exercise_data = json.loads(json_content)
                    
                    # Check that all required keys are present
                    required_keys = ['title', 'description', 'starter_code', 'solution', 'tests']
                    for key in required_keys:
                        if key not in exercise_data:
                            raise KeyError(f"Missing key: {key}")
                    
                    # Clean starter_code and solution from triple quotes
                    if isinstance(exercise_data.get('starter_code'), str):
                        # Clean and format starting code
                        starter_code = exercise_data['starter_code']
                        starter_code = starter_code.replace('"""', '').replace("'''", '').strip()
                        # Replace \n with real line breaks
                        starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t')
                        exercise_data['starter_code'] = starter_code
                    
                    if isinstance(exercise_data.get('solution'), str):
                        # Clean and format solution
                        solution = exercise_data['solution']
                        solution = solution.replace('"""', '').replace("'''", '').strip()
                        # Replace \n with real line breaks
                        solution = solution.replace('\\n', '\n').replace('\\t', '\t')
                        exercise_data['solution'] = solution
                    
                    print(f"✅ Exercise parsed: {exercise_data['title']}")
                    
                    # Create exercise
                    exercise = Exercise.objects.create(
                        title=exercise_data['title'],
                        description=exercise_data['description'],
                        difficulty=difficulty,
                        topic=topic,
                        starter_code=exercise_data['starter_code'],
                        solution=exercise_data['solution'],
                        tests=exercise_data['tests'],
                        created_by=request.user
                    )
                    
                    print(f"✅ Exercise created successfully: {exercise.title} (ID: {exercise.id})")
                    messages.success(request, f'Exercise "{exercise.title}" generated successfully!')
                    return redirect('exercises:detail', exercise_id=exercise.id)
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"❌ JSON parsing error: {e}")
                    print(f"Response received: {result['answer'][:500]}...")
                    
                    # Try more aggressive parsing
                    try:
                        # Alternative method: manually extract values
                        answer = result['answer']
                        
                        # Extract title
                        title_match = re.search(r'"title":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                        title = title_match.group(1) if title_match else f"Exercise on {topic}"
                        
                        # Extract description
                        desc_match = re.search(r'"description":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                        description = desc_match.group(1) if desc_match else f"Practical exercise on {topic}"
                        
                        # Extract starter_code (between quotes or in a block)
                        starter_match = re.search(r'"starter_code":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                        if not starter_match:
                            # Look in a code block
                            starter_match = re.search(r'"starter_code":\s*```python\n(.*?)```', answer, re.DOTALL)
                        
                        starter_code = starter_match.group(1) if starter_match else f"# TODO: Implement your solution for {topic}\n\ndef my_function():\n    # Your code here\n    pass"
                        
                        # Extract solution
                        solution_match = re.search(r'"solution":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                        if not solution_match:
                            solution_match = re.search(r'"solution":\s*```python\n(.*?)```', answer, re.DOTALL)
                        
                        solution = solution_match.group(1) if solution_match else f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'"
                        
                        # Clean escapes
                        starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        solution = solution.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        
                        # Default tests if not found
                        tests = [
                            {"input": "my_function()", "expected": "Hello World"}
                        ]
                        
                        # Try to extract tests
                        tests_match = re.search(r'"tests":\s*\[(.*?)\]', answer, re.DOTALL)
                        if tests_match:
                            try:
                                tests_str = '[' + tests_match.group(1) + ']'
                                tests = json.loads(tests_str)
                            except:
                                pass  # Keep default tests
                        
                        print(f"✅ Manual parsing successful: {title}")
                        
                        # Create exercise with extracted data
                        exercise = Exercise.objects.create(
                            title=title,
                            description=description,
                            difficulty=difficulty,
                            topic=topic,
                            starter_code=starter_code,
                            solution=solution,
                            tests=tests,
                            created_by=request.user
                        )
                        
                        print(f"✅ Exercise created with manual parsing: {exercise.title} (ID: {exercise.id})")
                        messages.success(request, f'Exercise "{exercise.title}" generated successfully!')
                        return redirect('exercises:detail', exercise_id=exercise.id)
                        
                    except Exception as manual_error:
                        print(f"❌ Manual parsing failed: {manual_error}")
                    
                    # Create basic fallback exercise
                    fallback_exercise = Exercise.objects.create(
                        title=f"Exercise on {topic}",
                        description=f"Practical exercise on {topic}. Complete the code below.",
                        difficulty=difficulty,
                        topic=topic,
                        starter_code=f"# TODO: Implement your solution for {topic}\n\ndef my_function():\n    # Your code here\n    pass\n",
                        solution=f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'\n",
                        tests=[
                            {"input": "my_function()", "expected": "Hello World"}
                        ],
                        created_by=request.user
                    )
                    
                    messages.warning(request, f'AI generated a malformed response. Basic exercise created on "{topic}".')
                    return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            else:
                print(f"❌ Orchestrator error: {result.get('error', 'Unknown error')}")
                messages.error(request, f'Generation error: {result.get("error", "Unknown error")}')
                
        except Exception as e:
            print(f"❌ Exception during generation: {str(e)}")
            
            # Create fallback exercise in case of total error
            try:
                fallback_exercise = Exercise.objects.create(
                    title=f"Exercise on {topic}",
                    description=f"Practical exercise on {topic}. Complete the code below.",
                    difficulty=difficulty,
                    topic=topic,
                    starter_code=f"# TODO: Implement your solution for {topic}\n\ndef my_function():\n    # Your code here\n    pass\n",
                    solution=f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'\n",
                    tests=[
                        {"input": "my_function()", "expected": "Hello World"}
                    ],
                    created_by=request.user
                )
                
                messages.warning(request, f'AI generation error. Basic exercise created on "{topic}".')
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            except Exception as fallback_error:
                messages.error(request, f'Generation error: {str(e)}')
    
    return redirect('exercises:list')

@login_required
def generate_exercise_from_course(request):
    """Generate an exercise based on a course topic"""
    
    topic = request.GET.get('topic', '').strip()
    difficulty = request.GET.get('difficulty', 'intermediate')  # Default difficulty for courses
    
    if not topic:
        messages.error(request, 'No topic specified to generate the exercise.')
        return redirect('exercises:list')
    
    try:
        # Use AI orchestrator to generate exercise
        orchestrator = get_orchestrator(request.user)
        
        # Specialized prompt for course-based exercises
        prompt = f"""
        Generate a practical Python programming exercise based on the course: "{topic}" (level {difficulty})
        
        MANDATORY STEPS:
        1. Define ONE clear main function related to the course topic
        2. Write the complete solution that actually works
        3. Create starter_code with # TODO to complete
        4. Generate tests that call EXACTLY this function
        5. Verify that expected results are correct
        
        CRITICAL RULES:
        - Tests must call the SAME function as defined in the solution
        - "expected" values must be the REAL result of your function
        - Test varied cases: normal, edge, error
        - Exercise should allow practicing concepts from course "{topic}"
        
        CONSISTENCY EXAMPLE for decorators:
        If your solution defines "def my_decorator(func):" and a function "calculate(a,b)",
        then your tests should be "calculate(2, 3)" with the correct expected result.
        
        STRICT JSON Format:
        {{
            "title": "Practical exercise title",
            "description": "Detailed exercise description",
            "starter_code": "Starting code with # TODO",
            "solution": "Complete solution code",
            "tests": [
                {{"input": "my_function(2, 3)", "expected": "5"}},
                {{"input": "my_function(-1, 1)", "expected": "0"}},
                {{"input": "my_function(0, 0)", "expected": "0"}}
            ]
        }}
        
        FINAL VERIFICATION: Make sure that if I execute your solution then your tests, 
        the results exactly match the "expected" values.
        """
        
        result = orchestrator.answer_question(prompt)
        
        if result['success']:
            try:
                # Parse JSON response with robust cleaning
                answer = result['answer'].strip()
                print(f"🔍 Raw response received: {answer[:500]}...")
                
                # Clean response from markdown code blocks
                if '```json' in answer:
                    start_marker = answer.find('```json') + 7
                    end_marker = answer.find('```', start_marker)
                    if end_marker != -1:
                        json_content = answer[start_marker:end_marker].strip()
                    else:
                        json_content = answer[start_marker:].strip()
                else:
                    # Extract JSON if there's text before/after
                    start_idx = answer.find('{')
                    end_idx = answer.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_content = answer[start_idx:end_idx]
                    else:
                        raise json.JSONDecodeError("No JSON found", answer, 0)
                
                print(f"🧹 Extracted JSON: {json_content[:300]}...")
                
                # Clean Python triple quotes in JSON
                json_content = json_content.replace('"""', '"')
                json_content = json_content.replace("'''", '"')
                
                # Clean line breaks in strings
                import re
                json_content = re.sub(r':\s*"([^"]*)\n([^"]*)"', r': "\1\\n\2"', json_content, flags=re.MULTILINE)
                
                print(f"🔧 Cleaned JSON: {json_content[:300]}...")
                
                # Parse cleaned JSON
                exercise_data = json.loads(json_content)
                
                # Check that all required keys are present
                required_keys = ['title', 'description', 'starter_code', 'solution', 'tests']
                for key in required_keys:
                    if key not in exercise_data:
                        raise KeyError(f"Missing key: {key}")
                
                # Clean starter_code and solution from triple quotes
                if isinstance(exercise_data.get('starter_code'), str):
                    # Clean and format starting code
                    starter_code = exercise_data['starter_code']
                    starter_code = starter_code.replace('"""', '').replace("'''", '').strip()
                    # Replace \n with real line breaks
                    starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t')
                    exercise_data['starter_code'] = starter_code
                
                if isinstance(exercise_data.get('solution'), str):
                    # Clean and format solution
                    solution = exercise_data['solution']
                    solution = solution.replace('"""', '').replace("'''", '').strip()
                    # Replace \n with real line breaks
                    solution = solution.replace('\\n', '\n').replace('\\t', '\t')
                    exercise_data['solution'] = solution
                
                print(f"✅ Exercise parsed: {exercise_data['title']}")
                
                # Create exercise
                exercise = Exercise.objects.create(
                    title=exercise_data['title'],
                    description=exercise_data['description'],
                    difficulty=difficulty,
                    topic=topic,
                    starter_code=exercise_data['starter_code'],
                    solution=exercise_data['solution'],
                    tests=exercise_data['tests'],
                    created_by=request.user
                )
                
                print(f"✅ Exercise created successfully: {exercise.title} (ID: {exercise.id})")
                messages.success(request, f'Exercise "{exercise.title}" generated successfully from course!')
                return redirect('exercises:detail', exercise_id=exercise.id)
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"❌ JSON parsing error: {e}")
                print(f"Response received: {result['answer'][:500]}...")
                
                # Try more aggressive parsing
                try:
                    # Alternative method: manually extract values
                    answer = result['answer']
                    
                    # Extract title
                    title_match = re.search(r'"title":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                    title = title_match.group(1) if title_match else f"Practical exercise: {topic}"
                    
                    # Extract description
                    desc_match = re.search(r'"description":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                    description = desc_match.group(1) if desc_match else f"Practical exercise based on the course '{topic}'. Complete the code below to practice the learned concepts."
                    
                    # Extract starter_code (between quotes or in a block)
                    starter_match = re.search(r'"starter_code":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                    if not starter_match:
                        # Look in a code block
                        starter_match = re.search(r'"starter_code":\s*```python\n(.*?)```', answer, re.DOTALL)
                    
                    starter_code = starter_match.group(1) if starter_match else f"# Exercise based on course: {topic}\n# TODO: Implement your solution\n\ndef my_function():\n    # Your code here\n    pass"
                    
                    # Extract solution
                    solution_match = re.search(r'"solution":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                    if not solution_match:
                        solution_match = re.search(r'"solution":\s*```python\n(.*?)```', answer, re.DOTALL)
                    
                    solution = solution_match.group(1) if solution_match else f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'"
                    
                    # Clean escapes
                    starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                    solution = solution.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                    
                    # Default tests if not found
                    tests = [
                        {"input": "my_function()", "expected": "Hello World"}
                    ]
                    
                    # Try to extract tests
                    tests_match = re.search(r'"tests":\s*\[(.*?)\]', answer, re.DOTALL)
                    if tests_match:
                        try:
                            tests_str = '[' + tests_match.group(1) + ']'
                            tests = json.loads(tests_str)
                        except:
                            pass  # Keep default tests
                    
                    print(f"✅ Manual parsing successful: {title}")
                    
                    # Create exercise with extracted data
                    exercise = Exercise.objects.create(
                        title=title,
                        description=description,
                        difficulty=difficulty,
                        topic=topic,
                        starter_code=starter_code,
                        solution=solution,
                        tests=tests,
                        created_by=request.user
                    )
                    
                    print(f"✅ Exercise created with manual parsing: {exercise.title} (ID: {exercise.id})")
                    messages.success(request, f'Exercise "{exercise.title}" generated successfully from course!')
                    return redirect('exercises:detail', exercise_id=exercise.id)
                    
                except Exception as manual_error:
                    print(f"❌ Manual parsing failed: {manual_error}")
                
                # Create basic fallback exercise
                fallback_exercise = Exercise.objects.create(
                    title=f"Practical exercise: {topic}",
                    description=f"Practical exercise based on the course '{topic}'. Complete the code below to practice the learned concepts.",
                    difficulty=difficulty,
                    topic=topic,
                    starter_code=f"# Exercise based on course: {topic}\n# TODO: Implement your solution\n\ndef my_function():\n    # Your code here\n    pass\n",
                    solution=f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'\n",
                    tests=[
                        {"input": "my_function()", "expected": "Hello World"}
                    ],
                    created_by=request.user
                )
                
                messages.warning(request, f'AI generated a malformed response. Basic exercise created on "{topic}".')
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        else:
            print(f"❌ Orchestrator error: {result.get('error', 'Unknown error')}")
            messages.error(request, f'Generation error: {result.get("error", "Unknown error")}')
            
    except Exception as e:
        print(f"❌ Exception during generation: {str(e)}")
        
        # Create fallback exercise in case of total error
        try:
            fallback_exercise = Exercise.objects.create(
                title=f"Practical exercise: {topic}",
                description=f"Practical exercise based on the course '{topic}'. Complete the code below.",
                difficulty=difficulty,
                topic=topic,
                starter_code=f"# TODO: Implement your solution for {topic}\n\ndef my_function():\n    # Your code here\n    pass\n",
                solution=f"# Example solution for {topic}\n\ndef my_function():\n    return 'Hello World'\n",
                tests=[
                    {"input": "my_function()", "expected": "Hello World"}
                ],
                created_by=request.user
            )
            
            messages.warning(request, f'AI generation error. Basic exercise created on "{topic}".')
            return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        except Exception as fallback_error:
            messages.error(request, f'Generation error: {str(e)}')
    
    return redirect('exercises:list')

@login_required
def user_progress(request):
    """User progress page for exercises"""
    
    # General statistics
    total_exercises = Exercise.objects.filter(is_active=True).count()
    completed_exercises = UserExerciseProgress.objects.filter(
        user=request.user,
        is_completed=True
    ).count()
    
    # Progress by difficulty
    difficulty_stats = {}
    for difficulty, label in Exercise.DIFFICULTY_CHOICES:
        total = Exercise.objects.filter(difficulty=difficulty, is_active=True).count()
        completed = UserExerciseProgress.objects.filter(
            user=request.user,
            exercise__difficulty=difficulty,
            is_completed=True
        ).count()
        
        difficulty_stats[difficulty] = {
            'label': label,
            'total': total,
            'completed': completed,
            'percentage': round((completed / total * 100) if total > 0 else 0, 1)
        }
    
    # Recent exercises
    recent_progress = UserExerciseProgress.objects.filter(
        user=request.user
    ).select_related('exercise').order_by('-first_attempt_at')[:10]
    
    # Recent submissions
    recent_submissions = ExerciseSubmission.objects.filter(
        user=request.user
    ).select_related('exercise').order_by('-submitted_at')[:10]
    
    context = {
        'total_exercises': total_exercises,
        'completed_exercises': completed_exercises,
        'completion_percentage': round((completed_exercises / total_exercises * 100) if total_exercises > 0 else 0, 1),
        'difficulty_stats': difficulty_stats,
        'recent_progress': recent_progress,
        'recent_submissions': recent_submissions,
    }
    
    return render(request, 'exercises/user_progress.html', context)