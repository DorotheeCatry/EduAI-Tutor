from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Course(models.Model):
    """Modèle pour sauvegarder les cours générés"""
    
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=200)
    module = models.CharField(max_length=100, default='general')
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    
    # Métadonnées
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_favorite = models.BooleanField(default=False)
    
    # Statistiques
    view_count = models.PositiveIntegerField(default=0)
    completion_rate = models.FloatField(default=0.0)  # Pourcentage de lecture
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
    
    def __str__(self):
        return f"{self.title}"
    
    def increment_view_count(self):
        """Incrémente le compteur de vues"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

class CourseSection(models.Model):
    """Sections d'un cours pour un meilleur tracking"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField()
    section_type = models.CharField(max_length=50, choices=[
        ('introduction', 'Introduction'),
        ('explanation', 'Explication'),
        ('examples', 'Exemples'),
        ('summary', 'Résumé'),
        ('advanced', 'Approfondissement'),
    ])
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']