import logging

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.utils.translation import gettext_lazy as _
from django.views import View
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
from .effacement import inventorier, supprimer_compte

logger_users = logging.getLogger(__name__)

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
        messages.success(self.request, 'Login successful! Welcome.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Login error. Check your credentials.')
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
        # Force student role for all new users
        form.instance.role = KodaUser.Role.STUDENT
        # Set default Koda avatar
        if not form.instance.avatar:
            form.instance.koda_avatar = "koda_base.png"
        response = super().form_valid(form)
        messages.success(self.request, 'Account created successfully! You can now log in.')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Account creation error. Check the entered information.')
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    """
    Vue de déconnexion personnalisée.
    """
    def get_next_page(self):
        return reverse_lazy('users:login')
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        messages.success(request, 'You have been logged out successfully.')
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
        # Get all available avatars
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
                messages.error(self.request, f"Avatar save error: {e}")

        messages.success(self.request, 'Profile updated successfully!')
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


class SuppressionCompteView(LoginRequiredMixin, View):
    """
    Suppression du compte de l'utilisateur connecté.

    Compétence visée : C4 (épreuve E1) — droit à l'effacement, article 17
    Compétence visée : C17 (épreuve E4)

    Choix : une confirmation explicite par saisie de l'adresse électronique,
    plutôt qu'une simple case à cocher. Motivation : l'effacement est
    irréversible et emporte les cours, exercices, soumissions et progression.
    Une case se coche par inadvertance ; recopier son adresse suppose de lire.

    Choix : la vue ne déclare jamais le succès de son propre chef. Elle appelle
    `supprimer_compte`, qui relit la base et le disque, et n'affiche un message
    de confirmation que si le rapport porte `conforme`. Un effacement partiel
    annoncé comme complet serait pire qu'un effacement absent : il donnerait
    l'illusion d'être conforme.
    """

    template_name = 'users/supprimer_compte.html'

    def get(self, request):
        return render(request, self.template_name, {
            'effets': self._effets_annonces(request.user),
        })

    def post(self, request):
        confirmation = (request.POST.get('confirmation') or '').strip().lower()
        if confirmation != (request.user.email or '').strip().lower():
            messages.error(
                request,
                _("La confirmation ne correspond pas à votre adresse "
                  "électronique. Le compte n'a pas été supprimé."),
            )
            return render(request, self.template_name, {
                'effets': self._effets_annonces(request.user),
            })

        utilisateur = request.user
        identifiant = utilisateur.pk
        logout(request)
        rapport = supprimer_compte(utilisateur)

        if rapport.conforme:
            messages.success(
                request,
                _("Votre compte et les données qui s'y rattachaient ont été "
                  "supprimés."),
            )
        else:
            # On ne ment pas à l'utilisateur sur l'étendue de l'effacement.
            logger_users.error(
                "effacement incomplet du compte %s : %s / %s",
                identifiant, rapport.subsiste, rapport.fichiers_subsistants,
            )
            messages.warning(
                request,
                _("Votre compte a été supprimé, mais certaines données n'ont "
                  "pas pu être effacées. L'incident est enregistré et sera "
                  "traité ; vous pouvez nous contacter pour en suivre le "
                  "traitement."),
            )
        return redirect('/')

    @staticmethod
    def _effets_annonces(utilisateur) -> dict:
        """
        Ce que l'utilisateur perdra, compté avant qu'il ne confirme.

        Compétence visée : C4 (épreuve E1)

        L'article 12.1 impose une information claire. Annoncer « votre compte
        sera supprimé » sans dire que les cours et les soumissions le seront
        aussi ne satisfait pas cette exigence.
        """
        return inventorier(utilisateur.pk)
