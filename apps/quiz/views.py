from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from apps.agents.agent_orchestrator import get_orchestrator
from apps.chat.actions import actions_pour
from apps.referentiel.services import (
    competence_par_code,
    competences_du_referentiel_actif,
)
from apps.quotas.service import QuotaDepasse
from .models import GameRoom, GameParticipant, GameQuestion, GameAnswer
from django.shortcuts import get_object_or_404
from django.contrib import messages
import json
from django.utils.translation import gettext as _

@login_required
def delete_room(request, room_code):
    """Delete a room (host only)"""
    try:
        room = get_object_or_404(GameRoom, code=room_code)
        
        # Check if user is host
        if room.host != request.user:
            messages.error(request, _('Only the host can delete this room.'))
            return redirect('quiz:lobby')
        
        room_topic = room.topic
        room.delete()
        messages.success(request, _('Room "%(sujet)s" deleted successfully!')
                              % {"sujet": room_topic})
        
    except GameRoom.DoesNotExist:
        messages.error(request, _('Room not found.'))
    except Exception as e:
        messages.error(request, _("Error deleting room: %(erreur)s")
                            % {"erreur": e})
    
    return redirect('quiz:lobby')

@login_required
def quiz_lobby(request):
    # Get active rooms
    active_rooms = GameRoom.objects.filter(status__in=['waiting', 'starting']).order_by('-created_at')[:10]

    # Score moyen réel, sur les seules sessions closes : une session ouverte
    # est un quiz engendré, pas un quiz fait (incident 010).
    from django.db.models import Avg

    from apps.agents.agent_watcher import LearningSession

    score_moyen = LearningSession.objects.filter(
        user=request.user, activity_type='quiz',
        end_time__isnull=False, score__isnull=False,
    ).aggregate(moyenne=Avg('score'))['moyenne']

    context = {
        'active_rooms': active_rooms,
        'score_moyen': score_moyen,
        # Les compétences proposées au lancement d'un quiz solo. Sans ce menu,
        # aucune session ne porterait de compétence et le bloc « à revoir »
        # resterait en sujets libres.
        'competences_par_module': competences_du_referentiel_actif(),
    }
    return render(request, 'quiz/quiz_lobby.html', context)

@login_required
def create_room(request):
    """Create a new game room"""
    if request.method == 'POST':
        topic = request.POST.get('topic', 'General Python')
        num_questions = int(request.POST.get('num_questions', 10))
        max_players = int(request.POST.get('max_players', 20))
        
        # Create room
        room = GameRoom.objects.create(
            code=GameRoom.generate_code(),
            host=request.user,
            topic=topic,
            num_questions=num_questions,
            max_players=max_players
        )
        
        # Add host as participant
        GameParticipant.objects.create(
            room=room,
            user=request.user
        )
        
        messages.success(request, _("Room created with code: %(code)s")
                              % {"code": room.code})
        return redirect('quiz:room_detail', room_code=room.code)
    
    return render(request, 'quiz/create_room.html')

@login_required
def start_multiplayer_game(request, room_code):
    """Start multiplayer game (host only)"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check if user is host
    if room.host != request.user:
        messages.error(request, _('Only the host can start the game.'))
        return redirect('quiz:room_detail', room_code=room_code)
    
    # Check if room is in waiting state
    if room.status != 'waiting':
        messages.error(request, _('Game already started or finished.'))
        return redirect('quiz:room_detail', room_code=room_code)
    
    # Generate questions using AI
    try:
        orchestrator = get_orchestrator(request.user)
        quiz_data = orchestrator.create_quiz(room.topic, room.num_questions)
        
        if quiz_data and quiz_data.get('questions'):
            # Save questions to database
            for i, question_data in enumerate(quiz_data['questions']):
                GameQuestion.objects.create(
                    room=room,
                    question_number=i + 1,
                    question_text=question_data['question'],
                    options=question_data['options'],
                    correct_answer=question_data['correct_answer'],
                    explanation=question_data.get('explanation', '')
                )
            
            # Update room status
            room.status = 'in_progress'
            room.current_question = 1
            room.save()
            
            messages.success(request, _("Game started! %(nombre)s questions generated.")
                              % {"nombre": len(quiz_data["questions"])})
            return redirect('quiz:multiplayer_game', room_code=room_code)
        else:
            messages.error(request, _('Failed to generate questions. Please try again.'))
            
    # Quota de génération (C13), intercepté avant le cas général : le message
    # « réessayez » du bloc suivant serait faux ici, la partie ne pouvant pas
    # être lancée avant demain.
    except QuotaDepasse as depassement:
        messages.warning(request, depassement.message)

    except Exception as e:
        print(f"Error generating questions: {e}")
        messages.error(request, _("Error generating questions: %(erreur)s")
                            % {"erreur": e})
    
    return redirect('quiz:room_detail', room_code=room_code)

@login_required
def join_room(request):
    """Join an existing room"""
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        
        try:
            room = GameRoom.objects.get(code=room_code, status__in=['waiting', 'starting'])
            
            if room.is_full:
                messages.error(request, _('This room is full.'))
                return render(request, 'quiz/join_room.html')
            
            # Add player if not already in room
            participant, created = GameParticipant.objects.get_or_create(
                room=room,
                user=request.user,
                defaults={'is_active': True}
            )
            
            if not created:
                participant.is_active = True
                participant.save()
            
            return redirect('quiz:room_detail', room_code=room.code)
            
        except GameRoom.DoesNotExist:
            messages.error(request, _('Room not found or already finished.'))
    
    return render(request, 'quiz/join_room.html')

@login_required
def room_detail(request, room_code):
    """Room detail page (waiting lobby)"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check if user is in room
    try:
        # Garde d'accès : la levée de DoesNotExist est l'effet recherché,
        # l'objet lui-même n'est jamais utilisé.
        GameParticipant.objects.get(room=room, user=request.user)
    except GameParticipant.DoesNotExist:
        messages.error(request, _('You must join this room to access it.'))
        return redirect('quiz:join_room')
    
    participants = room.participants.filter(is_active=True).order_by('joined_at')
    
    context = {
        'room': room,
        'participants': participants,
        'is_host': room.host == request.user,
        'can_start': room.status == 'waiting' and room.player_count >= 1  # Allow single player
    }
    
    return render(request, 'quiz/room_detail.html', context)

@login_required
def room_status_api(request, room_code):
    """API pour récupérer le statut de la room en temps réel"""
    try:
        room = get_object_or_404(GameRoom, code=room_code)
        
        # Vérifier que l'utilisateur est dans la room
        # Garde d'accès, comme ci-dessus.
        GameParticipant.objects.get(room=room, user=request.user, is_active=True)
        
        participants = room.participants.filter(is_active=True).order_by('-score', 'joined_at')
        
        participants_data = []
        for p in participants:
            avatar_url = '/static/koda/koda_base.png'  # Default
            if p.user.avatar:
                if hasattr(p.user.avatar, 'url'):
                    avatar_url = p.user.avatar.url
                else:
                    avatar_url = f'/static/koda/{p.user.avatar}'
            elif p.user.koda_avatar:
                avatar_url = f'/static/koda/{p.user.koda_avatar}'
            
            participants_data.append({
                'username': p.user.username,
                'score': p.score,
                'correct_answers': p.correct_answers,
                'is_host': p.user == room.host,
                'avatar_url': avatar_url
            })
        
        return JsonResponse({
            'status': room.status,
            'current_question': room.current_question,
            'participants': participants_data,
            'player_count': room.player_count,
            'can_start': room.status == 'waiting' and room.host == request.user
        })
        
    except (GameRoom.DoesNotExist, GameParticipant.DoesNotExist):
        return JsonResponse({'error': 'Room or participant not found'}, status=404)

@login_required
def multiplayer_quiz_api(request, room_code):
    """API pour le quiz multijoueur en temps réel"""
    print(f"🎯 API Quiz called for room {room_code}, method: {request.method}")
    
    room = get_object_or_404(GameRoom, code=room_code)
    
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user, is_active=True)
    except GameParticipant.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    if request.method == 'GET':
        # Récupérer la question actuelle
        try:
            print(f"📝 Getting question {room.current_question} for room {room_code}")
            
            current_question = GameQuestion.objects.get(
                room=room,
                question_number=room.current_question
            )
            
            print(f"✅ Found question: {current_question.question_text[:50]}...")
            
            # Vérifier si l'utilisateur a déjà répondu
            has_answered = GameAnswer.objects.filter(
                participant=participant,
                question=current_question
            ).exists()
            
            return JsonResponse({
                'question': {
                    'number': current_question.question_number,
                    'total': room.num_questions,
                    'text': current_question.question_text,
                    'options': current_question.options
                },
                'has_answered': has_answered,
                'time_left': 60,  # Simplification pour l'instant
                'room_status': room.status
            })
            
        except GameQuestion.DoesNotExist:
            print(f"❌ Question {room.current_question} not found for room {room_code}")
            return JsonResponse({'error': 'Question not found'}, status=404)
    
    elif request.method == 'POST':
        # Soumettre une réponse
        print(f"📤 Submitting answer for room {room_code}")
        
        data = json.loads(request.body)
        answer_index = data.get('answer')
        response_time = data.get('response_time', 60)
        
        print(f"📊 Answer: {answer_index}, Response time: {response_time}s")
        
        try:
            current_question = GameQuestion.objects.get(
                room=room,
                question_number=room.current_question
            )
            
            # Vérifier si déjà répondu
            existing_answer = GameAnswer.objects.filter(
                participant=participant,
                question=current_question
            ).first()
            
            if existing_answer:
                return JsonResponse({'error': 'Already answered'}, status=400)
            
            print("💾 Creating answer record...")
            
            # Créer la réponse
            game_answer = GameAnswer.objects.create(
                participant=participant,
                question=current_question,
                selected_answer=answer_index,
                response_time=response_time
            )
            
            # Calculer les points
            points = game_answer.calculate_points()
            game_answer.save()
            
            print(f"🎯 Points calculated: {points}")
            
            # Mettre à jour le score du participant
            participant.score += points
            if game_answer.is_correct:
                participant.correct_answers += 1
            participant.save()
            
            # Vérifier si tous les joueurs ont répondu
            active_players = room.participants.filter(is_active=True).count()
            answered_players = GameAnswer.objects.filter(
                question=current_question
            ).count()
            
            all_answered = answered_players >= active_players
            
            print(f"📈 Updated participant score: {participant.score}")
            print(f"👥 All answered: {all_answered} ({answered_players}/{active_players})")
            
            # Move to next question if all answered
            if all_answered and room.current_question < room.num_questions:
                room.current_question += 1
                room.save()
                print(f"➡️ Moving to question {room.current_question}")
            elif all_answered and room.current_question >= room.num_questions:
                room.status = 'finished'
                room.save()
                print("🏁 Game finished!")
            
            return JsonResponse({
                'success': True,
                'points': points,
                'is_correct': game_answer.is_correct,
                'correct_answer': current_question.correct_answer,
                'explanation': current_question.explanation,
                'all_answered': all_answered,
                'new_score': participant.score,
                'next_question_ready': all_answered
            })
            
        except GameQuestion.DoesNotExist:
            print("❌ Question not found when submitting answer")
            return JsonResponse({'error': 'Question not found'}, status=404)
        except Exception as e:
            print(f"❌ Error submitting answer: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
@login_required
def multiplayer_game(request, room_code):
    """Multiplayer game interface"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check that user is participant
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user, is_active=True)
    except GameParticipant.DoesNotExist:
        messages.error(request, _('You are not authorized to access this game.'))
        return redirect('quiz:lobby')
    
    context = {
        'room': room,
        'participant': participant
    }
    
    return render(request, 'quiz/multiplayer_game.html', context)
@login_required
def quiz_start(request):
    """
    Lance un quiz solo sur un sujet ou une compétence choisie.

    Compétence visée : C17 (épreuve E4)

    Le rattachement au référentiel vient d'un choix explicite, comme pour les
    exercices (décision 027). Quand une compétence est choisie, son intitulé
    devient le sujet du quiz : les deux désignent alors la même chose par
    construction.
    """
    mode = request.GET.get('mode', 'solo')
    competence = competence_par_code(request.GET.get('competence', '').strip())
    topic = (competence.intitule if competence
             else request.GET.get('topic', 'General Python'))

    # Generate quiz with AI
    orchestrator = get_orchestrator(request.user)
    try:
        num_questions = int(request.GET.get('num_questions', 10))
        if num_questions < 1 or num_questions > 50:
            num_questions = 10
    except (TypeError, ValueError):
        num_questions = 10
        
    # Quota de génération (C13). La page prévoit déjà un champ `error` : le
    # message du refus y prend la place du message d'échec technique.
    try:
        result = orchestrator.create_quiz(topic, num_questions, competence=competence)
    except QuotaDepasse as depassement:
        return render(request, 'quiz/quiz_start.html', {
            'mode': mode,
            'topic': topic,
            'quiz_data': None,
            'error': depassement.message,
        })

    # Check that questions were actually returned
    quiz_data = result if result and "questions" in result and result["questions"] else None

    # Contexte transmis au tuteur, EXPURGÉ des bonnes réponses.
    #
    # Compétence visée : C10 (épreuve E3)
    #
    # `quiz_data` porte `correct_answer` et `explanation` : le navigateur en a
    # besoin pour afficher la correction après chaque question. Le tuteur, non.
    # Un tuteur qui connaît la réponse attendue la donne — c'est ce qu'on lui
    # demande de faire, aider — et le quiz cesse de mesurer quoi que ce soit
    # (décision 029).
    #
    # L'expurgation a lieu ICI, côté serveur : la version destinée au tuteur ne
    # contient jamais la réponse, pas même dans la page. La laisser au
    # navigateur reviendrait à confier ce refus à du JavaScript qu'une refonte
    # peut réécrire.
    contexte_tuteur = None
    if quiz_data:
        contexte_tuteur = {
            'page': 'quiz',
            'resume': topic,
            'elements': [{'libelle': "Quiz", 'valeur': topic}],
            'charge': {'sujet': topic},
            'questions_sans_reponse': [
                {'question': question.get('question', ''),
                 'options': list(question.get('options', []))}
                for question in quiz_data['questions']
            ],
            'actions': [
                {'code': action['code'], 'libelle': str(action['libelle'])}
                for action in actions_pour('quiz')
            ],
        }

    context = {
        'mode': mode,
        'topic': topic,
        'quiz_data': quiz_data,
        'contexte_tuteur': contexte_tuteur,
        'error': None if quiz_data else "⚠️ No quiz could be generated."
    }
    return render(request, 'quiz/quiz_start.html', context)

@require_POST
@login_required
def submit_quiz(request):
    """
    Enregistre le résultat d'un quiz solo.

    Compétence visée : C17 (épreuve E4) — application web
    Compétences concernées : C20 (E5) — les données du suivi ; C13 (E3)

    Ce point de terminaison existait, était routé, et n'était appelé par
    personne : le gabarit du quiz affichait le score dans une boîte de dialogue
    puis redirigeait, sans rien envoyer. Aucune session n'était close, aucune
    erreur enregistrée, aucun compteur incrémenté (incident 010).

    Choix : `@require_POST` remplace le test manuel de la méthode, et
    `@csrf_exempt` est RETIRÉ. Motivation : cette vue modifie les statistiques
    du compte connecté. Un point de terminaison qui écrit sans protection CSRF
    est déclenchable depuis n'importe quelle page tierce ouverte dans le
    navigateur de l'apprenant — le gabarit envoie donc le jeton.

    Choix : le corps n'apporte que `session_id` et `answers`. Motivation : le
    sujet du quiz et ses bonnes réponses sont relus côté serveur, depuis la
    session et le quiz enregistrés. Les accepter du client permettrait de
    s'attribuer un score en les fabriquant.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "corps de requête illisible"},
            status=400,
        )

    session_id = data.get("session_id")
    answers = data.get("answers", [])

    if not isinstance(answers, list):
        return JsonResponse(
            {"success": False, "error": "`answers` doit être une liste"},
            status=400,
        )

    orchestrator = get_orchestrator(request.user)
    resultat = orchestrator.submit_quiz_results(session_id, answers)

    return JsonResponse(resultat, status=200 if resultat.get("success") else 400)
@login_required
def quiz_result(request):
    return render(request, 'quiz/quiz_result.html')
