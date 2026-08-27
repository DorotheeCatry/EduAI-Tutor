"""
URL configuration for eduai_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from django.views.i18n import set_language
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

def redirect_to_login(request):
    """Redirects to default login page"""
    return redirect('users:login')

def redirect_to_courses(request):
    """Redirects to courses if logged in, otherwise to login"""
    if request.user.is_authenticated:
        return redirect('courses:generator')
    return redirect('users:login')

urlpatterns = [
    path('i18n/setlang/', set_language, name='set_language'),  # 💬 View to change language
    path('admin/', admin.site.urls),
    path("__reload__/", include("django_browser_reload.urls")),

    # Custom app routes
    path('', redirect_to_courses),                      # Smart redirection
    path('auth/', include('apps.users.urls')),          # authentication
    path('courses/', include('apps.courses.urls')),
    path('quiz/', include('apps.quiz.urls')),
    path('revision/', include('apps.revision.urls')),
    path('chat/', include('apps.chat.urls')),
    path('tracker/', include('apps.tracker.urls')),
    path('exercises/', include('apps.exercises.urls')),

    # --- API REST du jeu de données (C5, Bloc 1) ---
    #
    # Préfixe distinct de celui que prendra l'API du service IA (C9, Bloc 2),
    # qui vivra dans un service FastAPI séparé. La séparation exigée par le
    # référentiel se lit ainsi dans l'URL, avant d'ouvrir le code.
    path('api/dataset/', include('apps.api_data.urls')),

    # --- Documentation OpenAPI de l'API du jeu de données ---
    #
    # Le schéma est engendré depuis le code : sérialiseurs, filtres et
    # permissions en sont la source. Une documentation écrite à la main
    # diverge du code dès la première modification, et une documentation
    # fausse est pire qu'absente — elle est crue.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'),
         name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'),
         name='redoc'),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)