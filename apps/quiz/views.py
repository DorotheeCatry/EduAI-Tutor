from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from apps.agents.agent_orchestrator import get_orchestrator
import json

@login_required
def quiz_lobby(request):
    return render(request, 'quiz/quiz_lobby.html')

@login_required
def quiz_start(request):
    mode = request.GET.get('mode', 'solo')
    topic = request.GET.get('topic', 'Python général')

    # Générer un quiz avec l'IA
    orchestrator = get_orchestrator(request.user)
    try:
        num_questions = int(request.GET.get('num_questions', 10))
        if num_questions < 1 or num_questions > 50:
            num_questions = 10
    except (TypeError, ValueError):
        num_questions = 10
        
    result = orchestrator.create_quiz(topic, num_questions)

    # Vérifie que des questions ont bien été retournées
    quiz_data = result if result and "questions" in result and result["questions"] else None

    context = {
        'mode': mode,
        'topic': topic,
        'quiz_data': quiz_data,
        'error': None if quiz_data else "⚠️ Aucun quiz n’a pu être généré."
    }
    return render(request, 'quiz/quiz_start.html', context)

@csrf_exempt
@login_required
def submit_quiz(request):
    """API endpoint pour soumettre les résultats d'un quiz"""
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        answers = data.get('answers', [])
        quiz_data = data.get('quiz_data', {})
        
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.submit_quiz_results(session_id, answers, quiz_data)
        
        return JsonResponse(result)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
@login_required
def quiz_result(request):
    return render(request, 'quiz/quiz_result.html')