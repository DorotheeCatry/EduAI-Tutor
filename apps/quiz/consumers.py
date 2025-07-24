import json
import asyncio
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import GameRoom, GameParticipant, GameQuestion, GameAnswer
from apps.agents.agent_orchestrator import get_orchestrator

User = get_user_model()

class QuizConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'quiz_{self.room_code}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Rejoindre le groupe de la salle
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Ajouter le joueur à la salle
        # Add player to room
        await self.add_player_to_room()
        
        # Send current room state
        await self.send_room_state()

    async def disconnect(self, close_code):
        # Remove player from room
        await self.remove_player_from_room()
        
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'start_game':
            await self.start_game()
        elif message_type == 'submit_answer':
            await self.submit_answer(data)
        elif message_type == 'next_question':
            await self.next_question()

    @database_sync_to_async
    def add_player_to_room(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            participant, created = GameParticipant.objects.get_or_create(
                room=room,
                user=self.user,
                defaults={'is_active': True}
            )
            if not created:
                participant.is_active = True
                participant.save()
            return room
        except GameRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def remove_player_from_room(self):
        try:
            participant = GameParticipant.objects.get(
                room__code=self.room_code,
                user=self.user
            )
            participant.is_active = False
            participant.save()
        except GameParticipant.DoesNotExist:
            pass

    @database_sync_to_async
    def get_room_state(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            participants = list(room.participants.filter(is_active=True).values(
                'user__username', 'score', 'correct_answers'
            ))
            return {
                'room': {
                    'code': room.code,
                    'topic': room.topic,
                    'status': room.status,
                    'current_question': room.current_question,
                    'num_questions': room.num_questions,
                    'host': room.host.username,
                },
                'participants': participants
            }
        except GameRoom.DoesNotExist:
            return None

    async def send_room_state(self):
        room_state = await self.get_room_state()
        if room_state:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'room_update',
                    'data': room_state
                }
            )

    @database_sync_to_async
    def can_start_game(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            return (room.host == self.user and 
                    room.status == 'waiting' and 
                    room.player_count >= 1)
        except GameRoom.DoesNotExist:
            return False

    async def start_game(self):
        if not await self.can_start_game():
            return
        
        # Générer les questions
        # Generate questions
        await self.generate_questions()
        
        # Change room status
        await self.update_room_status('starting')
        
        # Send start signal
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_starting',
                'countdown': 5
            }
        )
        
        # Wait 5 seconds then start
        await asyncio.sleep(5)
        await self.send_first_question()

    @database_sync_to_async
    def generate_questions(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            
            # Use AI orchestrator to generate quiz
            orchestrator = get_orchestrator()
            quiz_data = orchestrator.create_quiz(room.topic, room.num_questions)
            
            # Save questions
            for i, question_data in enumerate(quiz_data['questions']):
                GameQuestion.objects.create(
                    room=room,
                    question_number=i + 1,
                    question_text=question_data['question'],
                    options=question_data['options'],
                    correct_answer=question_data['correct_answer'],
                    explanation=question_data.get('explanation', '')
                )
            
            return True
        except Exception as e:
            print(f"Question generation error: {e}")
            return False

    @database_sync_to_async
    def update_room_status(self, status):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            room.status = status
            if status == 'in_progress':
                room.started_at = datetime.now()
                room.current_question = 1
                room.question_start_time = datetime.now()
            elif status == 'finished':
                room.finished_at = datetime.now()
            room.save()
        except GameRoom.DoesNotExist:
            pass

    async def send_first_question(self):
        await self.update_room_status('in_progress')
        question_data = await self.get_current_question()
        
        if question_data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'new_question',
                    'question': question_data,
                    'time_limit': 60
                }
            )

    @database_sync_to_async
    def get_current_question(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            question = room.questions.get(question_number=room.current_question)
            return {
                'number': question.question_number,
                'total': room.num_questions,
                'text': question.question_text,
                'options': question.options
            }
        except (GameRoom.DoesNotExist, GameQuestion.DoesNotExist):
            return None

    async def submit_answer(self, data):
        answer_index = data.get('answer')
        response_time = data.get('response_time', 60)
        
        # Sauvegarder la réponse
        # Save answer
        points = await self.save_answer(answer_index, response_time)
        
        # Send confirmation to player
        await self.send(text_data=json.dumps({
            'type': 'answer_submitted',
            'points': points
        }))
        
        # Check if all players answered
        if await self.all_players_answered():
            await self.show_results()

    @database_sync_to_async
    def save_answer(self, answer_index, response_time):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            participant = GameParticipant.objects.get(room=room, user=self.user)
            question = GameQuestion.objects.get(room=room, question_number=room.current_question)
            
            # Create answer
            game_answer = GameAnswer.objects.create(
                participant=participant,
                question=question,
                selected_answer=answer_index,
                response_time=response_time
            )
            
            # Calculate points
            points = game_answer.calculate_points()
            game_answer.save()
            
            # Update participant score
            participant.score += points
            if game_answer.is_correct:
                participant.correct_answers += 1
            participant.save()
            
            return points
        except Exception as e:
            print(f"Answer save error: {e}")
            return 0

    @database_sync_to_async
    def all_players_answered(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            active_players = room.participants.filter(is_active=True).count()
            answered_players = GameAnswer.objects.filter(
                question__room=room,
                question__question_number=room.current_question
            ).count()
            return answered_players >= active_players
        except GameRoom.DoesNotExist:
            return True

    async def show_results(self):
        results = await self.get_question_results()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'question_results',
                'results': results
            }
        )
        
        # Wait 5 seconds then move to next question
        await asyncio.sleep(5)
        await self.next_question()

    @database_sync_to_async
    def get_question_results(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            question = GameQuestion.objects.get(room=room, question_number=room.current_question)
            
            # Answer statistics
            answers = GameAnswer.objects.filter(question=question)
            stats = [0, 0, 0, 0]  # Compteur pour chaque option
            
            for answer in answers:
                stats[answer.selected_answer] += 1
            
            # Current leaderboard
            leaderboard = list(room.participants.filter(is_active=True).order_by('-score').values(
                'user__username', 'score', 'correct_answers'
            ))
            
            return {
                'correct_answer': question.correct_answer,
                'explanation': question.explanation,
                'stats': stats,
                'leaderboard': leaderboard
            }
        except Exception as e:
            print(f"Results error: {e}")
            return {}

    async def next_question(self):
        has_next = await self.move_to_next_question()
        
        if has_next:
            question_data = await self.get_current_question()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'new_question',
                    'question': question_data,
                    'time_limit': 60
                }
            )
        else:
            await self.end_game()

    @database_sync_to_async
    def move_to_next_question(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            room.current_question += 1
            room.question_start_time = datetime.now()
            room.save()
            return room.current_question <= room.num_questions
        except GameRoom.DoesNotExist:
            return False

    async def end_game(self):
        await self.update_room_status('finished')
        final_results = await self.get_final_results()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_finished',
                'results': final_results
            }
        )

    @database_sync_to_async
    def get_final_results(self):
        try:
            room = GameRoom.objects.get(code=self.room_code)
            participants = room.participants.filter(is_active=True).order_by('-score')
            
            results = []
            for i, participant in enumerate(participants):
                # Add XP bonus based on ranking
                bonus_xp = max(50 - (i * 10), 10)  # 50 XP for 1st, 40 for 2nd, etc.
                participant.user.add_xp(bonus_xp, 'multiplayer_quiz')
                
                results.append({
                    'rank': i + 1,
                    'username': participant.user.username,
                    'score': participant.score,
                    'correct_answers': participant.correct_answers,
                    'total_questions': room.num_questions,
                    'accuracy': round((participant.correct_answers / room.num_questions) * 100, 1),
                    'bonus_xp': bonus_xp
                })
            
            return results
        except Exception as e:
            print(f"Final results error: {e}")
            return []

    # Handlers for group messages
    async def room_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'room_update',
            'data': event['data']
        }))

    async def game_starting(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_starting',
            'countdown': event['countdown']
        }))

    async def new_question(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_question',
            'question': event['question'],
            'time_limit': event['time_limit']
        }))

    async def question_results(self, event):
        await self.send(text_data=json.dumps({
            'type': 'question_results',
            'results': event['results']
        }))

    async def game_finished(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_finished',
            'results': event['results']
        }))