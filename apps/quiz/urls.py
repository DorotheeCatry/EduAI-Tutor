from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('lobby/', views.quiz_lobby, name='lobby'),
    path('start/', views.quiz_start, name='start'),
    path('result/', views.quiz_result, name='result'),
]