from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('generator/', views.course_generator, name='generator'),
    path('detail/<int:course_id>/', views.course_detail, name='detail'),
]