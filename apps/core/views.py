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
    # Rediriger vers le générateur de cours par défaut
    from django.shortcuts import redirect
    return redirect('courses:generator')