from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class KodaUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', _('Student')
        ADMIN = 'admin', _('Administrator')

    # Les champs username et email sont déjà inclus dans AbstractUser
    # On peut les personnaliser si nécessaire
    email = models.EmailField(
        _('Email address'),
        unique=True,
        help_text=_('Required. Enter a valid email address.')
    )
    
    # Permettre la connexion par email ou username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name=_("Role")
    )

    bio = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Biography"),
        help_text=_("A short biography of the user.")
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        default="koda_base.png",
        verbose_name=_("Avatar")
    )

    koda_avatar = models.CharField(
        max_length=100, 
        blank=True, 
        null=True)    # nom du fichier koda


    LANGUAGE_CHOICES = [
        ("en", _("English")),
        ("fr", _("French")),
    ]

    language_preference = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default="fr",
        verbose_name=_("Preferred language")
    )

    xp = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Experience Points"),
        help_text=_("Total experience points gained by the student.")
    )

    @property
    def level(self):
        return self.xp // 100 + 1  # Exemple : 100 XP = 1 niveau

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
