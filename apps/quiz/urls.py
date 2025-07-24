from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('lobby/', views.quiz_lobby, name='lobby'),
    path('start/', views.quiz_start, name='start'),
    path('submit/', views.submit_quiz, name='submit'),
    path('result/', views.quiz_result, name='result'),
    
    # Multijoueur
    path('create/', views.create_room, name='create_room'),
    path('join/', views.join_room, name='join_room'),
    path('room/<str:room_code>/', views.room_detail, name='room_detail'),
    path('room/<str:room_code>/start/', views.start_multiplayer_game, name='start_multiplayer_game'),
    path('play/<str:room_code>/', views.multiplayer_game, name='multiplayer_game'),
    path('room/<str:room_code>/delete/', views.delete_room, name='delete_room'),
    
    # API temps réel
    path('api/room/<str:room_code>/status/', views.room_status_api, name='room_status_api'),
    path('api/room/<str:room_code>/quiz/', views.multiplayer_quiz_api, name='multiplayer_quiz_api'),
]