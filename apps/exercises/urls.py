from django.urls import path
from . import views

app_name = 'exercises'

urlpatterns = [
    # Le carnet : plusieurs exercices dans une page, et son export Jupyter.
    path('carnet/', views.carnet, name='carnet'),
    path('carnet/telecharger/', views.carnet_ipynb, name='carnet_ipynb'),
    path('carnet/executer/', views.carnet_executer, name='carnet_executer'),
    path('', views.exercise_list, name='list'),
    path('<int:exercise_id>/', views.exercise_detail, name='detail'),
    path('<int:exercise_id>/submit/', views.submit_code, name='submit'),
    path('generate/', views.generate_exercise, name='generate'),
    path('generate-from-course/', views.generate_exercise_from_course, name='generate_from_course'),
    path('<int:exercise_id>/delete/', views.delete_exercise, name='delete'),
    path('progress/', views.user_progress, name='progress'),
]
