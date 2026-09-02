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
        messages.success(request, _('You have been logged out successfully.'))
        return response
    

#: Avatar servi quand l'apprenant n'a rien choisi.
AVATAR_PAR_DEFAUT = "koda_base.png"

#: Extensions retenues pour la liste des avatars Koda.
EXTENSIONS_D_AVATAR = (".png", ".jpg", ".jpeg")


def url_d_avatar_koda(nom_de_fichier):
    """
    Rend l'URL statique d'un avatar Koda.

    Compétence visée : C17 (épreuve E4)

    Choix : une URL statique, et non une URL de `media/`. Motivation : les
    avatars Koda sont livrés dans l'image, versionnés avec le reste. Les
    médias, eux, ne sont ni versionnés ni persistants chez l'hébergeur.
    """
    return f"/static/koda/{nom_de_fichier}"


def avatars_koda_disponibles():
    """
    Liste les avatars Koda proposés au choix, lus dans le dossier source.

    Compétence visée : C17 (épreuve E4)

    Choix : lire `static/koda`, et jamais `STATIC_ROOT`. Motivation mesurée :
    après `collectstatic`, `STATIC_ROOT` porte chaque avatar DEUX fois —
    l'original et sa copie empreintée, soit 40 entrées pour 20 avatars. La
    liste affichait donc des doublons, et la moitié des noms proposés
    n'existait pas dans le dossier que l'enregistrement va lire : les choisir
    provoquait une erreur 500.

    La règle est celle que le projet applique déjà à l'import des cours : ce
    qu'on propose et ce qu'on sait ouvrir doivent venir de la même source.
    """
    racine = os.path.join(settings.BASE_DIR, "static", "koda")
    avatars = []
    if os.path.isdir(racine):
        for nom_de_fichier in os.listdir(racine):
            if not nom_de_fichier.lower().endswith(EXTENSIONS_D_AVATAR):
                continue
            libelle = (nom_de_fichier.rsplit(".", 1)[0]
                       .replace("koda_", "").replace("_", " ").title())
            avatars.append({
                "filename": nom_de_fichier,
                "display_name": libelle,
                "url": url_d_avatar_koda(nom_de_fichier),
            })
    avatars.sort(key=lambda avatar: avatar["display_name"])
    return avatars


class ProfileView(LoginRequiredMixin, UpdateView):
    """
    Vue de modification du profil utilisateur.
    """
    model = KodaUser
    fields = ['username', 'email', 'bio', 'language_preference', 'animation_koda', 'avatar']
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_avatars'] = avatars_koda_disponibles()

        # L'avatar envoyé par l'apprenant l'emporte sur l'avatar Koda ; à
        # défaut, on affiche le Koda choisi. Le test portait auparavant sur
        # `hasattr(avatar, 'name')`, vrai pour tout ImageField même vide : la
        # branche Koda n'était donc jamais atteinte, et aucune vignette
        # n'apparaissait jamais comme sélectionnée.
        televerse = self.request.user.avatar
        if televerse:
            context['current_avatar_url'] = televerse.url
            context['current_avatar_type'] = 'uploaded'
        else:
            nom = self.request.user.koda_avatar or AVATAR_PAR_DEFAUT
            context['current_avatar_url'] = url_d_avatar_koda(nom)
            context['current_avatar_type'] = 'koda'
            context['current_avatar_name'] = nom

        return context

    def form_valid(self, form):
        selected_koda_avatar = self.request.POST.get('selected_koda_avatar')
        cropped_avatar = self.request.POST.get('cropped_avatar')

        if selected_koda_avatar:
            # Le nom est refusé s'il ne figure pas dans la liste proposée.
            # Motivation : il arrive de la requête, donc de l'extérieur. Sans
            # ce contrôle, un nom inattendu remontait en erreur 500 — c'est
            # exactement ce qui se produisait avec les noms empreintés par
            # `collectstatic`, que l'ancienne liste proposait alors que le
            # dossier source ne les porte pas.
            connus = {avatar['filename'] for avatar in avatars_koda_disponibles()}
            if selected_koda_avatar not in connus:
                messages.error(
                    self.request,
                    _("Cet avatar n'existe pas. Choisissez-en un dans la liste."),
                )
                return self.form_invalid(form)

            # L'avatar Koda est écrit comme un NOM DE FICHIER, servi depuis
            # les fichiers statiques, et non recopié dans `media/`. Motivation
            # mesurée : l'ancienne version recopiait le PNG dans `media/`, dont
            # rien ne sert le contenu quand DEBUG vaut False. L'avatar était
            # bien enregistré et n'apparaissait jamais. Il est déjà livré dans
            # l'image comme fichier statique : le copier ailleurs n'ajoutait
            # qu'un chemin de plus par lequel se perdre.
            if form.instance.avatar:
                form.instance.avatar.delete(save=False)
            form.instance.avatar = None
            form.instance.koda_avatar = selected_koda_avatar

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
