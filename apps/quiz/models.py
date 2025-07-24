from django.db import models
from django.contrib.auth import get_user_model
import string
import random

User = get_user_model()

class GameRoom(models.Model):
    """Multiplayer game room"""
    
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('starting', 'Starting'),
        ('in_progress', 'In Progress'),
        ('finished', 'Finished'),
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
        """Generates unique code for room"""
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
    """Participant in a game room"""
    
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
    """Question in a game"""
    
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='questions')
    question_number = models.IntegerField()
    question_text = models.TextField()
    options = models.JSONField()  # Liste des 4 options
    correct_answer = models.IntegerField()  # Index of correct answer (0-3)
    explanation = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['room', 'question_number']
        ordering = ['question_number']
    
    def __str__(self):
        return f"Q{self.question_number} - {self.room.code}"

class GameAnswer(models.Model):
    """Player's answer to a question"""
    
    participant = models.ForeignKey(GameParticipant, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name='answers')
    selected_answer = models.IntegerField()  # Index of chosen answer (0-3)
    response_time = models.FloatField()  # Response time in seconds
    points_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['participant', 'question']
    
    @property
    def is_correct(self):
        return self.selected_answer == self.question.correct_answer
    
    def calculate_points(self):
        """Calculates points based on accuracy and speed"""
        if not self.is_correct:
            return 0
        
        # Base points for correct answer
        base_points = 1000
        
        # Speed bonus (max 500 points)
        # Faster response = more points
        max_time = 60  # 60 seconds max
        time_bonus = max(0, int((max_time - self.response_time) / max_time * 500))
        
        total_points = base_points + time_bonus
        self.points_earned = total_points
        return total_points
    
    def __str__(self):
        return f"{self.participant.user.username} - Q{self.question.question_number}"
