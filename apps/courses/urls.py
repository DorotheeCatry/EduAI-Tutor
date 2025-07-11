from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('generator/', views.course_generator, name='generator'),
    path('api/modules/', views.get_modules_api, name='modules_api'),
    path('api/sections/<str:module_id>/', views.get_sections_api, name='sections_api'),
    path('detail/<int:course_id>/', views.course_detail, name='detail'),
]