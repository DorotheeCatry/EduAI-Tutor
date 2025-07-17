from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django import forms
from django.conf import settings
import os
from .models import KodaUser

class RegisterForm(UserCreationForm):
    """
    Form for user registration.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors',
            'placeholder': 'votre@email.com'
        })
    )
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors',
            'placeholder': 'Nom d\'utilisateur'
        })
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors',
            'placeholder': '••••••••'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors',
            'placeholder': 'Confirmer le mot de passe'
        })
    )
    
    avatar = forms.CharField(
        required=False,
        initial='koda_base.png',
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = KodaUser
        fields = ("email", "username", "password1", "password2", "avatar")
        labels = {
            "email": _("Email"),
            "username": _("Username"),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Charger les avatars disponibles
        self.available_avatars = self.get_available_avatars()
    
    def get_available_avatars(self):
        """Récupère la liste des avatars Koda disponibles"""
        koda_path = os.path.join(settings.BASE_DIR, 'static', 'koda')
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
        return available_avatars
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Définir l'avatar sélectionné
        avatar = self.cleaned_data.get('avatar') or 'koda_base.png'
        user.avatar = avatar
        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    """
    Form for user login with email or username.
    """
    username = forms.CharField(
        label=_("Email or username"),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue transition-colors',
            'placeholder': 'your@email.com or username'
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue transition-colors',
            'placeholder': '••••••••'
        })
    )