from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from apps.agents.orchestrator import get_orchestrator
import json

@login_required
def search_chat(request):
    return render(request, 'chat/chat.html')

@csrf_exempt
@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message')
            
            if not message:
                return JsonResponse({'error': 'Message vide'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Format JSON invalide'}, status=400)
        
        # Utiliser l'orchestrateur IA pour répondre
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.answer_question(message)
        
        if result['success']:
            response = {
                'response': result['answer'],
                'sources': result['sources'],
                'timestamp': '12:34:56'
            }
        else:
            response = {
                'response': f"Désolé, je n'ai pas pu traiter votre question : {result.get('error', 'Erreur inconnue')}",
                'sources': [],
                'timestamp': '12:34:56'
            }
        
        return JsonResponse(response)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)