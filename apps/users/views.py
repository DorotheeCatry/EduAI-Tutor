from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import RegisterForm, LoginForm
from .models import KodaUser

class CustomLoginView(LoginView):
    """
    Vue de connexion personnalisée.
    """
    form_class = LoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('courses:generator')
    
    def form_valid(self, form):
        messages.success(self.request, 'Connexion réussie ! Bienvenue.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Erreur de connexion. Vérifiez vos identifiants.')
        return super().form_invalid(form)

class RegisterView(CreateView):
    """
    Vue d'inscription personnalisée.
    """
    model = KodaUser
    form_class = RegisterForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        # Forcer le rôle étudiant pour tous les nouveaux utilisateurs
        form.instance.role = KodaUser.Role.STUDENT
        response = super().form_valid(form)
        messages.success(self.request, 'Compte créé avec succès ! Vous pouvez maintenant vous connecter.')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Erreur lors de la création du compte. Vérifiez les informations saisies.')
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    """
    Vue de déconnexion personnalisée.
    """
    next_page = reverse_lazy('users:login')
    
    def dispatch(self, request, *args, **kwargs):
        messages.info(request, 'Vous avez été déconnecté avec succès.')
        return super().dispatch(request, *args, **kwargs)