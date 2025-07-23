from django.urls import path
from . import views

app_name = 'exercises'

urlpatterns = [
    path('', views.exercise_list, name='list'),
    path('<int:exercise_id>/', views.exercise_detail, name='detail'),
    path('<int:exercise_id>/submit/', views.submit_code, name='submit'),
    path('generate/', views.generate_exercise, name='generate'),
    path('progress/', views.user_progress, name='progress'),
]