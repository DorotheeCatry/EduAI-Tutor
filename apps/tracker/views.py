from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.agents.agent_orchestrator import get_orchestrator

@login_required
def dashboard(request):
    # Récupérer les données du dashboard via l'orchestrateur
    orchestrator = get_orchestrator(request.user)
    dashboard_data = orchestrator.get_user_dashboard()
    
    context = {
        'dashboard_data': dashboard_data if dashboard_data['success'] else None,
        'error': dashboard_data.get('error') if not dashboard_data['success'] else None
    }
    
    return render(request, 'tracker/dashboard.html', context)