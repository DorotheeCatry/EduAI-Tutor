from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def homepage(request):
    return render(request, 'courses/generate.html')