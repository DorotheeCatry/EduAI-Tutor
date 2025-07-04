from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
]