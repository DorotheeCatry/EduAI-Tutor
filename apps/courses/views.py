from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.agents.agent_orchestrator import get_orchestrator
from apps.quotas.service import QuotaDepasse
from apps.rag.module_loader import module_loader
from .models import Course
import re
import markdown2


# Extras markdown2 retenus pour le rendu des cours. Regroupés ici plutôt que
# répétés dans chaque vue : le rendu doit être identique pour un cours qui vient
# d'être généré et pour un cours rechargé depuis la base.
MARKDOWN_EXTRAS = [
    "fenced-code-blocks",   # blocs délimités par ```python
    "highlightjs-lang",     # ajoute la classe language-* attendue par Prism
    "tables",               # tableaux avec <thead> et <th>
    "break-on-newline",     # un saut de ligne simple devient un <br>
    "cuddled-lists",        # liste collée au paragraphe qui la précède
]


def render_markdown(content):
    """
    Convertit en HTML le Markdown produit par les agents, côté serveur.

    Compétence visée : C17 (épreuve E4) — interface de l'application web
    Compétence visée : C9 (épreuve E2) — sécurisation du service exposé

    Choix : conversion côté serveur avec markdown2 plutôt qu'un parseur en
    expressions régulières côté navigateur. Le parseur JavaScript précédent
    convertissait tout `**gras**` en titre `<h3>`, ce qui coupait les phrases
    en trois et produisait une hiérarchie de titres incohérente ; il plaçait
    aussi des blocs `<h2>` et `<ul>` à l'intérieur de `<p>`, et ne traitait
    pas les tableaux.

    Choix : safe_mode="escape" pour neutraliser le HTML brut. Le sujet saisi
    par l'apprenant alimente le prompt du Pedagogue ; sans échappement, une
    injection amenant le modèle à produire une balise <script> ou un attribut
    onerror s'exécuterait dans la page (XSS, OWASP A03).

    Choix : extra "tables" afin d'obtenir des <table> à en-têtes <th>, que les
    lecteurs d'écran peuvent restituer — critère d'accessibilité transversal
    des grilles (WCAG 2.1 AA / RGAA).

    Args:
        content: le Markdown renvoyé par l'agent, ou une chaîne vide.

    Returns:
        Le HTML correspondant, prêt à être inséré dans le template.
    """
    if not content:
        return ""

    return markdown2.markdown(
        content,
        extras=MARKDOWN_EXTRAS,
        safe_mode="escape",
    )


def test_template(request):
    """Vue de test pour vérifier les templates"""
    return render(request, 'test.html')

@login_required
def course_generator(request):
    """Main view for course generation"""
    
    print(f"DEBUG: course_generator called, method: {request.method}")
    print(f"DEBUG: user authenticated: {request.user.is_authenticated}")
    
    if request.method == 'POST':
        topic = request.POST.get('topic')
        module = request.POST.get('module', '')
        
        if not topic:
            messages.error(request, 'Please enter a topic to generate the course.')
            context = {'modules': module_loader.get_available_modules()}
            return render(request, 'courses/generate.html', context)
        
        # Use AI orchestrator to generate the course
        orchestrator = get_orchestrator(request.user)
        
        # Pass module context to orchestrator
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            if module_info:
                orchestrator.current_module = module_info['name']
        
        # Quota de génération (C13) : le refus n'est pas une panne, il a son
        # propre message et laisse l'apprenant sur le formulaire.
        try:
            result = orchestrator.generate_course(topic)
        except QuotaDepasse as depassement:
            messages.warning(request, depassement.message)
            context = {'modules': module_loader.get_available_modules()}
            return render(request, 'courses/generate.html', context)
        
        if result['success']:
            # Add XP for course generation
            xp_result = request.user.add_xp(15, 'course_generation')
            
            # Direct markdown processing
            content = result['content']
            
            # Extract title from markdown
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            course_title = title_match.group(1) if title_match else f"Course on {topic}"
            
            context = {
                'course': {
                    'title': course_title,
                    'topic': topic,
                    'module': module,
                    'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                    # Le Markdown brut reste dans le contexte : c'est lui qui est
                    # renvoyé au formulaire d'enregistrement, donc stocké en base.
                    'content': content,
                    # Le HTML n'est destiné qu'à l'affichage.
                    'content_html': render_markdown(content),
                    'sources': result['sources']
                },
                'modules': module_loader.get_available_modules(),
                'is_saved_course': False,
                'xp_result': xp_result
            }
        else:
            context = {
                'error': result.get('error', 'Error during course generation'),
                'topic': topic,
                'modules': module_loader.get_available_modules(),
                'is_saved_course': False
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    # GET request - show form
    context = {
        'modules': module_loader.get_available_modules()
    }
    print(f"DEBUG: Rendering template with context: {context}")
    return render(request, 'courses/generate.html', context)


@login_required
def save_course(request):
    """Save a generated course"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title', 'Untitled Course')
            topic = request.POST.get('topic', '')
            module = request.POST.get('module', 'general')
            content = request.POST.get('content', '')
            
            # Create course in database
            course = Course.objects.create(
                title=title,
                topic=topic,
                module=module,
                content=content,
                sources=[],
                created_by=request.user
            )
            
            # Add XP for saving a course
            request.user.add_xp(10, 'course_save')
            request.user.total_courses_completed += 1
            request.user.save()
            
            messages.success(request, f'✨ Course "{course.title}" saved successfully!')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as save_error:
            print(f"❌ Save error: {save_error}")
            messages.error(request, f'❌ Save error: {save_error}')
            return redirect('courses:generator')
    
    return redirect('courses:generator')



@login_required
def course_detail(request, course_id):
    """Display a saved course"""
    try:
        course = get_object_or_404(Course, id=course_id, created_by=request.user)
        course.increment_view_count()
        
        # Extract title from markdown if no explicit title
        content = course.content
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        course_title = title_match.group(1) if title_match else course.title
        
        context = {
            'course': {
                'title': course_title,
                'topic': course.topic,
                'module': course.module,
                'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == course.module), course.module.replace('_', ' ').title()) if course.module and course.module != 'general' else None,
                'content': course.content,
                'content_html': render_markdown(course.content),
                'sources': course.sources
            },
            'is_saved_course': True  # Flag pour identifier un cours sauvegardé
        }
    except Course.DoesNotExist:
        messages.error(request, '❌ Course not found.')
        return redirect('courses:generator')
    
    return render(request, 'courses/course_detail.html', context)

@require_http_methods(["GET"])
def get_modules_api(request):
    """API to get list of available modules"""
    modules = module_loader.get_available_modules()
    return JsonResponse({'modules': modules})

@require_http_methods(["GET"])
def get_sections_api(request, module_id):
    """API to get sections of a module"""
    sections = module_loader.get_module_sections(module_id)
    
    # Format sections for API
    formatted_sections = []
    for section_key, files in sections.items():
        formatted_sections.append({
            'id': section_key,
            'name': section_key.replace('_', ' ').replace(section_key.split('_')[0] + '_', '').title(),
            'files_count': len(files),
            'files': files
        })
    
    return JsonResponse({
        'module_id': module_id,
        'sections': formatted_sections
    })

@login_required
def my_courses(request):
    """List of user's saved courses"""
    courses = Course.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'courses': courses
    }
    return render(request, 'courses/my_courses.html', context)

@login_required
def delete_course(request, course_id):
    """Delete a saved course"""
    if request.method == 'POST':
        try:
            course = get_object_or_404(Course, id=course_id, created_by=request.user)
            course_title = course.title
            course.delete()
            messages.success(request, f'🗑️ Course "{course_title}" deleted successfully!')
        except Course.DoesNotExist:
            messages.error(request, '❌ Course not found.')
        except Exception as delete_error:
            messages.error(request, f'❌ Delete error: {delete_error}')
    
    return redirect('courses:my_courses')
