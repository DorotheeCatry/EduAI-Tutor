# apps/agents/agent_orchestrator.py

from .agent_researcher import get_researcher_chain
from .agent_pedagogue import get_pedagogue_chain
from .agent_coach import generate_quiz, generate_code_exercise
from .agent_watcher import LearningSession, get_watcher_agent
from django.contrib.auth import get_user_model

# Déclare l'agent courant au monitorage (C20). Sans cette déclaration,
# les traces portent l'agent « inconnu » et la répartition par agent —
# celle qui permet d'arbitrer le routage des modèles — manque.
from apps.monitoring.sondes import sous_agent

# Quota de génération (C13). Chaque méthode ci-dessous déclenche un appel
# facturé : le décompte a lieu ici, au goulot par lequel passent toutes les
# entrées — vues Django comme service FastAPI, qui amorce Django et réutilise
# ces mêmes agents. Un contrôle posé sur les vues laisserait le second sans
# protection. Voir docs/decisions/019.
from apps.quotas.service import consommer, consommer_pour_le_service_ia

import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class AIOrchestrator:
    """
    Main orchestrator that coordinates all AI agents
    """
    
    def __init__(self, user=None, pour_service_ia=False):
        self.user = user
        # Déclare qui décompte la génération (C13). L'API du service IA n'a pas
        # d'apprenant à qui l'imputer : ses consommateurs sont des programmes
        # porteurs d'une clé de service. Le drapeau est explicite et non déduit
        # de `user is None` — une absence d'utilisateur peut aussi signifier
        # qu'une vue a oublié de le transmettre, et les deux cas n'appellent
        # pas la même règle.
        self.pour_service_ia = pour_service_ia
        self.researcher = get_researcher_chain()
        self.pedagogue = get_pedagogue_chain()
        if user:
            self.watcher = get_watcher_agent(user)

    def _decompter(self):
        """
        Décompte la génération sur le bon compteur, ou lève `QuotaDepasse`.

        Compétence visée : C13 (épreuve E3)

        Appelé en tête des trois méthodes génératrices, hors de leur `try` :
        ces blocs interceptent `Exception` et transformeraient le refus en
        panne technique affichée à l'apprenant.
        """
        if self.pour_service_ia:
            return consommer_pour_le_service_ia()
        return consommer(self.user)
    
    @sous_agent("pedagogue")
    def generate_course(self, topic, difficulty="intermediate"):
        """
        Generates a complete course using Researcher + Pedagogue

        Compétence visée : C13 (épreuve E3) — le quota est décompté ici.
        """
        # Hors du `try` ci-dessous, délibérément : ce bloc intercepte
        # `Exception` et renverrait le refus sous la forme d'une panne
        # technique. `QuotaDepasse` doit remonter jusqu'à l'appelant, qui seul
        # sait comment l'annoncer à l'apprenant.
        self._decompter()

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

        Compétence visée : C13 (épreuve E3) — le quota est décompté ici.
        """
        # Voir generate_course : le décompte précède le `try` pour la même
        # raison. Cette méthode sert aussi bien le chat que la génération
        # d'exercices, qui la sollicitent avec des invites différentes.
        self._decompter()

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
    def create_quiz(self, topic, num_questions, competence=None):
        """
        Creates a quiz on a given topic and returns a directly usable dict.

        Compétence visée : C13 (épreuve E3) — le quota est décompté ici.
        """
        # Voir generate_course. Un quiz de dix questions est une seule
        # génération : c'est un seul appel au modèle.
        self._decompter()

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
                    competence=competence,
                    metadata={
                        'num_questions': num_questions,
                        'language': user_language,
                        # Les questions sont conservées côté serveur.
                        #
                        # Compétence visée : C17 (épreuve E4)
                        #
                        # Sans elles, la correction du quiz ne pouvait se faire
                        # qu'à partir de ce que le navigateur renvoyait — donc
                        # à partir de données que l'apprenant peut réécrire. Le
                        # score, le décompte des bonnes réponses et l'énoncé
                        # des erreurs se calculent désormais ici.
                        #
                        # Ce que cela ne corrige pas : les bonnes réponses sont
                        # envoyées au navigateur pour l'affichage de la
                        # correction, et restent donc lisibles dans la page. Ce
                        # quiz mesure un apprentissage, il ne certifie rien —
                        # la triche y coûte plus qu'elle ne rapporte.
                        'questions': quiz_data["questions"],
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

    
    def submit_quiz_results(self, session_id, answers):
        """
        Enregistre le résultat d'un quiz solo terminé.

        Compétence visée : C17 (épreuve E4) — application web
        Compétences concernées : C20 (E5) — données du suivi ; C21 (E5)

        Deux défauts corrigés le 31/08/2026, consignés en incident 010.

        Le premier : cette méthode n'était appelée par personne. Le gabarit du
        quiz affichait le score dans une boîte de dialogue puis redirigeait.

        Le second : les erreurs étaient enregistrées avec `topic=session_id`,
        sous un commentaire « temporary topic ». Le sujet d'une erreur était
        donc un identifiant de session — un nombre — au lieu de la notion. Rien
        ne pouvait se construire dessus, et le provisoire avait duré.

        Choix : la notion vient de la session, relue en base, et non du corps
        de la requête. Motivation : c'est la seule valeur dont le serveur soit
        l'auteur. Elle a été écrite par `create_quiz` au moment de la
        génération, avec le sujet réellement demandé.
        """
        if not self.user or not session_id:
            return {'success': False, 'error': 'User or session not found'}

        session = LearningSession.objects.filter(
            id=session_id, user=self.user, activity_type='quiz',
        ).first()

        if session is None:
            return {'success': False, 'error': 'Session de quiz introuvable'}

        questions = (session.metadata or {}).get('questions') or []
        if not questions:
            # Une session ouverte avant que les questions ne soient conservées
            # côté serveur. On ne fabrique pas un score à partir de rien.
            return {'success': False,
                    'error': 'Questions absentes de la session, résultat non enregistré'}

        try:
            correct_answers = 0

            for index, question in enumerate(questions):
                reponse = answers[index] if index < len(answers) else -1
                bonne_reponse = question.get('correct_answer')

                if reponse == bonne_reponse:
                    correct_answers += 1
                    continue

                options = question.get('options') or []
                # -1 signale une question laissée sans réponse : le temps
                # écoulé sans clic. C'est un état distinct d'une mauvaise
                # réponse, et l'écrire tel quel évite de compter comme erreur
                # de compréhension ce qui n'est qu'un abandon.
                if reponse == -1:
                    donnee = 'Sans réponse'
                elif 0 <= reponse < len(options):
                    donnee = options[reponse]
                else:
                    donnee = 'Réponse hors des options proposées'

                self.watcher.record_mistake(
                    # La NOTION, et non l'identifiant de session.
                    topic=session.topic,
                    # Et la compétence, quand l'apprenant en a choisi une :
                    # c'est ce qui permet au bloc « à revoir » de parler la
                    # même langue que le reste de la page.
                    competence=session.competence,
                    mistake_type='quiz_wrong_answer',
                    question=question.get('question', ''),
                    user_answer=donnee,
                    correct_answer=(options[bonne_reponse]
                                    if isinstance(bonne_reponse, int)
                                    and 0 <= bonne_reponse < len(options)
                                    else ''),
                )

            total_questions = len(questions)
            score = (correct_answers / total_questions) * 100

            session_close = self.watcher.end_session(session_id, score)

            base_xp = 10
            bonus_xp = int(score / 10)
            streak_bonus = min(self.user.current_streak * 2, 20)
            total_xp = base_xp + bonus_xp + streak_bonus

            xp_result = self.user.add_xp(total_xp, 'quiz_completion')
            self.user.total_quizzes_completed += 1
            self.user.save()

            return {
                'success': True,
                'score': score,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'topic': session.topic,
                'xp_result': xp_result,
                # Un résumé, et non l'objet de session : un modèle Django ne
                # se sérialise pas en JSON, et le renvoyer levait une erreur
                # 500. Le défaut existait depuis l'origine dans ce chemin que
                # rien n'appelait — il attendait d'être exécuté pour se voir.
                'session': {
                    'id': session_close.id,
                    'duree_secondes': session_close.duration_seconds,
                } if session_close else None,
                'streak_bonus': streak_bonus,
            }

        except Exception as erreur:
            # Volontairement large, et journalisée plutôt que tue : le quiz est
            # terminé du point de vue de l'apprenant, mais son résultat n'a pas
            # été enregistré. L'absence de clôture de la session est ce qui
            # rendra l'écart visible au monitorage.
            logger.exception(
                "resultat de quiz non enregistre pour la session %s : %s",
                session_id, erreur,
            )
            return {'success': False, 'error': str(erreur)}

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

def get_orchestrator(user=None, pour_service_ia=False):
    """
    Factory function to create an orchestrator

    Compétence visée : C13 (épreuve E3)

    `pour_service_ia` doit valoir True pour les appels venus de l'API FastAPI :
    ils sont décomptés du plafond global du jour et non du quota d'un apprenant.
    """
    return AIOrchestrator(user, pour_service_ia=pour_service_ia)
