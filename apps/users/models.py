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
        default="koda_base.png",
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
    
    # Nouveaux champs pour le système de niveaux
    total_courses_completed = models.PositiveIntegerField(default=0)
    total_quizzes_completed = models.PositiveIntegerField(default=0)
    total_study_time_minutes = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    @property
    def level(self):
        """Calcule le niveau basé sur l'XP avec une progression exponentielle"""
        if self.xp < 100:
            return 1
        elif self.xp < 300:
            return 2
        elif self.xp < 600:
            return 3
        elif self.xp < 1000:
            return 4
        elif self.xp < 1500:
            return 5
        elif self.xp < 2100:
            return 6
        elif self.xp < 2800:
            return 7
        elif self.xp < 3600:
            return 8
        elif self.xp < 4500:
            return 9
        else:
            return min(10 + (self.xp - 4500) // 1000, 50)  # Max niveau 50
    
    @property
    def xp_for_next_level(self):
        """XP nécessaire pour le prochain niveau"""
        current_level = self.level
        if current_level == 1:
            return 100
        elif current_level == 2:
            return 300
        elif current_level == 3:
            return 600
        elif current_level == 4:
            return 1000
        elif current_level == 5:
            return 1500
        elif current_level == 6:
            return 2100
        elif current_level == 7:
            return 2800
        elif current_level == 8:
            return 3600
        elif current_level == 9:
            return 4500
        else:
            return (current_level - 9) * 1000 + 4500
    
    @property
    def xp_progress_percentage(self):
        """Pourcentage de progression vers le prochain niveau"""
        current_level_xp = self.xp_for_current_level
        next_level_xp = self.xp_for_next_level
        
        # Éviter la division par zéro
        if next_level_xp <= current_level_xp:
            return 100.0
        
        # Calculer le pourcentage de progression dans le niveau actuel
        progress = ((self.xp - current_level_xp) / (next_level_xp - current_level_xp)) * 100
        return min(100, max(0, progress))
    
    @property
    def xp_in_current_level(self):
        """XP gagnés dans le niveau actuel"""
        return self.xp - self.xp_for_current_level
    
    @property
    def xp_needed_for_next_level(self):
        """XP nécessaires pour passer au niveau suivant"""
        return self.xp_for_next_level - self.xp_for_current_level
    
    @property
    def xp_for_current_level(self):
        """XP requis pour le niveau actuel"""
        current_level = self.level
        if current_level == 1:
            return 0
        elif current_level == 2:
            return 100
        elif current_level == 3:
            return 300
        elif current_level == 4:
            return 600
        elif current_level == 5:
            return 1000
        elif current_level == 6:
            return 1500
        elif current_level == 7:
            return 2100
        elif current_level == 8:
            return 2800
        elif current_level == 9:
            return 3600
        else:
            return (current_level - 10) * 1000 + 4500
    
    @property
    def level_title(self):
        """Title based on level"""
        level = self.level
        if level == 1:
            return "Beginner"
        elif level <= 3:
            return "Apprentice"
        elif level <= 5:
            return "Student"
        elif level <= 8:
            return "Developer"
        elif level <= 12:
            return "Expert"
        elif level <= 20:
            return "Master"
        elif level <= 30:
            return "Sage"
        else:
            return "Legend"
    
    def add_xp(self, amount, activity_type="general"):
        """Add XP and update statistics"""
        from datetime import date
        
        old_level = self.level
        self.xp += amount
        new_level = self.level
        
        # Update last activity date and streak
        today = date.today()
        if self.last_activity_date:
            if self.last_activity_date == today:
                pass  # Same day, no streak change
            elif (today - self.last_activity_date).days == 1:
                self.current_streak += 1  # Consecutive day
            else:
                self.current_streak = 1  # Reset streak
        else:
            self.current_streak = 1
        
        self.last_activity_date = today
        self.save()
        
        # Return level up information
        return {
            'xp_gained': amount,
            'total_xp': self.xp,
            'old_level': old_level,
            'new_level': new_level,
            'level_up': new_level > old_level,
            'activity_type': activity_type
        }

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
