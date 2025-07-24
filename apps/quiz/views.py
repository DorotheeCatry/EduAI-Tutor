from django.shortcuts import render
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from apps.agents.agent_orchestrator import get_orchestrator
from .models import GameRoom, GameParticipant, GameQuestion
from django.shortcuts import get_object_or_404
from django.contrib import messages
import json

@login_required
def quiz_lobby(request):
    # Get active rooms
    active_rooms = GameRoom.objects.filter(status__in=['waiting', 'starting']).order_by('-created_at')[:10]
    
    context = {
        'active_rooms': active_rooms
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
        
        messages.success(request, f'Room created with code: {room.code}')
        return redirect('quiz:room_detail', room_code=room.code)
    
    return render(request, 'quiz/create_room.html')

@login_required
def start_multiplayer_game(request, room_code):
    """Start multiplayer game (host only)"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check if user is host
    if room.host != request.user:
        messages.error(request, 'Only the host can start the game.')
        return redirect('quiz:room_detail', room_code=room_code)
    
    # Check if room is in waiting state
    if room.status != 'waiting':
        messages.error(request, 'Game already started or finished.')
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
            
            messages.success(request, f'Game started! {len(quiz_data["questions"])} questions generated.')
            return redirect('quiz:multiplayer_game', room_code=room_code)
        else:
            messages.error(request, 'Failed to generate questions. Please try again.')
            
    except Exception as e:
        print(f"Error generating questions: {e}")
        messages.error(request, f'Error generating questions: {str(e)}')
    
    return redirect('quiz:room_detail', room_code=room_code)

@login_required
def join_room(request):
    """Join an existing room"""
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        
        try:
            room = GameRoom.objects.get(code=room_code, status__in=['waiting', 'starting'])
            
            if room.is_full:
                messages.error(request, 'This room is full.')
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
            messages.error(request, 'Room not found or already finished.')
    
    return render(request, 'quiz/join_room.html')

@login_required
def room_detail(request, room_code):
    """Room detail page (waiting lobby)"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check if user is in room
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user)
    except GameParticipant.DoesNotExist:
        messages.error(request, 'You must join this room to access it.')
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
def multiplayer_game(request, room_code):
    """Multiplayer game interface"""
    room = get_object_or_404(GameRoom, code=room_code)
    
    # Check that user is participant
    try:
        participant = GameParticipant.objects.get(room=room, user=request.user, is_active=True)
    except GameParticipant.DoesNotExist:
        messages.error(request, 'You are not authorized to access this game.')
        return redirect('quiz:lobby')
    
    context = {
        'room': room,
        'participant': participant
    }
    
    return render(request, 'quiz/multiplayer_game.html', context)
@login_required
def quiz_start(request):
    mode = request.GET.get('mode', 'solo')
    topic = request.GET.get('topic', 'General Python')

    # Generate quiz with AI
    orchestrator = get_orchestrator(request.user)
    try:
        num_questions = int(request.GET.get('num_questions', 10))
        if num_questions < 1 or num_questions > 50:
            num_questions = 10
    except (TypeError, ValueError):
        num_questions = 10
        
    result = orchestrator.create_quiz(topic, num_questions)

    # Check that questions were actually returned
    quiz_data = result if result and "questions" in result and result["questions"] else None

    context = {
        'mode': mode,
        'topic': topic,
        'quiz_data': quiz_data,
        'error': None if quiz_data else "⚠️ No quiz could be generated."
    }
    return render(request, 'quiz/quiz_start.html', context)

@csrf_exempt
@login_required
def submit_quiz(request):
    """API endpoint to submit quiz results"""
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