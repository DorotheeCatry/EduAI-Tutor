from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

class AuthenticationMiddleware:
    """
    Middleware pour rediriger automatiquement les utilisateurs non connectés
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # URLs qui ne nécessitent pas d'authentification
        public_urls = [
            '/auth/login/',
            '/auth/register/',
            '/admin/',
            '/static/',
            '/media/',
            '/__reload__/',
            '/i18n/',
        ]
        
        # Vérifier si l'URL actuelle est publique
        is_public = any(request.path.startswith(url) for url in public_urls)
        
        # Si l'utilisateur n'est pas connecté et essaie d'accéder à une page protégée
        if not request.user.is_authenticated and not is_public:
            return redirect('/auth/login/')
        
        # Si l'utilisateur est connecté et essaie d'accéder à login/register
        if request.user.is_authenticated and request.path in ['/auth/login/', '/auth/register/']:
            return redirect('/courses/generator/')
        
        response = self.get_response(request)
        return response