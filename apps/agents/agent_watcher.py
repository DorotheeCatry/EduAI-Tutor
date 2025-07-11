# apps/agents/agent_watcher.py

from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from collections import defaultdict
import json

User = get_user_model()

class LearningSession(models.Model):
    """Modèle pour tracker les sessions d'apprentissage"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=50)  # 'course', 'quiz', 'chat', 'revision'
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    score = models.FloatField(null=True, blank=True)  # Pour les quiz
    metadata = models.JSONField(default=dict)  # Données supplémentaires
    
    class Meta:
        app_label = 'agents'

class UserMistake(models.Model):
    """Modèle pour tracker les erreurs des utilisateurs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    mistake_type = models.CharField(max_length=100)
    question = models.TextField()
    user_answer = models.TextField()
    correct_answer = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'agents'

class WatcherAgent:
    """Agent Surveillant pour analyser les performances et détecter les lacunes"""
    
    def __init__(self, user):
        self.user = user
    
    def track_session(self, topic, activity_type, metadata=None):
        """Démarre le tracking d'une session"""
        session = LearningSession.objects.create(
            user=self.user,
            topic=topic,
            activity_type=activity_type,
            metadata=metadata or {}
        )
        return session
    
    def end_session(self, session_id, score=None):
        """Termine une session et calcule la durée"""
        try:
            session = LearningSession.objects.get(id=session_id, user=self.user)
            session.end_time = datetime.now()
            session.duration_seconds = int((session.end_time - session.start_time).total_seconds())
            if score is not None:
                session.score = score
            session.save()
            return session
        except LearningSession.DoesNotExist:
            return None
    
    def record_mistake(self, topic, mistake_type, question, user_answer, correct_answer):
        """Enregistre une erreur de l'utilisateur"""
        mistake = UserMistake.objects.create(
            user=self.user,
            topic=topic,
            mistake_type=mistake_type,
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer
        )
        return mistake
    
    def get_user_stats(self):
        """Retourne les statistiques de l'utilisateur"""
        sessions = LearningSession.objects.filter(user=self.user)
        
        total_time = sum(s.duration_seconds for s in sessions if s.duration_seconds)
        total_sessions = sessions.count()
        
        # Calcul du score moyen pour les quiz
        quiz_sessions = sessions.filter(activity_type='quiz', score__isnull=False)
        avg_score = quiz_sessions.aggregate(models.Avg('score'))['score__avg'] or 0
        
        # Sessions par sujet
        topics_stats = defaultdict(lambda: {'sessions': 0, 'time': 0, 'avg_score': 0})
        for session in sessions:
            topics_stats[session.topic]['sessions'] += 1
            topics_stats[session.topic]['time'] += session.duration_seconds or 0
            if session.score:
                topics_stats[session.topic]['avg_score'] = session.score
        
        return {
            'total_time_seconds': total_time,
            'total_sessions': total_sessions,
            'average_score': round(avg_score, 1),
            'topics': dict(topics_stats),
            'level': self.calculate_level()
        }
    
    def calculate_level(self):
        """Calcule le niveau de l'utilisateur basé sur son XP"""
        return self.user.level
    
    def get_weak_topics(self, limit=5):
        """Identifie les sujets où l'utilisateur a le plus d'erreurs"""
        mistakes = UserMistake.objects.filter(user=self.user, reviewed=False)
        
        topic_mistakes = defaultdict(int)
        for mistake in mistakes:
            topic_mistakes[mistake.topic] += 1
        
        # Trier par nombre d'erreurs décroissant
        weak_topics = sorted(topic_mistakes.items(), key=lambda x: x[1], reverse=True)
        return weak_topics[:limit]
    
    def get_revision_recommendations(self):
        """Génère des recommandations de révision basées sur les erreurs"""
        weak_topics = self.get_weak_topics()
        
        recommendations = []
        for topic, mistake_count in weak_topics:
            # Récupérer les erreurs spécifiques pour ce sujet
            recent_mistakes = UserMistake.objects.filter(
                user=self.user,
                topic=topic,
                reviewed=False
            ).order_by('-timestamp')[:3]
            
            recommendations.append({
                'topic': topic,
                'mistake_count': mistake_count,
                'priority': 'high' if mistake_count >= 3 else 'medium',
                'recent_mistakes': [
                    {
                        'question': m.question,
                        'user_answer': m.user_answer,
                        'correct_answer': m.correct_answer
                    } for m in recent_mistakes
                ]
            })
        
        return recommendations
    
    def mark_mistakes_reviewed(self, topic):
        """Marque les erreurs d'un sujet comme révisées"""
        UserMistake.objects.filter(
            user=self.user,
            topic=topic,
            reviewed=False
        ).update(reviewed=True)

def get_watcher_agent(user):
    """Factory function pour créer un agent surveillant"""
    return WatcherAgent(user)