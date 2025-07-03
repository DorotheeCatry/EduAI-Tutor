from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class RegisterForm(UserCreationForm):
    """
    Form for user registration.
    """
    class Meta:
        model = CustomUser
        fields = ("username", "email", "password1", "password2", "role")
        labels = {
            "username": _("Username"),
            "email": _("Email"),
            'role': _("Role")}