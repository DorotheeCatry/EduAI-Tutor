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
        module = request.POST.get('module', '')
        
        # Construire le sujet complet
        if module and module != 'general':
            full_topic = f"{topic} (module: {module})"
        else:
            full_topic = topic
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.generate_course(full_topic, difficulty)
        
        if result['success']:
            context = {
                'generated_course': {
                    'topic': topic,
                    'module': module,
                    'difficulty': result['difficulty'],
                    'content': result['content'],
                    'sources': result['sources']
                },
                'modules': get_available_modules()
            }
        else:
            context = {
                'error': result.get('error', 'Erreur lors de la génération du cours'),
                'topic': topic,
                'difficulty': difficulty,
                'modules': get_available_modules()
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    context = {
        'modules': get_available_modules()
    }
    return render(request, 'courses/generate.html', context)

def get_available_modules():
    """Retourne la liste des modules disponibles"""
    return [
        {'id': 'general', 'name': 'Général', 'description': 'Concepts généraux'},
        {'id': 'python_basics', 'name': 'Python - Bases', 'description': 'Variables, types, conditions, boucles'},
        {'id': 'python_functions', 'name': 'Python - Fonctions', 'description': 'Fonctions, décorateurs, lambda'},
        {'id': 'python_oop', 'name': 'Python - POO', 'description': 'Classes, héritage, polymorphisme'},
        {'id': 'python_advanced', 'name': 'Python - Avancé', 'description': 'Métaclasses, descripteurs, async'},
        {'id': 'web_apis', 'name': 'APIs Web', 'description': 'REST, FastAPI, Django REST'},
        {'id': 'databases', 'name': 'Bases de données', 'description': 'SQL, ORM, migrations'},
        {'id': 'testing', 'name': 'Tests', 'description': 'Unittest, pytest, TDD'},
        {'id': 'deployment', 'name': 'Déploiement', 'description': 'Docker, CI/CD, cloud'},
    ]
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