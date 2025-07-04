from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('search/', views.search_chat, name='search'),
    path('api/message/', views.send_message, name='send_message'),
]