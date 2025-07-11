from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def homepage(request):
    """Render the homepage for authenticated users.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: Rendered homepage template.
    """
    return render(request, 'core/homepage.html')