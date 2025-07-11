from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from apps.agents.orchestrator import get_orchestrator
import json

@login_required
def course_generator(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        difficulty = request.POST.get('difficulty')
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.generate_course(topic, difficulty)
        
        if result['success']:
            context = {
                'generated_course': {
                    'topic': result['topic'],
                    'difficulty': result['difficulty'],
                    'content': result['content'],
                    'sources': result['sources']
                }
            }
        else:
            context = {
                'error': result.get('error', 'Erreur lors de la génération du cours'),
                'topic': topic,
                'difficulty': difficulty
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    return render(request, 'courses/generate.html')

@login_required
def course_detail(request, course_id):
    # Logique pour afficher un cours spécifique
    context = {
        'course': {
            'id': course_id,
            'title': 'Cours exemple',
            'content': 'Contenu du cours...'
        }
    }
    return render(request, 'courses/course_detail.html', context)