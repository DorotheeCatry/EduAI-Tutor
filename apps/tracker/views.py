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
    
    # Basic statistics
    total_courses = Course.objects.filter(created_by=user).count()
    
    # Calculate total study time (simulation based on courses)
    total_study_minutes = user.total_study_time_minutes or (total_courses * 25)  # ~25min per course
    study_hours = total_study_minutes // 60
    study_minutes = total_study_minutes % 60
    
    # Study time today (simulation)
    today_minutes = min(150, total_study_minutes // 10)  # Max 2h30 per day
    today_hours = today_minutes // 60
    today_mins = today_minutes % 60
    
    # Success rate (based on XP and quizzes)
    success_rate = min(95, 60 + (user.xp // 50))  # Between 60% and 95%
    
    # This week's progress (realistic simulation)
    week_progress = [
        {'day': 'Monday', 'minutes': max(0, today_minutes - 60), 'percentage': min(100, (today_minutes - 60) * 100 // 150)},
        {'day': 'Tuesday', 'minutes': max(0, today_minutes - 30), 'percentage': min(100, (today_minutes - 30) * 100 // 150)},
        {'day': 'Wednesday', 'minutes': max(0, today_minutes - 90), 'percentage': min(100, (today_minutes - 90) * 100 // 150)},
        {'day': 'Thursday', 'minutes': today_minutes, 'percentage': min(100, today_minutes * 100 // 150)},
    ]
    
    # Recent topics (real user courses)
    recent_courses = Course.objects.filter(created_by=user).order_by('-created_at')[:3]
    recent_subjects = []
    
    for i, course in enumerate(recent_courses):
        score = min(95, 70 + (user.xp // 30) + (i * 5))  # Score based on XP
        time_ago = "2h ago" if i == 0 else f"{i+1} day{'s' if i > 0 else ''} ago"
        
        recent_subjects.append({
            'title': course.title[:30] + "..." if len(course.title) > 30 else course.title,
            'score': score,
            'time_ago': time_ago,
            'status': 'Completed' if score > 80 else 'In progress'
        })
    
    # If not enough courses, add examples
    while len(recent_subjects) < 3:
        examples = [
            {'title': 'Python Basics', 'score': 85, 'time_ago': '3 days ago', 'status': 'Completed'},
            {'title': 'Web Development', 'score': 72, 'time_ago': '1 week ago', 'status': 'In progress'},
            {'title': 'Data Structures', 'score': 90, 'time_ago': '2 weeks ago', 'status': 'Completed'}
        ]
        recent_subjects.append(examples[len(recent_subjects)])
    
    # Progress goals
    weekly_goal_courses = 5
    weekly_goal_quizzes = 10
    daily_goal_minutes = 120  # 2h per day
    
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