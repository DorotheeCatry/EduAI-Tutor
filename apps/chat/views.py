from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from apps.agents.agent_orchestrator import get_orchestrator
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
                return JsonResponse({'error': 'Empty message'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        
        # Use AI orchestrator to respond
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.answer_question(message)
        
        if result['success']:
            # Don't include sources in response
            response = {
                'response': result['answer'],
                'timestamp': '12:34:56'
            }
        else:
            response = {
                'response': f"Sorry, I couldn't process your question: {result.get('error', 'Unknown error')}",
                'timestamp': '12:34:56'
            }
        
        return JsonResponse(response)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)