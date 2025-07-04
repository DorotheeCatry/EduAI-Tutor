from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def course_generator(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        difficulty = request.POST.get('difficulty')
        
        # Ici vous pourrez intégrer votre logique IA pour générer le cours
        # Pour l'instant, on simule une réponse
        
        context = {
            'generated_course': {
                'topic': topic,
                'difficulty': difficulty,
                'content': f"Cours généré sur {topic} (niveau {difficulty})"
            }
        }
        return render(request, 'courses/course_detail.html', context)
    
    return render(request, 'courses/generate.html')

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