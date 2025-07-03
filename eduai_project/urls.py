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
from django.views.i18n import set_language


urlpatterns = [
    path('i18n/setlang/', set_language, name='set_language'),  # 💬 Vue pour changer la langue
]

urlpatterns += [
    path('admin/', admin.site.urls),
    path("__reload__/", include("django_browser_reload.urls")),

    # Routes des apps personnalisées
    path('', include('apps.core.urls')),                # page d'accueil ou layout général
    #path('users/', include('apps.users.urls')),        # inscription, connexion, profil
    #path('courses/', include('apps.courses.urls')),
    #path('quiz/', include('apps.quiz.urls')),
    #path('revision/', include('apps.revision.urls')),
    #path('agents/', include('apps.agents.urls')),
    #path('rag/', include('apps.rag.urls')),
    #path('chat/', include('apps.chat.urls')),
    #path('tracker/', include('apps.tracker.urls')),
]