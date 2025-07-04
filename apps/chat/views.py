from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def search_chat(request):
    return render(request, 'chat/chat.html')

@csrf_exempt
def send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message')
        
        # Ici vous pourrez intégrer votre logique IA pour répondre
        # Pour l'instant, on simule une réponse
        
        response = {
            'response': f"Réponse IA à: {message}",
            'timestamp': '12:34:56'
        }
        
        return JsonResponse(response)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)