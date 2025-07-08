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
            'class': 'input-field',
            'placeholder': 'votre@email.com'
        })
    )
    
    class Meta:
        model = KodaUser
        fields = ("email", "username", "password1", "password2", "role")
        labels = {
            "email": _("Email"),
            "username": _("Username"),
            'role': _("Role")
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Nom d\'utilisateur'
            }),
        }

class LoginForm(AuthenticationForm):
    """
    Form for user login with email or username.
    """
    username = forms.CharField(
        label=_("Email ou nom d'utilisateur"),
        widget=forms.TextInput(attrs={
            'class': 'input-field',
            'placeholder': 'votre@email.com ou nom d\'utilisateur'
        })
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '••••••••'
        })
    )