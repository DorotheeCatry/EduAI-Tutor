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
from django.templatetags.static import static
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
    fields = ['username', 'email', 'bio', 'language_preference', 'avatar']
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Récupérer tous les avatars disponibles
        koda_path = os.path.join(settings.STATIC_ROOT or 'static', 'koda')
        if not os.path.exists(koda_path):
            koda_path = os.path.join('static', 'koda')

        available_avatars = []
        if os.path.exists(koda_path):
            for filename in os.listdir(koda_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    display_name = filename.replace('koda_', '').replace('.png', '').replace('_', ' ').title()
                    available_avatars.append({
                        'filename': filename,
                        'display_name': display_name,
                        'url': f'/static/koda/{filename}'
                    })

        available_avatars.sort(key=lambda x: x['display_name'])
        context['available_avatars'] = available_avatars

        current_avatar = self.request.user.avatar
        if current_avatar and hasattr(current_avatar, 'name'):
            context['current_avatar_url'] = current_avatar.url
            context['current_avatar_type'] = 'uploaded'
        else:
            avatar_name = current_avatar or 'koda_base.png'
            context['current_avatar_url'] = f'/static/koda/{avatar_name}'
            context['current_avatar_type'] = 'koda'
            context['current_avatar_name'] = avatar_name

        return context

    def form_valid(self, form):
        selected_koda_avatar = self.request.POST.get('selected_koda_avatar')
        cropped_avatar = self.request.POST.get('cropped_avatar')

        if selected_koda_avatar:
            if form.instance.avatar and hasattr(form.instance.avatar, 'delete'):
                form.instance.avatar.delete(save=False)
            from django.core.files.base import File
            koda_path = os.path.join(settings.BASE_DIR, 'static', 'koda', selected_koda_avatar)
            with open(koda_path, 'rb') as f:
                form.instance.avatar.save(selected_koda_avatar, File(f), save=False)

        elif cropped_avatar:
            try:
                format, imgstr = cropped_avatar.split(';base64,')
                ext = format.split('/')[-1]
                data = ContentFile(base64.b64decode(imgstr), name=f'avatar_{uuid.uuid4()}.{ext}')

                if form.instance.avatar and hasattr(form.instance.avatar, 'delete'):
                    form.instance.avatar.delete(save=False)

                form.instance.avatar = data
            except Exception as e:
                messages.error(self.request, f"Erreur lors de la sauvegarde de l'avatar : {e}")

        messages.success(self.request, 'Profil mis à jour avec succès !')
        return super().form_valid(form)


def get_koda_avatars():
    # Tu peux scanner un dossier static ou stocker en base si tu veux
    return [
        {"filename": "avatar_koda_base.png", "url": static("koda/avatar_koda_base.png"), "display_name": "Koda Classic"},
        {"filename": "avatar_koda_ninja.png", "url": static("koda/avatar_koda_ninja.png"), "display_name": "Ninja Koda"},
        {"filename": "avatar_koda_zen.png", "url": static("koda/avatar_koda_zen.png"), "display_name": "Zen Koda"},
    ]

def get_koda_url(filename):
    if filename:
        return static(f'koda/{filename}')
    return static('koda/avatar_koda_base.png')
