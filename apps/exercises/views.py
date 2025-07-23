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
            return JsonResponse({'error': 'Code vide'}, status=400)
        
        # Créer la soumission
        submission = ExerciseSubmission.objects.create(
            exercise=exercise,
            user=request.user,
            submitted_code=submitted_code,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Exécuter les tests
        start_time = time.time()
        
        # Debug: afficher les tests
        print(f"🧪 Tests à exécuter pour {exercise.title}:")
        for i, test in enumerate(exercise.tests):
            print(f"  Test {i+1}: {test}")
        
        # Vérifier que les tests sont bien formatés
        if not exercise.tests:
            return JsonResponse({'error': 'Aucun test défini pour cet exercice'}, status=400)
        
        test_results = secure_executor.run_tests(submitted_code, exercise.tests)
        
        # Debug: afficher les résultats
        print(f"📊 Résultats des tests:")
        for result in test_results:
            print(f"  Test {result['test_number']}: {'✅' if result['passed'] else '❌'} - {result.get('error', 'OK')}")
        
        execution_time = time.time() - start_time
        
        # Analyser les résultats
        passed_tests = sum(1 for result in test_results if result['passed'])
        total_tests = len(test_results)
        all_passed = passed_tests == total_tests
        
        # Mettre à jour la soumission
        submission.test_results = test_results
        submission.execution_time = execution_time
        submission.status = 'success' if all_passed else 'failed'
        
        # Créer un résumé des erreurs
        if not all_passed:
            errors = [result['error'] for result in test_results if result['error']]
            submission.error_message = '\n'.join(errors)
        
        submission.save()
        
        # Mettre à jour les statistiques de l'exercice
        exercise.attempts_count += 1
        if all_passed:
            exercise.success_count += 1
        exercise.save()
        
        # Mettre à jour la progression utilisateur
        progress = UserExerciseProgress.objects.get(
            user=request.user,
            exercise=exercise
        )
        progress.attempts_count += 1
        
        if all_passed and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = submission.submitted_at
            progress.best_submission = submission
            
            # Ajouter de l'XP pour la réussite
            xp_gained = 20 + (exercise.difficulty == 'advanced' and 10 or 0)
            xp_result = request.user.add_xp(xp_gained, 'exercise_completion')
            
        elif all_passed and (not progress.best_submission or 
                           submission.execution_time < progress.best_submission.execution_time):
            progress.best_submission = submission
        
        progress.save()
        
        # Préparer la réponse
        response_data = {
            'success': all_passed,
            'submission_id': submission.id,
            'test_results': test_results,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'execution_time': round(execution_time, 3),
            'message': 'Félicitations ! Tous les tests sont passés !' if all_passed else f'{passed_tests}/{total_tests} tests réussis'
        }
        
        # Ajouter les infos XP si exercice complété
        if all_passed and 'xp_result' in locals():
            response_data['xp_result'] = xp_result
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erreur serveur: {str(e)}'}, status=500)

@login_required
def generate_exercise(request):
    """Génère un nouvel exercice avec l'IA"""
    
    if request.method == 'POST':
        topic = request.POST.get('topic', '').strip()
        difficulty = request.POST.get('difficulty', 'beginner')
        
        if not topic:
            messages.error(request, 'Veuillez spécifier un sujet pour l\'exercice.')
            return redirect('exercises:list')
        
        try:
            # Utiliser l'orchestrateur IA pour générer l'exercice
            orchestrator = get_orchestrator(request.user)
            
            # Créer un prompt spécialisé pour les exercices
            prompt = f"""
            Génère un exercice de programmation Python sur le sujet "{topic}" 
            de niveau {difficulty}.
            
            L'exercice doit inclure :
            - Un titre clair
            - Une description détaillée de ce qu'il faut faire
            - Du code de départ avec des TODO
            - Une solution complète
            - Au moins 3 tests avec entrées et sorties attendues
            
            Format JSON requis :
            {{
                "title": "Titre de l'exercice",
                "description": "Description détaillée",
                "starter_code": "Code de départ avec # TODO",
                "solution": "Code solution complet",
                "tests": [
                    {{"input": "fonction(2, 3)", "expected": "5"}},
                    {{"input": "fonction(-1, 1)", "expected": "0"}}
                ]
            }}
            """
            
            result = orchestrator.answer_question(prompt)
            
            if result['success']:
                try:
                    # Parser la réponse JSON avec nettoyage robuste
                    answer = result['answer'].strip()
                    print(f"🔍 Réponse brute reçue: {answer[:500]}...")
                    
                    # Nettoyer la réponse des blocs de code markdown
                    if '```json' in answer:
                        # Extraire le contenu entre ```json et ```
                        start_marker = answer.find('```json') + 7
                        end_marker = answer.find('```', start_marker)
                        if end_marker != -1:
                            json_content = answer[start_marker:end_marker].strip()
                        else:
                            json_content = answer[start_marker:].strip()
                    else:
                        # Extraire le JSON si il y a du texte avant/après
                        start_idx = answer.find('{')
                        end_idx = answer.rfind('}') + 1
                        if start_idx != -1 and end_idx != -1:
                            json_content = answer[start_idx:end_idx]
                        else:
                            raise json.JSONDecodeError("No JSON found", answer, 0)
                    
                    print(f"🧹 JSON extrait: {json_content[:300]}...")
                    
                    # Nettoyer les triples quotes Python dans le JSON
                    json_content = json_content.replace('"""', '"')
                    json_content = json_content.replace("'''", '"')
                    
                    # Nettoyer les retours à la ligne et caractères de contrôle dans les chaînes JSON
                    import re
                    
                    # Fonction pour nettoyer une chaîne JSON
                    def clean_json_string(match):
                        key = match.group(1)
                        value = match.group(2)
                        # Remplacer les retours à la ligne par \n et échapper les guillemets
                        cleaned_value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"')
                        return f'"{key}": "{cleaned_value}"'
                    
                    # Appliquer le nettoyage aux chaînes JSON multilignes
                    json_content = re.sub(r'"([^"]+)":\s*"([^"]*(?:\n[^"]*)*)"', clean_json_string, json_content, flags=re.MULTILINE | re.DOTALL)
                    # Fonction pour nettoyer une chaîne JSON
                    def clean_json_string(match):
                        key = match.group(1)
                        value = match.group(2)
                        # Remplacer les retours à la ligne par \n et échapper les guillemets
                        cleaned_value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"')
                        return f'"{key}": "{cleaned_value}"'
                    
                    # Appliquer le nettoyage aux chaînes JSON multilignes
                    json_content = re.sub(r'"([^"]+)":\s*"([^"]*(?:\n[^"]*)*)"', clean_json_string, json_content, flags=re.MULTILINE | re.DOTALL)
                    
                    print(f"🔧 JSON nettoyé: {json_content[:300]}...")
                    
                    # Parser le JSON nettoyé
                    exercise_data = json.loads(json_content)
                    
                    # Vérifier que toutes les clés requises sont présentes
                    required_keys = ['title', 'description', 'starter_code', 'solution', 'tests']
                    for key in required_keys:
                        if key not in exercise_data:
                            raise KeyError(f"Clé manquante: {key}")
                    
                    # Nettoyer le starter_code et solution des triples quotes
                    if isinstance(exercise_data.get('starter_code'), str):
                        # Nettoyer et formater le code de départ
                        starter_code = exercise_data['starter_code']
                        starter_code = starter_code.replace('"""', '').replace("'''", '').strip()
                        # Remplacer les \n par de vrais retours à la ligne
                        starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t')
                        exercise_data['starter_code'] = starter_code
                    
                    if isinstance(exercise_data.get('solution'), str):
                        # Nettoyer et formater la solution
                        solution = exercise_data['solution']
                        solution = solution.replace('"""', '').replace("'''", '').strip()
                        # Remplacer les \n par de vrais retours à la ligne
                        solution = solution.replace('\\n', '\n').replace('\\t', '\t')
                        exercise_data['solution'] = solution
                    
                    print(f"✅ Exercice parsé: {exercise_data['title']}")
                    
                    # Créer l'exercice
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
                    
                    print(f"✅ Exercice créé avec succès : {exercise.title} (ID: {exercise.id})")
                    messages.success(request, f'Exercice "{exercise.title}" généré avec succès !')
                    return redirect('exercises:detail', exercise_id=exercise.id)
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"❌ Erreur parsing JSON : {e}")
                    print(f"Réponse reçue : {result['answer'][:500]}...")
                    
                    # Essayer un parsing plus agressif
                    try:
                        # Méthode alternative : extraire manuellement les valeurs
                        answer = result['answer']
                        
                        # Extraire le titre
                        title_match = re.search(r'"title":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                        title = title_match.group(1) if title_match else f"Exercice sur {topic}"
                        
                        # Extraire la description
                        desc_match = re.search(r'"description":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                        description = desc_match.group(1) if desc_match else f"Exercice pratique sur {topic}"
                        
                        # Extraire le starter_code (entre guillemets ou dans un bloc)
                        starter_match = re.search(r'"starter_code":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                        if not starter_match:
                            # Chercher dans un bloc de code
                            starter_match = re.search(r'"starter_code":\s*```python\n(.*?)```', answer, re.DOTALL)
                        
                        starter_code = starter_match.group(1) if starter_match else f"# TODO: Implémentez votre solution pour {topic}\n\ndef ma_fonction():\n    # Votre code ici\n    pass"
                        
                        # Extraire la solution
                        solution_match = re.search(r'"solution":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                        if not solution_match:
                            solution_match = re.search(r'"solution":\s*```python\n(.*?)```', answer, re.DOTALL)
                        
                        solution = solution_match.group(1) if solution_match else f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'"
                        
                        # Nettoyer les échappements
                        starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        solution = solution.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        
                        # Tests par défaut si pas trouvés
                        tests = [
                            {"input": "ma_fonction()", "expected": "Hello World"}
                        ]
                        
                        # Essayer d'extraire les tests
                        tests_match = re.search(r'"tests":\s*\[(.*?)\]', answer, re.DOTALL)
                        if tests_match:
                            try:
                                tests_str = '[' + tests_match.group(1) + ']'
                                tests = json.loads(tests_str)
                            except:
                                pass  # Garder les tests par défaut
                        
                        print(f"✅ Parsing manuel réussi: {title}")
                        
                        # Créer l'exercice avec les données extraites
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
                        
                        print(f"✅ Exercice créé avec parsing manuel : {exercise.title} (ID: {exercise.id})")
                        messages.success(request, f'Exercice "{exercise.title}" généré avec succès !')
                        return redirect('exercises:detail', exercise_id=exercise.id)
                        
                    except Exception as manual_error:
                        print(f"❌ Parsing manuel échoué : {manual_error}")
                    
                    # Créer un exercice de fallback basique
                    fallback_exercise = Exercise.objects.create(
                        title=f"Exercice sur {topic}",
                        description=f"Exercice pratique sur {topic}. Complétez le code ci-dessous.",
                        difficulty=difficulty,
                        topic=topic,
                        starter_code=f"# TODO: Implémentez votre solution pour {topic}\n\ndef ma_fonction():\n    # Votre code ici\n    pass\n",
                        solution=f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'\n",
                        tests=[
                            {"input": "ma_fonction()", "expected": "Hello World"}
                        ],
                        created_by=request.user
                    )
                    
                    messages.warning(request, f'L\'IA a généré une réponse malformée. Exercice de base créé sur "{topic}".')
                    return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            else:
                print(f"❌ Erreur orchestrateur : {result.get('error', 'Erreur inconnue')}")
                messages.error(request, f'Erreur lors de la génération : {result.get("error", "Erreur inconnue")}')
                
        except Exception as e:
            print(f"❌ Exception lors de la génération : {str(e)}")
            
            # Créer un exercice de fallback en cas d'erreur totale
            try:
                fallback_exercise = Exercise.objects.create(
                    title=f"Exercice sur {topic}",
                    description=f"Exercice pratique sur {topic}. Complétez le code ci-dessous.",
                    difficulty=difficulty,
                    topic=topic,
                    starter_code=f"# TODO: Implémentez votre solution pour {topic}\n\ndef ma_fonction():\n    # Votre code ici\n    pass\n",
                    solution=f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'\n",
                    tests=[
                        {"input": "ma_fonction()", "expected": "Hello World"}
                    ],
                    created_by=request.user
                )
                
                messages.warning(request, f'Erreur lors de la génération IA. Exercice de base créé sur "{topic}".')
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            except Exception as fallback_error:
                messages.error(request, f'Erreur lors de la génération : {str(e)}')
    
    return redirect('exercises:list')

@login_required
def generate_exercise_from_course(request):
    """Génère un exercice basé sur le sujet d'un cours"""
    
    topic = request.GET.get('topic', '').strip()
    difficulty = request.GET.get('difficulty', 'intermediate')  # Difficulté par défaut pour les cours
    
    if not topic:
        messages.error(request, 'Aucun sujet spécifié pour générer l\'exercice.')
        return redirect('exercises:list')
    
    try:
        # Utiliser l'orchestrateur IA pour générer l'exercice
        orchestrator = get_orchestrator(request.user)
        
        # Prompt spécialisé pour les exercices basés sur un cours
        prompt = f"""
        Génère un exercice de programmation Python pratique basé sur le cours suivant : "{topic}"
        
        L'exercice doit être de niveau {difficulty} et permettre de mettre en pratique 
        les concepts enseignés dans le cours.
        
        L'exercice doit inclure :
        - Un titre clair lié au sujet du cours
        - Une description détaillée de ce qu'il faut implémenter
        - Du code de départ avec des parties à compléter (marquées par # TODO)
        - Une solution complète fonctionnelle
        - Au moins 3 tests avec entrées et sorties attendues
        
        Format JSON requis :
        {{
            "title": "Titre de l'exercice pratique",
            "description": "Description détaillée de l'exercice",
            "starter_code": "Code de départ avec # TODO",
            "solution": "Code solution complet",
            "tests": [
                {{"input": "fonction(2, 3)", "expected": "5"}},
                {{"input": "fonction(-1, 1)", "expected": "0"}},
                {{"input": "fonction(0, 0)", "expected": "0"}}
            ]
        }}
        """
        
        result = orchestrator.answer_question(prompt)
        
        if result['success']:
            try:
                # Parser la réponse JSON avec nettoyage robuste
                answer = result['answer'].strip()
                print(f"🔍 Réponse brute reçue: {answer[:500]}...")
                
                # Nettoyer la réponse des blocs de code markdown
                if '```json' in answer:
                    start_marker = answer.find('```json') + 7
                    end_marker = answer.find('```', start_marker)
                    if end_marker != -1:
                        json_content = answer[start_marker:end_marker].strip()
                    else:
                        json_content = answer[start_marker:].strip()
                else:
                    # Extraire le JSON si il y a du texte avant/après
                    start_idx = answer.find('{')
                    end_idx = answer.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_content = answer[start_idx:end_idx]
                    else:
                        raise json.JSONDecodeError("No JSON found", answer, 0)
                
                print(f"🧹 JSON extrait: {json_content[:300]}...")
                
                # Nettoyer les triples quotes Python dans le JSON
                json_content = json_content.replace('"""', '"')
                json_content = json_content.replace("'''", '"')
                
                # Nettoyer les retours à la ligne dans les chaînes
                import re
                json_content = re.sub(r':\s*"([^"]*)\n([^"]*)"', r': "\1\\n\2"', json_content, flags=re.MULTILINE)
                
                print(f"🔧 JSON nettoyé: {json_content[:300]}...")
                
                # Parser le JSON nettoyé
                exercise_data = json.loads(json_content)
                
                # Vérifier que toutes les clés requises sont présentes
                required_keys = ['title', 'description', 'starter_code', 'solution', 'tests']
                for key in required_keys:
                    if key not in exercise_data:
                        raise KeyError(f"Clé manquante: {key}")
                
                # Nettoyer le starter_code et solution des triples quotes
                if isinstance(exercise_data.get('starter_code'), str):
                    # Nettoyer et formater le code de départ
                    starter_code = exercise_data['starter_code']
                    starter_code = starter_code.replace('"""', '').replace("'''", '').strip()
                    # Remplacer les \n par de vrais retours à la ligne
                    starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t')
                    exercise_data['starter_code'] = starter_code
                
                if isinstance(exercise_data.get('solution'), str):
                    # Nettoyer et formater la solution
                    solution = exercise_data['solution']
                    solution = solution.replace('"""', '').replace("'''", '').strip()
                    # Remplacer les \n par de vrais retours à la ligne
                    solution = solution.replace('\\n', '\n').replace('\\t', '\t')
                    exercise_data['solution'] = solution
                
                print(f"✅ Exercice parsé: {exercise_data['title']}")
                
                # Créer l'exercice
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
                
                print(f"✅ Exercice créé avec succès : {exercise.title} (ID: {exercise.id})")
                messages.success(request, f'Exercice "{exercise.title}" généré avec succès à partir du cours !')
                return redirect('exercises:detail', exercise_id=exercise.id)
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"❌ Erreur parsing JSON : {e}")
                print(f"Réponse reçue : {result['answer'][:500]}...")
                
                # Essayer un parsing plus agressif
                try:
                    # Méthode alternative : extraire manuellement les valeurs
                    answer = result['answer']
                    
                    # Extraire le titre
                    title_match = re.search(r'"title":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                    title = title_match.group(1) if title_match else f"Exercice pratique : {topic}"
                    
                    # Extraire la description
                    desc_match = re.search(r'"description":\s*"([^"]*(?:\\.[^"]*)*)"', answer)
                    description = desc_match.group(1) if desc_match else f"Exercice pratique basé sur le cours '{topic}'. Complétez le code ci-dessous pour mettre en pratique les concepts appris."
                    
                    # Extraire le starter_code (entre guillemets ou dans un bloc)
                    starter_match = re.search(r'"starter_code":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                    if not starter_match:
                        # Chercher dans un bloc de code
                        starter_match = re.search(r'"starter_code":\s*```python\n(.*?)```', answer, re.DOTALL)
                    
                    starter_code = starter_match.group(1) if starter_match else f"# Exercice basé sur le cours : {topic}\n# TODO: Implémentez votre solution\n\ndef ma_fonction():\n    # Votre code ici\n    pass"
                    
                    # Extraire la solution
                    solution_match = re.search(r'"solution":\s*"([^"]*(?:\\.[^"]*)*)"', answer, re.DOTALL)
                    if not solution_match:
                        solution_match = re.search(r'"solution":\s*```python\n(.*?)```', answer, re.DOTALL)
                    
                    solution = solution_match.group(1) if solution_match else f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'"
                    
                    # Nettoyer les échappements
                    starter_code = starter_code.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                    solution = solution.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                    
                    # Tests par défaut si pas trouvés
                    tests = [
                        {"input": "ma_fonction()", "expected": "Hello World"}
                    ]
                    
                    # Essayer d'extraire les tests
                    tests_match = re.search(r'"tests":\s*\[(.*?)\]', answer, re.DOTALL)
                    if tests_match:
                        try:
                            tests_str = '[' + tests_match.group(1) + ']'
                            tests = json.loads(tests_str)
                        except:
                            pass  # Garder les tests par défaut
                    
                    print(f"✅ Parsing manuel réussi: {title}")
                    
                    # Créer l'exercice avec les données extraites
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
                    
                    print(f"✅ Exercice créé avec parsing manuel : {exercise.title} (ID: {exercise.id})")
                    messages.success(request, f'Exercice "{exercise.title}" généré avec succès à partir du cours !')
                    return redirect('exercises:detail', exercise_id=exercise.id)
                    
                except Exception as manual_error:
                    print(f"❌ Parsing manuel échoué : {manual_error}")
                
                # Créer un exercice de fallback basique
                fallback_exercise = Exercise.objects.create(
                    title=f"Exercice pratique : {topic}",
                    description=f"Exercice pratique basé sur le cours '{topic}'. Complétez le code ci-dessous pour mettre en pratique les concepts appris.",
                    difficulty=difficulty,
                    topic=topic,
                    starter_code=f"# Exercice basé sur le cours : {topic}\n# TODO: Implémentez votre solution\n\ndef ma_fonction():\n    # Votre code ici\n    pass\n",
                    solution=f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'\n",
                    tests=[
                        {"input": "ma_fonction()", "expected": "Hello World"}
                    ],
                    created_by=request.user
                )
                
                messages.warning(request, f'L\'IA a généré une réponse malformée. Exercice de base créé sur "{topic}".')
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        else:
            print(f"❌ Erreur orchestrateur : {result.get('error', 'Erreur inconnue')}")
            messages.error(request, f'Erreur lors de la génération : {result.get("error", "Erreur inconnue")}')
            
    except Exception as e:
        print(f"❌ Exception lors de la génération : {str(e)}")
        
        # Créer un exercice de fallback en cas d'erreur totale
        try:
            fallback_exercise = Exercise.objects.create(
                title=f"Exercice pratique : {topic}",
                description=f"Exercice pratique basé sur le cours '{topic}'. Complétez le code ci-dessous.",
                difficulty=difficulty,
                topic=topic,
                starter_code=f"# TODO: Implémentez votre solution pour {topic}\n\ndef ma_fonction():\n    # Votre code ici\n    pass\n",
                solution=f"# Solution exemple pour {topic}\n\ndef ma_fonction():\n    return 'Hello World'\n",
                tests=[
                    {"input": "ma_fonction()", "expected": "Hello World"}
                ],
                created_by=request.user
            )
            
            messages.warning(request, f'Erreur lors de la génération IA. Exercice de base créé sur "{topic}".')
            return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        except Exception as fallback_error:
            messages.error(request, f'Erreur lors de la génération : {str(e)}')
    
    return redirect('exercises:list')

@login_required
def user_progress(request):
    """Page de progression utilisateur pour les exercices"""
    
    # Statistiques générales
    total_exercises = Exercise.objects.filter(is_active=True).count()
    completed_exercises = UserExerciseProgress.objects.filter(
        user=request.user,
        is_completed=True
    ).count()
    
    # Progression par difficulté
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
    
    # Exercices récents
    recent_progress = UserExerciseProgress.objects.filter(
        user=request.user
    ).select_related('exercise').order_by('-first_attempt_at')[:10]
    
    # Soumissions récentes
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