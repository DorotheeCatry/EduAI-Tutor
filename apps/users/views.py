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
import os
from django.conf import settings
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
        response = super().dispatch(request, *args, **kwargs)
        messages.success(request, 'Vous avez été déconnecté avec succès.')
        return response
    

class ProfileView(LoginRequiredMixin, UpdateView):
    """
    Vue de modification du profil utilisateur.
    """
    model = KodaUser
    fields = ['username', 'email', 'bio', 'language_preference']
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Récupérer tous les avatars disponibles
        koda_path = os.path.join(settings.BASE_DIR, 'static', 'koda')
        
        available_avatars = []
        if os.path.exists(koda_path):
            for filename in os.listdir(koda_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Créer un nom d'affichage plus joli
                    display_name = filename.replace('koda_', '').replace('.png', '').replace('_', ' ').title()
                    available_avatars.append({
                        'filename': filename,
                        'display_name': display_name,
                        'url': f'/static/koda/{filename}'
                    })
        
        # Trier par nom d'affichage
        available_avatars.sort(key=lambda x: x['display_name'])
        context['available_avatars'] = available_avatars
        
        # Avatar actuel de l'utilisateur
        current_avatar = self.request.user.avatar
        if current_avatar and hasattr(current_avatar, 'url') and current_avatar.name:
            # Si c'est un fichier uploadé
            context['current_avatar_url'] = current_avatar.url
            context['current_avatar_type'] = 'uploaded'
        else:
            # Si c'est un avatar Koda par défaut
            avatar_name = str(current_avatar) if current_avatar else 'koda_base.png'
            context['current_avatar_url'] = f'/static/koda/{avatar_name}'
            context['current_avatar_type'] = 'koda'
            context['current_avatar_name'] = avatar_name
        
        return context
    
    def form_valid(self, form):
        # Gérer la sélection d'avatar Koda
        selected_koda_avatar = self.request.POST.get('selected_koda_avatar')
        if selected_koda_avatar:
            # Supprimer l'ancien avatar uploadé s'il existe
            if form.instance.avatar and hasattr(form.instance.avatar, 'delete') and form.instance.avatar.name:
                form.instance.avatar.delete()
            # Définir l'avatar comme nom de fichier Koda
            form.instance.avatar = selected_koda_avatar
        
        # Gérer l'avatar recadré si présent
        cropped_avatar = self.request.POST.get('cropped_avatar')
        if cropped_avatar:
            # Supprimer l'ancien avatar s'il existe
            if form.instance.avatar and hasattr(form.instance.avatar, 'delete'):
                form.instance.avatar.delete()
            # Décoder l'image base64
            format, imgstr = cropped_avatar.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'avatar_{uuid.uuid4()}.{ext}')
            form.instance.avatar = data
        
        messages.success(self.request, 'Profil mis à jour avec succès !')
        return super().form_valid(form)