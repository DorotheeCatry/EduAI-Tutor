from django.db import models
from django.contrib.auth import get_user_model
import string
import random

User = get_user_model()

class GameRoom(models.Model):
    """Salle de jeu multijoueur"""
    
    STATUS_CHOICES = [
        ('waiting', 'En attente'),
        ('starting', 'Démarrage'),
        ('in_progress', 'En cours'),
        ('finished', 'Terminé'),
    ]
    
    code = models.CharField(max_length=10, unique=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_rooms')
    topic = models.CharField(max_length=200)
    num_questions = models.IntegerField(default=10)
    max_players = models.IntegerField(default=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_question = models.IntegerField(default=0)
    question_start_time = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Room {self.code} - {self.topic}"
    
    @classmethod
    def generate_code(cls):
        """Génère un code unique pour la salle"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not cls.objects.filter(code=code).exists():
                return code
    
    @property
    def player_count(self):
        return self.participants.filter(is_active=True).count()
    
    @property
    def is_full(self):
        return self.player_count >= self.max_players

class GameParticipant(models.Model):
    """Participant dans une salle de jeu"""
    
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['room', 'user']
        ordering = ['-score', 'joined_at']
    
    def __str__(self):
        return f"{self.user.username} in {self.room.code}"

class GameQuestion(models.Model):
    """Question d'une partie"""
    
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='questions')
    question_number = models.IntegerField()
    question_text = models.TextField()
    options = models.JSONField()  # Liste des 4 options
    correct_answer = models.IntegerField()  # Index de la bonne réponse (0-3)
    explanation = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['room', 'question_number']
        ordering = ['question_number']
    
    def __str__(self):
        return f"Q{self.question_number} - {self.room.code}"

class GameAnswer(models.Model):
    """Réponse d'un joueur à une question"""
    
    participant = models.ForeignKey(GameParticipant, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name='answers')
    selected_answer = models.IntegerField()  # Index de la réponse choisie (0-3)
    response_time = models.FloatField()  # Temps de réponse en secondes
    points_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['participant', 'question']
    
    @property
    def is_correct(self):
        return self.selected_answer == self.question.correct_answer
    
    def calculate_points(self):
        """Calcule les points basés sur justesse et rapidité"""
        if not self.is_correct:
            return 0
        
        # Points de base pour une bonne réponse
        base_points = 1000
        
        # Bonus de rapidité (max 500 points)
        # Plus on répond vite, plus on gagne de points
        max_time = 60  # 60 secondes max
        time_bonus = max(0, int((max_time - self.response_time) / max_time * 500))
        
        total_points = base_points + time_bonus
        self.points_earned = total_points
        return total_points
    
    def __str__(self):
        return f"{self.participant.user.username} - Q{self.question.question_number}"
