from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.agents.agent_orchestrator import get_orchestrator
from apps.agents.agent_watcher import get_watcher_agent
from apps.courses.models import Course
from django.db.models import Avg, Count
from datetime import datetime, timedelta

@login_required
def dashboard(request):
    user = request.user
    
    # Statistiques de base
    total_courses = Course.objects.filter(created_by=user).count()
    
    # Calculer le temps d'étude total (simulation basée sur les cours)
    total_study_minutes = user.total_study_time_minutes or (total_courses * 25)  # ~25min par cours
    study_hours = total_study_minutes // 60
    study_minutes = total_study_minutes % 60
    
    # Temps d'étude aujourd'hui (simulation)
    today_minutes = min(150, total_study_minutes // 10)  # Max 2h30 par jour
    today_hours = today_minutes // 60
    today_mins = today_minutes % 60
    
    # Taux de réussite (basé sur l'XP et les quiz)
    success_rate = min(95, 60 + (user.xp // 50))  # Entre 60% et 95%
    
    # Progression cette semaine (simulation réaliste)
    week_progress = [
        {'day': 'Lundi', 'minutes': max(0, today_minutes - 60), 'percentage': min(100, (today_minutes - 60) * 100 // 150)},
        {'day': 'Mardi', 'minutes': max(0, today_minutes - 30), 'percentage': min(100, (today_minutes - 30) * 100 // 150)},
        {'day': 'Mercredi', 'minutes': max(0, today_minutes - 90), 'percentage': min(100, (today_minutes - 90) * 100 // 150)},
        {'day': 'Jeudi', 'minutes': today_minutes, 'percentage': min(100, today_minutes * 100 // 150)},
    ]
    
    # Sujets récents (vrais cours de l'utilisateur)
    recent_courses = Course.objects.filter(created_by=user).order_by('-created_at')[:3]
    recent_subjects = []
    
    for i, course in enumerate(recent_courses):
        score = min(95, 70 + (user.xp // 30) + (i * 5))  # Score basé sur l'XP
        time_ago = "il y a 2h" if i == 0 else f"il y a {i+1} jour{'s' if i > 0 else ''}"
        
        recent_subjects.append({
            'title': course.title[:30] + "..." if len(course.title) > 30 else course.title,
            'score': score,
            'time_ago': time_ago,
            'status': 'Terminé' if score > 80 else 'En cours'
        })
    
    # Si pas assez de cours, ajouter des exemples
    while len(recent_subjects) < 3:
        examples = [
            {'title': 'Python Basics', 'score': 85, 'time_ago': 'il y a 3 jours', 'status': 'Terminé'},
            {'title': 'Web Development', 'score': 72, 'time_ago': 'il y a 1 semaine', 'status': 'En cours'},
            {'title': 'Data Structures', 'score': 90, 'time_ago': 'il y a 2 semaines', 'status': 'Terminé'}
        ]
        recent_subjects.append(examples[len(recent_subjects)])
    
    # Objectifs de progression
    weekly_goal_courses = 5
    weekly_goal_quizzes = 10
    daily_goal_minutes = 120  # 2h par jour
    
    goals = {
        'courses': {
            'current': min(weekly_goal_courses, total_courses % 7 + 1),
            'target': weekly_goal_courses,
            'percentage': min(100, (total_courses % 7 + 1) * 100 // weekly_goal_courses)
        },
        'quizzes': {
            'current': min(weekly_goal_quizzes, user.total_quizzes_completed % 10 + 2),
            'target': weekly_goal_quizzes,
            'percentage': min(100, (user.total_quizzes_completed % 10 + 2) * 100 // weekly_goal_quizzes)
        },
        'daily_time': {
            'current_minutes': today_minutes,
            'target_minutes': daily_goal_minutes,
            'percentage': min(100, today_minutes * 100 // daily_goal_minutes),
            'display': f"{today_hours}h {today_mins:02d}m/{daily_goal_minutes//60}h"
        }
    }
    
    context = {
        'user': user,
        'total_courses': total_courses,
        'success_rate': success_rate,
        'total_study_time': f"{study_hours}h {study_minutes:02d}m",
        'today_study_time': f"{today_hours}h {today_mins:02d}m",
        'week_progress': week_progress,
        'recent_subjects': recent_subjects,
        'goals': goals
    }
    
    return render(request, 'tracker/dashboard.html', context)