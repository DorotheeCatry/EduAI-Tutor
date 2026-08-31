# apps/agents/agent_watcher.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict
import json

User = get_user_model()

class LearningSession(models.Model):
    """Model for tracking learning sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=50)  # 'course', 'quiz', 'chat', 'revision'
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    score = models.FloatField(null=True, blank=True)  # For quizzes
    metadata = models.JSONField(default=dict)  # Additional data

    # Compétence visée, si l'apprenant en a choisi une.
    #
    # Compétence visée : C17 (épreuve E4)
    #
    # Même mécanique que pour les exercices (décision 027) : un choix
    # explicite, jamais une déduction sur le sujet libre. Un quiz ne fait
    # PAS progresser un niveau — faire attester une production par une
    # reconnaissance n'aurait pas de sens (décision 028) — mais il alimente le
    # bloc « à revoir », qui doit parler la même langue que le reste de la
    # page : une compétence, et non un sujet libre.
    competence = models.ForeignKey(
        "referentiel.Competence", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sessions",
        verbose_name="Compétence visée",
    )

    class Meta:
        app_label = 'agents'

class UserMistake(models.Model):
    """Model for tracking user mistakes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    mistake_type = models.CharField(max_length=100)
    question = models.TextField()
    user_answer = models.TextField()
    correct_answer = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    # La compétence, reprise de la session du quiz.
    #
    # Compétence visée : C17 (épreuve E4)
    #
    # `topic` reste renseigné : c'est le sujet du quiz, utile quand aucune
    # compétence n'a été choisie. Les deux coexistent parce qu'ils ne disent
    # pas la même chose — l'un est ce que l'apprenant a demandé, l'autre ce
    # que le référentiel en retient.
    competence = models.ForeignKey(
        "referentiel.Competence", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="erreurs",
        verbose_name="Compétence visée",
    )

    class Meta:
        app_label = 'agents'

class WatcherAgent:
    """Watcher Agent for analyzing performance and detecting gaps"""
    
    def __init__(self, user):
        self.user = user
    
    def track_session(self, topic, activity_type, metadata=None, competence=None):
        """
        Ouvre une session d'apprentissage.

        Compétence visée : C20 (épreuve E5)
        """
        session = LearningSession.objects.create(
            user=self.user,
            topic=topic,
            activity_type=activity_type,
            metadata=metadata or {},
            competence=competence,
        )
        return session
    
    def end_session(self, session_id, score=None):
        """
        Clôt une session et calcule sa durée.

        Compétence visée : C20 (épreuve E5) — données du suivi
        Compétence concernée : C21 (E5)

        Choix : `timezone.now()` et non `datetime.now()`. Motivation : le
        projet a `USE_TZ = True`, donc `start_time` porte un fuseau. Les
        soustraire produisait `TypeError: can't subtract offset-naive and
        offset-aware datetimes` — cette méthode n'a jamais pu aboutir depuis
        qu'elle existe. Personne ne s'en était aperçu parce que rien ne
        l'appelait : le gabarit du quiz ne soumettait pas ses résultats
        (incident 010). Un défaut dans du code mort ne se voit pas, il attend.
        """
        try:
            session = LearningSession.objects.get(id=session_id, user=self.user)
            session.end_time = timezone.now()
            session.duration_seconds = int((session.end_time - session.start_time).total_seconds())
            if score is not None:
                session.score = score
            session.save()
            return session
        except LearningSession.DoesNotExist:
            return None
    
    def record_mistake(self, topic, mistake_type, question, user_answer,
                       correct_answer, competence=None):
        """
        Enregistre une erreur d'apprenant.

        Compétence visée : C20 (épreuve E5) — données du suivi
        Compétence concernée : C17 (E4)

        `topic` porte le sujet du quiz, `competence` le rattachement au
        référentiel quand l'apprenant en a choisi un. Les deux sont conservés :
        le premier dit ce qui a été demandé, le second ce que le référentiel en
        retient. Sans le second, le bloc « à revoir » parlerait en sujets
        libres pendant que le reste de la page parle en compétences.
        """
        mistake = UserMistake.objects.create(
            user=self.user,
            topic=topic,
            mistake_type=mistake_type,
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
            competence=competence,
        )
        return mistake
    
    def get_user_stats(self):
        """Returns user statistics"""
        sessions = LearningSession.objects.filter(user=self.user)
        
        total_time = sum(s.duration_seconds for s in sessions if s.duration_seconds)
        total_sessions = sessions.count()
        
        # Calculate average score for quizzes
        quiz_sessions = sessions.filter(activity_type='quiz', score__isnull=False)
        avg_score = quiz_sessions.aggregate(models.Avg('score'))['score__avg'] or 0
        
        # Sessions by topic
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
        """Calculates user level based on XP"""
        return self.user.level
    
    def get_weak_topics(self, limit=5):
        """Identifies topics where user has the most errors"""
        mistakes = UserMistake.objects.filter(user=self.user, reviewed=False)
        
        topic_mistakes = defaultdict(int)
        for mistake in mistakes:
            topic_mistakes[mistake.topic] += 1
        
        # Sort by decreasing error count
        weak_topics = sorted(topic_mistakes.items(), key=lambda x: x[1], reverse=True)
        return weak_topics[:limit]
    
    def get_revision_recommendations(self):
        """Generates revision recommendations based on errors"""
        weak_topics = self.get_weak_topics()
        
        recommendations = []
        for topic, mistake_count in weak_topics:
            # Get specific errors for this topic
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
        """Marks topic errors as reviewed"""
        UserMistake.objects.filter(
            user=self.user,
            topic=topic,
            reviewed=False
        ).update(reviewed=True)

def get_watcher_agent(user):
    """Factory function to create a watcher agent"""
    return WatcherAgent(user)
