from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', _('Student')
        TEACHER = 'teacher', _('Teacher')
        ADMIN = 'admin', _('Administrator')

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT
    )

    bio = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Biography"),
        help_text=_("A short biography of the user.")
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    