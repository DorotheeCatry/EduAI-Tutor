from django.db import models
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class Exercise(models.Model):
    """Modèle pour les exercices de code Python"""
    
    DIFFICULTY_CHOICES = [
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    topic = models.CharField(max_length=100)  # Ex: "functions", "loops", "classes"
    
    # Code de départ fourni à l'utilisateur
    starter_code = models.TextField(default="# Votre code ici\n")
    
    # Solution de référence (pour les formateurs)
    solution = models.TextField()
    
    # Tests à exécuter (format JSON)
    tests = models.JSONField(default=list)
    
    # Métadonnées
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Statistiques
    attempts_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Exercice"
        verbose_name_plural = "Exercices"
    
    def __str__(self):
        return f"{self.title} ({self.get_difficulty_display()})"
    
    @property
    def success_rate(self):
        """Calcule le taux de réussite de l'exercice"""
        if self.attempts_count == 0:
            return 0
        return round((self.success_count / self.attempts_count) * 100, 1)

class ExerciseSubmission(models.Model):
    """Modèle pour les soumissions d'exercices"""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('success', 'Réussi'),
        ('failed', 'Échoué'),
        ('error', 'Erreur'),
        ('timeout', 'Timeout'),
    ]
    
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Code soumis par l'utilisateur
    submitted_code = models.TextField()
    
    # Résultats de l'exécution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    execution_output = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    execution_time = models.FloatField(null=True, blank=True)  # en secondes
    
    # Résultats des tests (format JSON)
    test_results = models.JSONField(default=list)
    
    # Métadonnées
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Soumission"
        verbose_name_plural = "Soumissions"
    
    def __str__(self):
        return f"{self.user.username} - {self.exercise.title} ({self.status})"
    
    @property
    def is_successful(self):
        """Vérifie si la soumission est réussie"""
        return self.status == 'success'
    
    @property
    def passed_tests_count(self):
        """Nombre de tests réussis"""
        return sum(1 for result in self.test_results if result.get('passed', False))
    
    @property
    def total_tests_count(self):
        """Nombre total de tests"""
        return len(self.test_results)

class UserExerciseProgress(models.Model):
    """Modèle pour suivre la progression des utilisateurs sur les exercices"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    
    # Progression
    is_completed = models.BooleanField(default=False)
    best_submission = models.ForeignKey(
        ExerciseSubmission, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='best_for_progress'
    )
    
    # Statistiques
    attempts_count = models.PositiveIntegerField(default=0)
    first_attempt_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'exercise']
        verbose_name = "Progression exercice"
        verbose_name_plural = "Progressions exercices"
    
    def __str__(self):
        status = "✅" if self.is_completed else "⏳"
        return f"{status} {self.user.username} - {self.exercise.title}"