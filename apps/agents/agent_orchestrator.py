# apps/agents/agent_orchestrator.py

from .agent_researcher import get_researcher_chain
from .agent_pedagogue import get_pedagogue_chain
from .agent_coach import generate_quiz, generate_code_exercise
from .agent_watcher import get_watcher_agent
from django.contrib.auth import get_user_model

# Déclare l'agent courant au monitorage (C20). Sans cette déclaration,
# les traces portent l'agent « inconnu » et la répartition par agent —
# celle qui permet d'arbitrer le routage des modèles — manque.
from apps.monitoring.sondes import sous_agent

User = get_user_model()

class AIOrchestrator:
    """
    Main orchestrator that coordinates all AI agents
    """
    
    def __init__(self, user=None):
        self.user = user
        self.researcher = get_researcher_chain()
        self.pedagogue = get_pedagogue_chain()
        if user:
            self.watcher = get_watcher_agent(user)
    
    @sous_agent("pedagogue")
    def generate_course(self, topic, difficulty="intermediate"):
        """
        Generates a complete course using Researcher + Pedagogue
        """
        try:
            print(f"🎓 Generating course on: {topic}")
            
            # Enhance prompt with module context
            enhanced_topic = topic
            if hasattr(self, 'current_module') and self.current_module:
                enhanced_topic = f"{topic} (dans le contexte de {self.current_module})"
            
            # 1. Generate structured course
            try:
                # Enhance context for pedagogue
                if hasattr(self.pedagogue, 'invoke'):
                    # With RAG
                    course_result = self.pedagogue.invoke({"query": enhanced_topic})
                else:
                    # Without RAG
                    course_result = self.pedagogue.invoke({"question": enhanced_topic})
                    
                content = course_result.get('result', course_result)
                sources = [doc.metadata.get('source', 'Unknown') for doc in course_result.get('source_documents', [])]
            except Exception as e:
                print(f"Error with RAG, using fallback: {e}")
                # Fallback without RAG (direct LLM call instead of RetrievalQA)
                try:
                    from apps.agents.tools.llm_loader import get_llm
                    from apps.agents.utils import load_prompt
                    from langchain.prompts import PromptTemplate
                    llm = get_llm()
                    prompt_template = load_prompt("pedagogue")
                    prompt = PromptTemplate(input_variables=["context", "question"], template=prompt_template)
                    formatted_prompt = prompt.format(context="Pas de contexte disponible (RAG désactivé)", question=enhanced_topic)
                    course_result = llm.invoke(formatted_prompt)
                    content = course_result.content if hasattr(course_result, 'content') else str(course_result)
                except Exception as inner_e:
                    print(f"Fallback direct LLM error: {inner_e}")
                    content = f"Désolé, une erreur technique est survenue: {inner_e}"
                sources = ["Generative AI (Fallback)"]
            
            # 3. Session tracking if user is connected
            session = None
            if self.user:
                try:
                    session = self.watcher.track_session(
                        topic=topic,
                        activity_type='course_generation',
                        metadata={}
                    )
                except Exception as e:
                    print(f"⚠️ Tracking disabled (missing table): {e}")
                    # Continue without tracking if tables don't exist yet
            
            return {
                'success': True,
                'topic': topic,
                'content': content,
                'sources': sources,
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Error during course generation: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'topic': topic
            }
    
    @sous_agent("researcher")
    def answer_question(self, question):
        """
        Answers a question using the RAG system
        """
        try:
            print(f"🔍 Searching for: {question}")
            
            # Use researcher to find and synthesize answer
            try:
                result = self.researcher.invoke(question)
                answer = result.get('result', result)
                sources = [doc.metadata.get('source', 'Unknown') for doc in result.get('source_documents', [])]
            except Exception as e:
                print(f"Error with RAG, using fallback: {e}")
                # Fallback without RAG (direct LLM call instead of RetrievalQA)
                try:
                    from apps.agents.tools.llm_loader import get_llm
                    from apps.agents.utils import load_prompt
                    from langchain.prompts import PromptTemplate
                    llm = get_llm()
                    prompt_template = load_prompt("researcher")
                    prompt = PromptTemplate(input_variables=["question"], template=prompt_template)
                    formatted_prompt = prompt.format(question=question)
                    result = llm.invoke(formatted_prompt)
                    answer = result.content if hasattr(result, 'content') else str(result)
                except Exception as inner_e:
                    print(f"Fallback direct LLM error: {inner_e}")
                    answer = f"Je ne peux pas répondre pour le moment. Erreur technique: {inner_e}"
                sources = ["Generative AI (Fallback)"]
            
            # Session tracking if user is connected
            session = None
            if self.user:
                try:
                    session = self.watcher.track_session(
                        topic=question[:100],  # Limit length
                        activity_type='chat',
                        metadata={'question': question}
                    )
                except Exception as e:
                    print(f"⚠️ Tracking disabled (missing table): {e}")
                    # Continue without tracking if tables don't exist yet
            
            return {
                'success': True,
                'question': question,
                'answer': answer,
                'sources': sources,
                'session_id': session.id if session else None
            }
            
        except Exception as e:
            print(f"Error answering question: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'question': question
            }
    
    @sous_agent("coach")
    def create_quiz(self, topic, num_questions):
        """
        Creates a quiz on a given topic and returns a directly usable dict.
        """
        try:
            # Get user language preference
            user_language = "fr"  # Default
            if self.user and hasattr(self.user, 'language_preference'):
                user_language = self.user.language_preference
            
            quiz_data = generate_quiz(topic, num_questions, user_language)

            # Session tracking (optional)
            session = None
            if self.user:
                session = self.watcher.track_session(
                    topic=topic,
                    activity_type='quiz',
                    metadata={
                        'num_questions': num_questions,
                        'language': user_language,
                    }
                )

            # Add metadata directly to return
            return {
                "questions": quiz_data["questions"],
                "topic": topic,
                "language": user_language,
                "session_id": session.id if session else None
            }

        except Exception as e:
            print(f"Error creating quiz: {e}")
            return {
                "questions": [],
                "error": str(e),
                "topic": topic
            }

    
    def submit_quiz_results(self, session_id, answers, quiz_data):
        """
        Processes quiz results and updates statistics
        """
        if not self.user or not session_id:
            return {'success': False, 'error': 'User or session not found'}
        
        try:
            # Calculate score
            correct_answers = 0
            total_questions = len(quiz_data['questions'])
            
            for i, user_answer in enumerate(answers):
                question = quiz_data['questions'][i]
                correct_answer = question['correct_answer']
                
                if user_answer == correct_answer:
                    correct_answers += 1
                else:
                    # Record the error
                    self.watcher.record_mistake(
                        topic=session_id,  # Use session_id as temporary topic
                        mistake_type='quiz_wrong_answer',
                        question=question['question'],
                        user_answer=question['options'][user_answer] if user_answer < len(question['options']) else 'No answer',
                        correct_answer=question['options'][correct_answer]
                    )
            
            score = (correct_answers / total_questions) * 100
            
            # End session
            session = self.watcher.end_session(session_id, score)
            
            # Calculate XP based on performance
            base_xp = 10  # Base XP for completing a quiz
            bonus_xp = int(score / 10)  # Score-based bonus (0-10 XP)
            streak_bonus = min(self.user.current_streak * 2, 20)  # Streak bonus (max 20 XP)
            
            total_xp = base_xp + bonus_xp + streak_bonus
            
            # Add XP and update stats
            xp_result = self.user.add_xp(total_xp, 'quiz_completion')
            self.user.total_quizzes_completed += 1
            self.user.save()
            
            return {
                'success': True,
                'score': score,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'xp_result': xp_result,
                'session': session,
                'streak_bonus': streak_bonus
            }
            
        except Exception as e:
            print(f"Error processing results: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_dashboard(self):
        """
        Generates user dashboard data
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
            print(f"Error generating dashboard: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def get_orchestrator(user=None):
    """Factory function to create an orchestrator"""
    return AIOrchestrator(user)
