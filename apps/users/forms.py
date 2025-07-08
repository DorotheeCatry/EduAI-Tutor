from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django import forms
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
    
    class Meta:
        model = KodaUser
        fields = ("email", "username", "password1", "password2")
        labels = {
            "email": _("Email"),
            "username": _("Username"),
        }

class LoginForm(AuthenticationForm):
    """
    Form for user login with email or username.
    """
    username = forms.CharField(
        label=_("Email ou nom d'utilisateur"),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue transition-colors',
            'placeholder': 'votre@email.com ou nom d\'utilisateur'
        })
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue transition-colors',
            'placeholder': '••••••••'
        })
    )