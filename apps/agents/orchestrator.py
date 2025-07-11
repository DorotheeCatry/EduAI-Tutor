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
            print(f"🎓 Génération de cours sur : {topic} (niveau: {difficulty})")
            
            # Améliorer le prompt avec le contexte du module
            enhanced_topic = topic
            if hasattr(self, 'current_module') and self.current_module:
                enhanced_topic = f"{topic} (dans le contexte de {self.current_module})"
            
            # 1. Génération du cours structuré
            try:
                # Améliorer le contexte pour le pédagogue
                if hasattr(self.pedagogue, 'invoke'):
                    # Avec RAG
                    course_result = self.pedagogue.invoke({"query": enhanced_topic})
                else:
                    # Sans RAG
                    course_result = self.pedagogue.invoke({"question": enhanced_topic})
                    
                content = course_result.get('result', course_result)
                sources = [doc.metadata.get('source', 'Unknown') for doc in course_result.get('source_documents', [])]
            except Exception as e:
                print(f"Erreur avec RAG, utilisation du fallback : {e}")
                # Fallback sans RAG
                try:
                    course_result = self.pedagogue.invoke({"question": enhanced_topic})
                except:
                    course_result = self.pedagogue.run(question=enhanced_topic)
                content = course_result.get('text', str(course_result))
                sources = ["IA générative"]
            
            # 3. Tracking de la session si utilisateur connecté
            session = None
            if self.user:
                try:
                    session = self.watcher.track_session(
                        topic=topic,
                        activity_type='course_generation',
                        metadata={'difficulty': difficulty}
                    )
                except Exception as e:
                    print(f"⚠️ Tracking désactivé (table manquante) : {e}")
                    # Continuer sans tracking si les tables n'existent pas encore
            
            return {
                'success': True,
                'topic': topic,
                'difficulty': difficulty,
                'content': content,
                'sources': sources,
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Erreur lors de la génération du cours : {e}")
            import traceback
            traceback.print_exc()
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
            print(f"🔍 Recherche pour : {question}")
            
            # Utiliser le chercheur pour trouver et synthétiser la réponse
            try:
                result = self.researcher.invoke(question)
                answer = result.get('result', result)
                sources = [doc.metadata.get('source', 'Unknown') for doc in result.get('source_documents', [])]
            except Exception as e:
                print(f"Erreur avec RAG, utilisation du fallback : {e}")
                # Fallback sans RAG
                result = self.researcher.invoke({"question": question})
                answer = result.get('text', str(result))
                sources = ["IA générative"]
            
            # Tracking de la session si utilisateur connecté
            session = None
            if self.user:
                try:
                    session = self.watcher.track_session(
                        topic=question[:100],  # Limiter la longueur
                        activity_type='chat',
                        metadata={'question': question}
                    )
                except Exception as e:
                    print(f"⚠️ Tracking désactivé (table manquante) : {e}")
                    # Continuer sans tracking si les tables n'existent pas encore
            
            return {
                'success': True,
                'question': question,
                'answer': answer,
                'sources': sources,
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Erreur lors de la réponse à la question : {e}")
            import traceback
            traceback.print_exc()
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