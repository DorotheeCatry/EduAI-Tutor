from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def homepage(request):
    """Redirect to course generator."""
    return redirect('courses:generator')