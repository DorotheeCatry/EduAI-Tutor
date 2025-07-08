from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def quiz_lobby(request):
    return render(request, 'quiz/quiz_lobby.html')

@login_required
def quiz_start(request):
    mode = request.GET.get('mode', 'solo')
    context = {
        'mode': mode
    }
    return render(request, 'quiz/quiz_start.html', context)

@login_required
def quiz_result(request):
    return render(request, 'quiz/quiz_result.html')