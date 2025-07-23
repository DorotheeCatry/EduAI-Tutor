from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from apps.agents.agent_orchestrator import get_orchestrator
from .models import GameRoom, GameParticipant
from django.shortcuts import get_object_or_404
from django.contrib import messages
import json

@login_required
def quiz_lobby(request):
    # Récupérer les salles actives
    active_rooms = GameRoom.objects.filter(status__in=['waiting', 'starting']).order_by('-created_at')[:10]
    
    context = {
        'active_rooms': active_rooms
    }
    return render(request, 'quiz/quiz_lobby.html', context)

@login_required
def create_room(request):
    """Créer une nouvelle salle de jeu"""
    if request.method == 'POST':
        topic = request.POST.get('topic', 'Python général')
        num_questions = int(request.POST.get('num_questions', 10))
        max_players = int(request.POST.get('max_players', 20))
        
        # Créer la salle
        room = GameRoom.objects.create(
            code=GameRoom.generate_code(),
            host=request.user,
            topic=topic,
            num_questions=num_questions,
            max_players=max_players
        )
        
        # Ajouter l'hôte comme participant
        GameParticipant.objects.create(
            room=room,
            user=request.user
        )
        
        messages.success(request, f'Salle créée avec le code : {room.code}')
        return redirect('quiz:room_detail', room_code=room.code)
    
    return render(request, 'quiz/create_room.html')

@login_required
def join_room(request):
    """Rejoindre une salle existante"""
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        
        try:
            room = GameRoom.objects.get(code=room_code, status__in=['waiting', 'starting'])
            
            if room.is_full:
                messages.error(request, 'Cette salle est complète.')
                return render(request, 'quiz/join_room.html')
            
            # Ajouter le joueur s'il n'est pas déjà dans la salle
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
            messages.error(request, 'Salle introuvable ou déjà terminée.')
    
    return render(request, 'quiz/join_room.html')

@login_required
def room_detail(request, room_code):
    """Page de détail d'une salle (lobby d'attente)"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Vérifier si l'utilisateur est dans la salle
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user)
    except GameParticipant.DoesNotExist:
        messages.error(request, 'Vous devez rejoindre cette salle pour y accéder.')
        return redirect('quiz:join_room')
    
    participants = room.participants.filter(is_active=True).order_by('joined_at')
    
    context = {
        'room': room,
        'participants': participants,
        'is_host': room.host == request.user,
        'can_start': room.status == 'waiting' and room.player_count >= 1
    }
    
    return render(request, 'quiz/room_detail.html', context)

@login_required
def multiplayer_game(request, room_code):
    """Interface de jeu multijoueur"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Vérifier que l'utilisateur est participant
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user, is_active=True)
    except GameParticipant.DoesNotExist:
        messages.error(request, 'Vous n\'êtes pas autorisé à accéder à cette partie.')
        return redirect('quiz:lobby')
    
    context = {
        'room': room,
        'participant': participant
    }
    
    return render(request, 'quiz/multiplayer_game.html', context)
@login_required
def quiz_start(request):
    mode = request.GET.get('mode', 'solo')
    topic = request.GET.get('topic', 'Python général')

    # Générer un quiz avec l'IA
    orchestrator = get_orchestrator(request.user)
    try:
        num_questions = int(request.GET.get('num_questions', 10))
        if num_questions < 1 or num_questions > 50:
            num_questions = 10
    except (TypeError, ValueError):
        num_questions = 10
        
    result = orchestrator.create_quiz(topic, num_questions)

    # Vérifie que des questions ont bien été retournées
    quiz_data = result if result and "questions" in result and result["questions"] else None

    context = {
        'mode': mode,
        'topic': topic,
        'quiz_data': quiz_data,
        'error': None if quiz_data else "⚠️ Aucun quiz n’a pu être généré."
    }
    return render(request, 'quiz/quiz_start.html', context)

@csrf_exempt
@login_required
def submit_quiz(request):
    """API endpoint pour soumettre les résultats d'un quiz"""
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        answers = data.get('answers', [])
        quiz_data = data.get('quiz_data', {})
        
        orchestrator = get_orchestrator(request.user)
        result = orchestrator.submit_quiz_results(session_id, answers, quiz_data)
        
        return JsonResponse(result)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
@login_required
def quiz_result(request):
    return render(request, 'quiz/quiz_result.html')