from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('test/', views.test_template, name='test'),
    path('generator/', views.course_generator, name='generator'),
    path('save/', views.save_course, name='save'),
    path('customize/', views.customize_course, name='customize'),
    path('api/modules/', views.get_modules_api, name='modules_api'),
    path('api/sections/<str:module_id>/', views.get_sections_api, name='sections_api'),
    path('detail/<int:course_id>/', views.course_detail, name='detail'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('delete/<int:course_id>/', views.delete_course, name='delete'),
]