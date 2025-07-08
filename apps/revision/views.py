from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def flashcards(request):
    return render(request, 'revision/flashcards.html')

@login_required
def review(request):
    return render(request, 'revision/review.html')