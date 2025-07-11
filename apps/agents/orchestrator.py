# apps/agents/orchestrator.py

from .agent_researcher import get_researcher_chain
from .agent_pedagogue import get_pedagogue_chain
from .agent_coach import generate_quiz, generate_code_exercise
from .agent_watcher import get_watcher_agent
from django.contrib.auth import get_user_model

User = get_user_model()

class AIOrchestrator:
    """
    Orchestrateur principal qui coordonne tous les agents IA
    """
    
    def __init__(self, user=None):
        self.user = user
        self.researcher = get_researcher_chain()
        self.pedagogue = get_pedagogue_chain()
        if user:
            self.watcher = get_watcher_agent(user)
    
    def generate_course(self, topic, difficulty="intermediate"):
        """
        Génère un cours complet en utilisant Chercheur + Pédagogue
        """
        try:
            # 1. Recherche de ressources pertinentes
            research_result = self.researcher.invoke(topic)
            
            # 2. Génération du cours structuré
            course_result = self.pedagogue.invoke({"query": topic})
            
            # 3. Tracking de la session si utilisateur connecté
            session = None
            if self.user:
                session = self.watcher.track_session(
                    topic=topic,
                    activity_type='course_generation',
                    metadata={'difficulty': difficulty}
                )
            
            return {
                'success': True,
                'topic': topic,
                'difficulty': difficulty,
                'content': course_result['result'],
                'sources': [doc.metadata.get('source', 'Unknown') for doc in course_result.get('source_documents', [])],
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Erreur lors de la génération du cours : {e}")
            return {
                'success': False,
                'error': str(e),
                'topic': topic
            }
    
    def answer_question(self, question):
        """
        Répond à une question en utilisant le système RAG
        """
        try:
            # Utiliser le chercheur pour trouver et synthétiser la réponse
            result = self.researcher.invoke(question)
            
            # Tracking de la session si utilisateur connecté
            session = None
            if self.user:
                session = self.watcher.track_session(
                    topic=question[:100],  # Limiter la longueur
                    activity_type='chat',
                    metadata={'question': question}
                )
            
            return {
                'success': True,
                'question': question,
                'answer': result['result'],
                'sources': [doc.metadata.get('source', 'Unknown') for doc in result.get('source_documents', [])],
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Erreur lors de la réponse à la question : {e}")
            return {
                'success': False,
                'error': str(e),
                'question': question
            }
    
    def create_quiz(self, topic, difficulty="intermediate", num_questions=5):
        """
        Crée un quiz sur un sujet donné
        """
        try:
            quiz_data = generate_quiz(topic, difficulty, num_questions)
            
            # Tracking de la session si utilisateur connecté
            session = None
            if self.user:
                session = self.watcher.track_session(
                    topic=topic,
                    activity_type='quiz',
                    metadata={
                        'difficulty': difficulty,
                        'num_questions': num_questions
                    }
                )
            
            return {
                'success': True,
                'topic': topic,
                'difficulty': difficulty,
                'quiz': quiz_data,
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Erreur lors de la création du quiz : {e}")
            return {
                'success': False,
                'error': str(e),
                'topic': topic
            }
    
    def submit_quiz_results(self, session_id, answers, quiz_data):
        """
        Traite les résultats d'un quiz et met à jour les statistiques
        """
        if not self.user or not session_id:
            return {'success': False, 'error': 'User or session not found'}
        
        try:
            # Calculer le score
            correct_answers = 0
            total_questions = len(quiz_data['questions'])
            
            for i, user_answer in enumerate(answers):
                question = quiz_data['questions'][i]
                correct_answer = question['correct_answer']
                
                if user_answer == correct_answer:
                    correct_answers += 1
                else:
                    # Enregistrer l'erreur
                    self.watcher.record_mistake(
                        topic=session_id,  # Utiliser session_id comme topic temporaire
                        mistake_type='quiz_wrong_answer',
                        question=question['question'],
                        user_answer=question['options'][user_answer] if user_answer < len(question['options']) else 'No answer',
                        correct_answer=question['options'][correct_answer]
                    )
            
            score = (correct_answers / total_questions) * 100
            
            # Terminer la session
            session = self.watcher.end_session(session_id, score)
            
            # Mettre à jour l'XP de l'utilisateur
            xp_gained = int(score / 10)  # 1 XP par 10% de score
            self.user.xp += xp_gained
            self.user.save()
            
            return {
                'success': True,
                'score': score,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'xp_gained': xp_gained,
                'session': session
            }
            
        except Exception as e:
            print(f"Erreur lors du traitement des résultats : {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_dashboard(self):
        """
        Génère les données du tableau de bord utilisateur
        """
        if not self.user:
            return {'success': False, 'error': 'User not authenticated'}
        
        try:
            stats = self.watcher.get_user_stats()
            recommendations = self.watcher.get_revision_recommendations()
            
            return {
                'success': True,
                'stats': stats,
                'recommendations': recommendations,
                'user_level': self.user.level,
                'user_xp': self.user.xp
            }
            
        except Exception as e:
            print(f"Erreur lors de la génération du dashboard : {e}")
            return {
                'success': False,
                'error': str(e)
            }

def get_orchestrator(user=None):
    """Factory function pour créer un orchestrateur"""
    return AIOrchestrator(user)