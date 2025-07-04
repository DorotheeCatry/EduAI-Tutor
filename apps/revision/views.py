from django.shortcuts import render

def flashcards(request):
    return render(request, 'revision/flashcards.html')

def review(request):
    return render(request, 'revision/review.html')