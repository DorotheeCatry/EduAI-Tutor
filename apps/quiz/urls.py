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
    path('play/<str:room_code>/', views.multiplayer_game, name='multiplayer_game'),
]