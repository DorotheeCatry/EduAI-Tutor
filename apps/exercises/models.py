from django.db import models
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class Exercise(models.Model):
    """Model for Python code exercises"""
    
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    topic = models.CharField(max_length=100)  # Ex: "functions", "loops", "classes"
    
    # Starting code provided to user
    starter_code = models.TextField(default="# Your code here\n")
    
    # Reference solution (for trainers)
    solution = models.TextField()
    
    # Tests to execute (JSON format)
    tests = models.JSONField(default=list)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Statistics
    attempts_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Exercise"
        verbose_name_plural = "Exercises"
    
    def __str__(self):
        return f"{self.title} ({self.get_difficulty_display()})"
    
    @property
    def success_rate(self):
        """Calculate exercise success rate"""
        if self.attempts_count == 0:
            return 0
        return round((self.success_count / self.attempts_count) * 100, 1)

class ExerciseSubmission(models.Model):
    """Model for exercise submissions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ]
    
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Code submitted by user
    submitted_code = models.TextField()
    
    # Execution results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    execution_output = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    execution_time = models.FloatField(null=True, blank=True)  # in seconds
    
    # Test results (JSON format)
    test_results = models.JSONField(default=list)
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
    
    def __str__(self):
        return f"{self.user.username} - {self.exercise.title} ({self.status})"
    
    @property
    def is_successful(self):
        """Check if submission is successful"""
        return self.status == 'success'
    
    @property
    def passed_tests_count(self):
        """Number of passed tests"""
        return sum(1 for result in self.test_results if result.get('passed', False))
    
    @property
    def total_tests_count(self):
        """Total number of tests"""
        return len(self.test_results)

class UserExerciseProgress(models.Model):
    """Model to track user progress on exercises"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    
    # Progress
    is_completed = models.BooleanField(default=False)
    best_submission = models.ForeignKey(
        ExerciseSubmission, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='best_for_progress'
    )
    
    # Statistics
    attempts_count = models.PositiveIntegerField(default=0)
    first_attempt_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'exercise']
        verbose_name = "Exercise progress"
        verbose_name_plural = "Exercise progress"
    
    def __str__(self):
        status = "✅" if self.is_completed else "⏳"
        return f"{status} {self.user.username} - {self.exercise.title}"