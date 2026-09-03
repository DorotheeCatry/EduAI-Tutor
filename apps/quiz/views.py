from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from apps.agents.agent_orchestrator import get_orchestrator
from apps.agents.agent_watcher import UserMistake
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
        # Rattachement au référentiel par choix explicite, comme en solo et
        # pour les exercices (décision 027). Quand une compétence est choisie,
        # son intitulé devient le sujet de la partie : les deux désignent alors
        # la même chose par construction.
        competence = competence_par_code(request.POST.get('competence', '').strip())
        topic = (competence.intitule if competence
                 else request.POST.get('topic', 'General Python'))
        num_questions = int(request.POST.get('num_questions', 10))
        max_players = int(request.POST.get('max_players', 20))
        
        # Create room
        room = GameRoom.objects.create(
            competence=competence,
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
    
    return render(request, 'quiz/create_room.html', {
        'competences_par_module': competences_du_referentiel_actif(),
    })

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
            # Départ du chronomètre, côté serveur.
            #
            # Compétence visée : C17 (épreuve E4)
            #
            # Le temps de réponse était fourni par le navigateur —
            # `data.get('response_time', 60)`. Il mesurait donc la latence du
            # réseau et la vitesse de la machine autant que la rapidité de la
            # personne, et n'importe qui pouvait annoncer 0,1 seconde depuis
            # une console. Un classement falsifiable en une ligne n'est pas un
            # classement, et l'écart ne portait pas seulement sur l'exactitude :
            # sur l'équité entre participants.
            room.question_start_time = timezone.now()
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

def cloturer_les_sessions_de_la_partie(room):
    """
    Enregistre une session d'apprentissage close pour chaque participant.

    Compétence visée : C20 (épreuve E5) — données du suivi
    Compétences concernées : C17 (E4) ; C21 (E5)

    Choix : une session par participant, ouverte et close dans le même geste,
    plutôt que la clôture de celle qu'ouvre la génération du quiz. Motivation :
    cette dernière n'existe que pour l'hôte — c'est lui qui a demandé la
    génération. Les autres joueurs n'en ont aucune, et la page Référentiel
    comptait donc zéro quiz terminé pour eux alors qu'ils venaient d'en
    finir un. Le compteur annonçait « quiz terminés » et ne pouvait pas voir
    ceux du multijoueur (incident 012).

    Le score retenu est le pourcentage de bonnes réponses, pas les points :
    les points récompensent la vitesse, et la page affiche une moyenne que
    l'apprenant lira comme une réussite.
    """
    from apps.agents.agent_watcher import LearningSession

    total = room.questions.count()
    for participant in room.participants.all():
        deja = LearningSession.objects.filter(
            user=participant.user,
            activity_type='quiz_multijoueur',
            metadata__code_salle=room.code,
        ).exists()
        if deja:
            # Idempotence : le sondage peut prononcer la fin plusieurs fois.
            continue
        pourcentage = (participant.correct_answers / total * 100) if total else 0.0
        maintenant = timezone.now()
        debut = room.started_at or room.created_at
        LearningSession.objects.create(
            user=participant.user,
            topic=room.topic,
            activity_type='quiz_multijoueur',
            competence=room.competence,
            score=round(pourcentage, 1),
            start_time=debut,
            end_time=maintenant,
            duration_seconds=max(0, int((maintenant - debut).total_seconds())),
            metadata={
                'code_salle': room.code,
                'points': participant.score,
                'bonnes_reponses': participant.correct_answers,
                'questions': total,
            },
        )


def faire_avancer_la_partie(room):
    """
    Prononce le passage à la question suivante, ou la fin de la partie.

    Compétence visée : C17 (épreuve E4)

    Choix : cet arbitrage est appelé par la soumission d'une réponse ET par le
    sondage d'état, alors qu'il ne vivait que dans la première. Motivation : la
    fin de partie ne pouvait être prononcée que par un joueur en train de
    répondre. Si le dernier participant attendu ferme son navigateur, plus
    aucune réponse n'arrive et la partie reste ouverte indéfiniment — personne
    ne reste pour la conclure. Le sondage, lui, bat toutes les deux secondes
    tant qu'une page est ouverte : c'est le seul signal encore disponible quand
    plus personne ne joue.

    Retourne True si tous les joueurs présents ont répondu à la question
    courante.
    """
    if room.status != 'in_progress':
        return room.status == 'finished'

    question_courante = GameQuestion.objects.filter(
        room=room, question_number=room.current_question
    ).first()
    if question_courante is None:
        return False

    # La partie attend les PRÉSENTS, pas les inscrits : la présence se déduit
    # du dernier sondage, pas d'un drapeau que rien ne remet à faux.
    joueurs_presents = sum(
        1 for p in room.participants.filter(is_active=True) if p.est_present
    )
    ont_repondu = GameAnswer.objects.filter(question=question_courante).count()
    tous_ont_repondu = ont_repondu >= max(1, joueurs_presents)

    if not tous_ont_repondu:
        return False

    if room.current_question < room.num_questions:
        room.current_question += 1
        # Le chronomètre repart avec la question, côté serveur.
        room.question_start_time = timezone.now()
        room.save()
    else:
        room.status = 'finished'
        room.finished_at = timezone.now()
        room.save()
        cloturer_les_sessions_de_la_partie(room)

    return True


@login_required
def room_status_api(request, room_code):
    """API pour récupérer le statut de la room en temps réel"""
    try:
        room = get_object_or_404(GameRoom, code=room_code)
        
        # Garde d'accès — SANS exiger `is_active`.
        #
        # Compétence visée : C17 (épreuve E4)
        #
        # Exiger un participant actif refusait l'entrée à quiconque revenait
        # après une coupure : la page de jeu répondait « vous n'êtes pas
        # autorisé » à sa propre partie. Le retour est ici la règle, pas
        # l'exception — un onglet fermé, un portable en veille, un réseau qui
        # saute.
        moi = GameParticipant.objects.get(room=room, user=request.user)
        if not moi.is_active:
            moi.is_active = True
        # Ce sondage EST le battement de cœur : il a lieu toutes les deux
        # secondes tant que la page est ouverte.
        moi.derniere_activite = timezone.now()
        moi.save(update_fields=['is_active', 'derniere_activite'])

        # Le sondage arbitre aussi. Sans cela, une partie dont le dernier
        # joueur attendu a fermé son navigateur ne se termine jamais : seule
        # une soumission pouvait prononcer la fin, et il n'en viendra plus.
        # Le battement de cœur ci-dessus doit précéder cet appel, faute de
        # quoi le joueur qui sonde ne se compterait pas lui-même comme
        # présent.
        faire_avancer_la_partie(room)

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
        # `is_active` n'est pas exigé : un participant qui revient doit
        # retrouver sa partie, à la question en cours.
        participant = GameParticipant.objects.get(room=room, user=request.user)
    except GameParticipant.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if not participant.is_active:
        participant.is_active = True
    participant.derniere_activite = timezone.now()
    participant.save(update_fields=['is_active', 'derniere_activite'])
    
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

        # Le temps de réponse est CALCULÉ ICI, à partir de l'horodatage posé
        # par le serveur au moment où la question a été servie. La valeur
        # envoyée par le navigateur, s'il en envoie une, n'est pas lue.
        #
        # Repli sur la durée maximale quand l'horodatage manque — parties
        # lancées avant ce correctif. Un repli haut plutôt que bas : il ne
        # donne aucun point immérité, là où un repli à zéro en donnerait le
        # maximum.
        if room.question_start_time:
            ecoule = (timezone.now() - room.question_start_time).total_seconds()
            response_time = max(0.0, min(ecoule, 60.0))
        else:
            response_time = 60.0
        
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
            else:
                # Une mauvaise réponse alimente le bloc « à revoir », comme en
                # solo (décision 028).
                #
                # Compétence visée : C17 (épreuve E4), C20 (E5)
                #
                # Sans cela, une partie multijoueur ne laissait AUCUNE trace
                # dans le parcours : ni progression — c'est voulu, un quiz ne
                # certifie pas une production — ni lacune signalée, ce qui
                # l'était moins. Une partie se terminait sans que rien n'en
                # subsiste pour l'apprenant.
                options = current_question.options or []
                donnee = (options[answer_index]
                          if isinstance(answer_index, int)
                          and 0 <= answer_index < len(options)
                          else 'Sans réponse')
                attendue = (options[current_question.correct_answer]
                            if 0 <= current_question.correct_answer < len(options)
                            else '')
                UserMistake.objects.create(
                    user=request.user,
                    topic=room.topic,
                    competence=room.competence,
                    mistake_type='quiz_multijoueur',
                    question=current_question.question_text,
                    user_answer=donnee,
                    correct_answer=attendue,
                )
            participant.save()
            
            # L'arbitrage — qui attend qui, et quand la partie s'achève — vit
            # dans `faire_avancer_la_partie`, appelée ici et par le sondage
            # d'état. Voir sa docstring : une partie doit pouvoir se conclure
            # même quand plus personne ne répond.
            all_answered = faire_avancer_la_partie(room)
            print(f"👥 All answered: {all_answered} (question {room.current_question}/{room.num_questions})")
            
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
    
    # Le retour d'un participant est la règle, pas l'exception : exiger
    # `is_active` renvoyait vers le salon quiconque revenait après une coupure.
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user)
    except GameParticipant.DoesNotExist:
        messages.error(request, _('You are not authorized to access this game.'))
        return redirect('quiz:lobby')

    if not participant.is_active:
        participant.is_active = True
        participant.save(update_fields=['is_active'])
    
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

    # Plusieurs notions à la fois, cochées dans le bloc « à revoir ».
    #
    # Compétence visée : C17 (épreuve E4)
    # Choix : un paramètre répété `notion`, et non une liste séparée par des
    # virgules. Motivation : plusieurs intitulés du référentiel contiennent des
    # virgules — ceux qui énumèrent des notions. Une liste à séparateur les
    # découperait en notions inexistantes, et le quiz porterait sur un sujet
    # que personne n'a demandé.
    #
    # Chaque valeur est d'abord cherchée comme CODE de compétence ; ce qui n'en
    # est pas est repris comme sujet libre, puisqu'un quiz peut avoir été lancé
    # hors référentiel (décision 027).
    notions = [n.strip() for n in request.GET.getlist('notion') if n.strip()]
    if notions:
        intitules = []
        for notion in notions:
            trouvee = competence_par_code(notion)
            intitules.append(trouvee.intitule if trouvee else notion)
        # Le quiz porte sur l'ensemble : c'est ce que « revoir mes erreurs »
        # veut dire. Une seule notion cochée redonne exactement le cas simple.
        topic = ' ; '.join(dict.fromkeys(intitules))
        # Une compétence n'est retenue que si elle est SEULE : un quiz qui
        # couvre trois notions ne se rattache honnêtement à aucune.
        competence = competence_par_code(notions[0]) if len(notions) == 1 else None
    else:
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
