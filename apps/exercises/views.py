from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from apps.agents.agent_orchestrator import get_orchestrator
from apps.quotas.service import QuotaDepasse
from django.views.decorators.http import require_POST
from .models import Exercise, ExerciseSubmission, UserExerciseProgress
from .security import secure_executor
import json
import time
from django.utils.translation import gettext as _
from apps.chat.actions import actions_pour
from apps.chat.contexte import contexte_d_exercice
from apps.referentiel.services import (
    competence_par_code,
    competences_du_referentiel_actif,
)

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
        # Les compétences du référentiel actif, groupées par module : c'est ce
        # que le formulaire de génération propose. Liste vide si aucun
        # référentiel n'est actif — le formulaire retombe alors sur le sujet
        # libre, et le dit.
        'competences_par_module': competences_du_referentiel_actif(),
    }
    
    return render(request, 'exercises/exercise_list.html', context)


@login_required
def carnet(request):
    """
    Plusieurs exercices à la suite, dans une seule page.

    Compétence visée : C17 (épreuve E4)

    Un exercice à la fois convient pour vérifier une notion ; une séance de
    travail en enchaîne plusieurs. C'est la forme du carnet, et celle que les
    apprenants connaissent par Jupyter.

    Choix : la sélection arrive par un paramètre répété `exercice`, et un
    identifiant inconnu est simplement ignoré. Motivation : la liste peut avoir
    changé entre l'affichage et l'envoi — un exercice retiré ne doit pas faire
    échouer la séance entière, il doit en sortir.

    Choix : la solution n'est JAMAIS transmise à la page (décision 029). Un
    carnet qui la contiendrait cesserait d'être un exercice.
    """
    from apps.exercises.generation_carnet import MAXIMUM, MINIMUM, engendrer
    from apps.quotas.service import QuotaDepasse

    identifiants = []
    for brut in request.GET.getlist('exercice'):
        try:
            identifiants.append(int(brut))
        except (TypeError, ValueError):
            continue

    exercices = (Exercise.objects
                 .filter(is_active=True, id__in=identifiants)
                 .select_related('competence')
                 .order_by('created_at'))

    # Les énoncés engendrés vivent dans la SESSION, pas dans le catalogue.
    #
    # Compétence visée : C17 (épreuve E4)
    # Motivation : un exercice du catalogue porte des tests et se corrige. Ceux
    # d'un carnet n'en ont pas — le carnet accompagne, il ne mesure pas. Les
    # enregistrer comme exercices remplirait la liste d'entrées que le
    # correcteur ne saurait pas traiter. La session les garde le temps de la
    # séance, et le fichier `.ipynb` les emporte pour de bon.
    engendres = request.session.get('carnet_engendre', [])
    sujet = (request.GET.get('sujet') or '').strip()
    refus = ''

    if sujet:
        try:
            nombre = int(request.GET.get('nombre', MINIMUM))
        except (TypeError, ValueError):
            nombre = MINIMUM
        try:
            engendres = engendrer(request.user, sujet, nombre)
        except QuotaDepasse as depassement:
            refus = depassement.message
            engendres = []
        request.session['carnet_engendre'] = engendres

    for rang, entree in enumerate(engendres):
        entree['cle'] = f'g{rang}'

    # Les énoncés sont du Markdown — titres, listes, blocs de code — produits
    # par le même agent que les cours. Les afficher en texte brut laisserait
    # leurs dièses et leurs accents graves à l'écran (décision 002).
    from apps.courses.views import render_markdown

    return render(request, 'exercises/carnet.html', {
        'exercices': [{
            'cle': str(exercice.id),
            'titre': exercice.title,
            'competence': exercice.competence.intitule if exercice.competence else '',
            'difficulte': exercice.get_difficulty_display(),
            'code': exercice.starter_code,
            'enonce_html': render_markdown(exercice.description),
        } for exercice in exercices] + [{
            'cle': entree['cle'],
            'titre': entree['titre'],
            'competence': sujet or '',
            'difficulte': '',
            'code': entree['code'],
            'enonce_html': render_markdown(entree['enonce']),
            'engendre': True,
        } for entree in engendres],
        'aucun_choix': not identifiants and not engendres,
        'refus_de_quota': refus,
        'minimum': MINIMUM,
        'maximum': MAXIMUM,
    })


@login_required
@require_POST
def carnet_ipynb(request):
    """
    Rend la séance sous la forme d'un carnet Jupyter téléchargeable.

    Compétence visée : C17 (épreuve E4)

    Choix : une requête POST portant le code réellement saisi, et non un lien
    qui régénérerait le carnet depuis la base. Motivation : l'apprenant
    télécharge ce qu'il a écrit — résolu ou non. Un lien rendrait toujours le
    code de départ, et le fichier ne vaudrait rien comme trace de travail.

    Choix : `Content-Disposition: attachment`. Motivation : sans lui, le
    navigateur affiche le JSON dans l'onglet, et l'apprenant doit deviner
    comment l'enregistrer avec la bonne extension.
    """
    from apps.exercises.carnet import composer, en_json

    codes, codes_engendres = {}, {}
    for cle, valeur in request.POST.items():
        if not cle.startswith('code-'):
            continue
        reference = cle.removeprefix('code-')
        try:
            codes[int(reference)] = valeur
        except ValueError:
            # Une clé qui n'est pas un nombre désigne un énoncé engendré.
            codes_engendres[reference] = valeur

    exercices = (Exercise.objects
                 .filter(is_active=True, id__in=list(codes))
                 .select_related('competence')
                 .order_by('created_at'))

    entrees = [{
        'titre': exercice.title,
        'enonce': exercice.description,
        'competence': exercice.competence.intitule if exercice.competence else '',
        'code': codes.get(exercice.id, exercice.starter_code),
    } for exercice in exercices]

    # Les énoncés engendrés ne sont pas en base : leur texte vient de la
    # session, et seul leur code arrive du formulaire.
    for rang, entree in enumerate(request.session.get('carnet_engendre', [])):
        cle = f'g{rang}'
        if cle not in codes_engendres:
            continue
        entrees.append({
            'titre': entree.get('titre', ''),
            'enonce': entree.get('enonce', ''),
            'competence': '',
            'code': codes_engendres[cle],
        })

    carnet_json = en_json(composer(
        str(_("Séance d'exercices — EduAI Tutor")), entrees))

    reponse = HttpResponse(carnet_json,
                           content_type='application/x-ipynb+json; charset=utf-8')
    reponse['Content-Disposition'] = 'attachment; filename="seance-eduai.ipynb"'
    return reponse


@login_required
@require_POST
def carnet_executer(request):
    """
    Exécute une cellule du carnet, sans rien enregistrer.

    Compétence visée : C17 (épreuve E4)
    Compétences concernées : C13 (E3) — sécurité ; C21 (E5)

    Choix : le même exécuteur restreint que partout ailleurs, et la même
    conversion des sessions au prompt. Motivation : un second chemin
    d'exécution serait une seconde surface d'attaque, et il finirait par
    diverger — le projet a déjà eu deux chats et deux mises en forme qui
    avaient divergé.

    Choix : rien n'est enregistré. Motivation : le carnet sert à essayer. La
    correction par les tests et l'enregistrement d'une soumission restent le
    fait de l'exercice seul, qui mesure ; le carnet accompagne.
    """
    from apps.courses.transcription import transcrire
    from apps.exercises.security import SecurePythonExecutor

    extrait = (request.POST.get('code') or '').strip()
    if not extrait:
        return JsonResponse({'error': str(_('Aucun code à exécuter.'))}, status=400)

    resultat = SecurePythonExecutor().execute_code(transcrire(extrait))
    return JsonResponse({
        'succes': bool(resultat.get('success')),
        'sortie': resultat.get('output') or '',
        'erreur': resultat.get('error') or '',
        'expire': bool(resultat.get('timeout')),
    })

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
    
    # Contexte transmis au tuteur : l'énoncé, le code saisi et la dernière
    # erreur. Composé ICI, côté serveur, et écrit dans la page — la bannière du
    # panneau et la requête lisent la même source, si bien qu'un contexte
    # absent se voit à l'écran (décision 029).
    #
    # La solution attendue n'est PAS transmise : un tuteur qui l'a la donne, et
    # l'exercice cesse de mesurer une production.
    derniere = recent_submissions[0] if recent_submissions else None
    contexte_tuteur = contexte_d_exercice(
        exercise,
        code_saisi=derniere.submitted_code if derniere else None,
        derniere_erreur=derniere.error_message if derniere else None,
    )
    contexte_tuteur['actions'] = [
        {'code': action['code'], 'libelle': str(action['libelle'])}
        for action in actions_pour('exercice')
    ]

    # L'énoncé est du Markdown, produit par le même agent que les cours : il
    # porte des listes, des exemples et des blocs de code. `linebreaks` ne
    # convertissait que les sauts de ligne, et laissait dièses et accents
    # graves à l'écran (décision 002).
    from apps.courses.views import render_markdown

    context = {
        'exercise': exercise,
        'enonce_html': render_markdown(exercise.description),
        'progress': progress,
        'recent_submissions': recent_submissions,
        'contexte_tuteur': contexte_tuteur,
    }
    
    return render(request, 'exercises/exercise_detail.html', context)

@login_required
def submit_code(request, exercise_id):
    """
    Exécute le code soumis et enregistre le résultat.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — CSRF

    `@csrf_exempt` est RETIRÉ. Cette vue écrit une soumission, met à jour la
    progression et attribue des XP : sans protection CSRF, elle était
    déclenchable depuis n'importe quelle page tierce ouverte dans le navigateur
    de l'apprenant.

    L'exemption était en outre inutile — le gabarit envoie déjà l'en-tête
    `X-CSRFToken`. Troisième occurrence du même geste dans ce projet
    (réserve 14).
    """
    
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
        print("📊 Résultats des tests:")
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
        difficulty = request.POST.get('difficulty', 'beginner')

        # Le rattachement au référentiel vient d'un CHOIX, jamais d'une
        # déduction sur le sujet libre. Voir la décision 027 : un rattachement
        # approché produirait une progression fausse et muette.
        #
        # Quand une compétence est choisie, son intitulé devient le sujet
        # transmis au modèle : c'est ce que l'apprenant a demandé, et cela
        # garantit que le sujet de l'exercice et la compétence qu'il vise
        # désignent la même chose.
        competence = competence_par_code(request.POST.get('competence', '').strip())
        topic = (competence.intitule if competence
                 else request.POST.get('topic', '').strip())

        if not topic:
            messages.error(request, _('Please specify a topic for the exercise.'))
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
                        created_by=request.user,
                        competence=competence,
                    )
                    
                    print(f"✅ Exercise created successfully: {exercise.title} (ID: {exercise.id})")
                    messages.success(request, _('Exercise "%(titre)s" generated successfully!') % {"titre": exercise.title})
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
                            except (json.JSONDecodeError, ValueError) as erreur:
                                # Exception nommée et journalisée : un « except »
                                # nu masquait aussi les interruptions clavier et
                                # les erreurs de programmation.
                                print(f"⚠️ Tests non analysables, valeurs par défaut conservées : {erreur}")
                        
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
                            created_by=request.user,
                            competence=competence,
                        )
                        
                        print(f"✅ Exercise created with manual parsing: {exercise.title} (ID: {exercise.id})")
                        messages.success(request, _('Exercise "%(titre)s" generated successfully!') % {"titre": exercise.title})
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
                        created_by=request.user,
                        # Repli : voir le commentaire de l'autre point de
                        # création. Un exercice qui se réussit en secondes ne
                        # doit pas faire progresser une compétence.
                        competence=None,
                    )
                    
                    messages.warning(request, _('AI generated a malformed response. Basic exercise created on "%(sujet)s".') % {"sujet": topic})
                    return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            else:
                print(f"❌ Orchestrator error: {result.get('error', 'Unknown error')}")
                messages.error(request, _("Generation error: %(erreur)s") % {"erreur": result.get("error", _("Unknown error"))})
                
        # Quota de génération (C13) : intercepté AVANT le `except Exception`
        # qui suit. Celui-ci fabrique un exercice de repli — comportement juste
        # pour une panne du modèle, absurde pour un refus : il créerait du
        # contenu tout en masquant à l'apprenant la raison du refus.
        except QuotaDepasse as depassement:
            messages.warning(request, depassement.message)
            return redirect('exercises:list')

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
                    created_by=request.user,
                    # PAS de rattachement au référentiel, volontairement.
                    #
                    # Compétence visée : C17 (épreuve E4)
                    #
                    # Cet exercice est un repli : la génération a échoué, et
                    # ce qui est créé est un gabarit vide dont la solution
                    # attendue est `return 'Hello World'`. Il se réussit en
                    # quelques secondes sans rien démontrer.
                    #
                    # Le rattacher ferait progresser une compétence par un
                    # exercice qui ne la travaille pas : trois échecs de
                    # génération suffiraient à obtenir un niveau 2. Il
                    # s'affiche donc « hors référentiel », ce qui est exact.
                    competence=None,
                )
                
                messages.warning(request, _('AI generation error. Basic exercise created on "%(sujet)s".') % {"sujet": topic})
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
            except Exception:
                messages.error(request, _("Generation error: %(erreur)s") % {"erreur": e})
    
    return redirect('exercises:list')

@login_required
def generate_exercise_from_course(request):
    """
    Génère un exercice à partir du sujet d'un cours.

    Compétence visée : C17 (épreuve E4)

    Ce chemin ne rattache PAS l'exercice à une compétence : il part du sujet
    d'un cours, texte libre, et aucun choix n'y est demandé. L'exercice produit
    s'affiche donc « hors référentiel » et ne compte pas dans la progression.

    Choix : laisser le rattachement vide plutôt que de le déduire du sujet du
    cours. Motivation : la même que pour la génération ordinaire — un
    rattachement approché produirait une progression fausse et muette, là où un
    rattachement absent se lit sur l'écran (décision 027).
    """
    # Rattachement volontairement absent sur ce chemin : voir la docstring.
    competence = None

    topic = request.GET.get('topic', '').strip()
    difficulty = request.GET.get('difficulty', 'intermediate')  # Default difficulty for courses
    
    if not topic:
        messages.error(request, _('No topic specified to generate the exercise.'))
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
                    created_by=request.user,
                    competence=competence,
                )
                
                print(f"✅ Exercise created successfully: {exercise.title} (ID: {exercise.id})")
                messages.success(request, _('Exercise "%(titre)s" generated successfully from course!') % {"titre": exercise.title})
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
                        except (json.JSONDecodeError, ValueError) as erreur:
                            # Même correction qu'au bloc précédent.
                            print(f"⚠️ Tests non analysables, valeurs par défaut conservées : {erreur}")
                    
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
                        created_by=request.user,
                        competence=competence,
                    )
                    
                    print(f"✅ Exercise created with manual parsing: {exercise.title} (ID: {exercise.id})")
                    messages.success(request, _('Exercise "%(titre)s" generated successfully from course!') % {"titre": exercise.title})
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
                    created_by=request.user,
                    # PAS de rattachement au référentiel, volontairement.
                    #
                    # Compétence visée : C17 (épreuve E4)
                    #
                    # Cet exercice est un repli : la génération a échoué, et
                    # ce qui est créé est un gabarit vide dont la solution
                    # attendue est `return 'Hello World'`. Il se réussit en
                    # quelques secondes sans rien démontrer.
                    #
                    # Le rattacher ferait progresser une compétence par un
                    # exercice qui ne la travaille pas : trois échecs de
                    # génération suffiraient à obtenir un niveau 2. Il
                    # s'affiche donc « hors référentiel », ce qui est exact.
                    competence=None,
                )
                
                messages.warning(request, _('AI generated a malformed response. Basic exercise created on "%(sujet)s".') % {"sujet": topic})
                return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        else:
            print(f"❌ Orchestrator error: {result.get('error', 'Unknown error')}")
            messages.error(request, _("Generation error: %(erreur)s") % {"erreur": result.get("error", _("Unknown error"))})
            
    # Voir la vue précédente : le refus de quota ne doit pas emprunter le
    # chemin de repli, qui créerait un exercice sans que rien n'explique
    # pourquoi la génération n'a pas eu lieu.
    except QuotaDepasse as depassement:
        messages.warning(request, depassement.message)
        return redirect('exercises:list')

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
            
            messages.warning(request, _('AI generation error. Basic exercise created on "%(sujet)s".') % {"sujet": topic})
            return redirect('exercises:detail', exercise_id=fallback_exercise.id)
        except Exception:
            messages.error(request, _("Generation error: %(erreur)s") % {"erreur": e})
    
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

@require_POST
@login_required
def delete_exercise(request, exercise_id):
    """Delete an exercise (creator only)"""
    try:
        exercise = get_object_or_404(Exercise, id=exercise_id)
        
        # Check if user is the creator
        if exercise.created_by != request.user:
            messages.error(request, _('You can only delete exercises you created.'))
            return redirect('exercises:list')
        
        exercise_title = exercise.title
        exercise.delete()
        messages.success(request, _('Exercise "%(titre)s" deleted successfully!') % {"titre": exercise_title})
        
    except Exercise.DoesNotExist:
        messages.error(request, _('Exercise not found.'))
    except Exception as e:
        messages.error(request, _("Error deleting exercise: %(erreur)s") % {"erreur": e})
    
    return redirect('exercises:list')
