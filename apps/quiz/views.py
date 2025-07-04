from django.shortcuts import render
from django.http import JsonResponse

def quiz_lobby(request):
    return render(request, 'quiz/quiz_lobby.html')

def quiz_start(request):
    mode = request.GET.get('mode', 'solo')
    context = {
        'mode': mode
    }
    return render(request, 'quiz/quiz_start.html', context)

def quiz_result(request):
    return render(request, 'quiz/quiz_result.html')