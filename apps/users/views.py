from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
import base64
import uuid
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
    
    def get_next_page(self):
        return reverse_lazy('users:login')
    
    def dispatch(self, request, *args, **kwargs):
        messages.info(request, 'Vous avez été déconnecté avec succès.')
        return super().dispatch(request, *args, **kwargs)

class ProfileView(LoginRequiredMixin, UpdateView):
    """
    Vue de modification du profil utilisateur.
    """
    model = KodaUser
    fields = ['username', 'email', 'bio', 'avatar', 'language_preference']
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        # Gérer l'avatar recadré si présent
        cropped_avatar = self.request.POST.get('cropped_avatar')
        if cropped_avatar:
            # Décoder l'image base64
            format, imgstr = cropped_avatar.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'avatar_{uuid.uuid4()}.{ext}')
            form.instance.avatar = data
        
        messages.success(self.request, 'Profil mis à jour avec succès !')
        return super().form_valid(form)