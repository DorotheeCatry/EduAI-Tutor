from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from apps.agents.agent_orchestrator import get_orchestrator
from apps.rag.module_loader import module_loader
from .models import Course
import re

@login_required
def course_generator(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        module = request.POST.get('module', '')
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        
        # Passer le contexte du module à l'orchestrateur
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            if module_info:
                orchestrator.current_module = module_info['name']
        
        result = orchestrator.generate_course(topic)
        
        if result['success']:
            # Traitement direct du markdown
            content = result['content']
            
            # Extraire le titre du markdown
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            course_title = title_match.group(1) if title_match else f"Cours sur {topic}"
            
            context = {
                'generated_course': {
                    'title': course_title,
                    'topic': topic,
                    'module': module,
                    'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                    'content': content,
                    'sources': result['sources']
                },
                'modules': module_loader.get_available_modules()
            }
        else:
            context = {
                'error': result.get('error', 'Erreur lors de la génération du cours'),
                'topic': topic,
                'modules': module_loader.get_available_modules()
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    context = {
        'modules': module_loader.get_available_modules()
    }
    return render(request, 'courses/generate.html', context)






@login_required
def save_course(request):
    """Sauvegarde un cours généré"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            title = request.POST.get('title', 'Cours sans titre')
            topic = request.POST.get('topic', '')
            module = request.POST.get('module', 'general')
            content = request.POST.get('content', '')
            
            # Créer le cours en base
            course = Course.objects.create(
                title=title,
                topic=topic,
                module=module,
                content=content,
                sources=[],
                created_by=request.user
            )
            
            messages.success(request, f'✨ Cours "{course.title}" sauvegardé avec succès !')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as save_error:
            print(f"❌ Erreur lors de la sauvegarde : {save_error}")
            messages.error(request, f'❌ Erreur lors de la sauvegarde : {save_error}')
            return redirect('courses:generator')
    
    return redirect('courses:generator')


def customize_course(request):
    """API endpoint pour personnaliser un cours existant"""
    if request.method == 'POST':
        try:
            customization_type = request.POST.get('customization_type')
            customization_request = request.POST.get('customization_request')
            current_content = request.POST.get('current_content')
            topic = request.POST.get('topic')
            
            if not all([customization_type, customization_request, current_content]):
                return JsonResponse({
                    'success': False,
                    'error': 'Paramètres manquants'
                })
            
            # Utiliser l'orchestrateur IA pour personnaliser le cours
            orchestrator = get_orchestrator(request.user)
            
            # Créer un prompt de personnalisation
            customization_prompts = {
                'complexity': f"Rends ce cours plus complexe et technique. Ajoute des détails avancés, des concepts plus poussés. Demande spécifique: {customization_request}",
                'examples': f"Ajoute plus d'exemples pratiques et concrets à ce cours. Demande spécifique: {customization_request}",
                'exercises': f"Ajoute plus d'exercices pratiques et de défis à ce cours. Demande spécifique: {customization_request}",
                'simplify': f"Simplifie ce cours pour le rendre plus accessible. Explique plus clairement. Demande spécifique: {customization_request}"
            }
            
            prompt = customization_prompts.get(customization_type, customization_request)
            full_prompt = f"{prompt}\n\nCours actuel à modifier:\n{current_content}"
            
            result = orchestrator.answer_question(full_prompt)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'content': result['answer']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Erreur lors de la personnalisation')
                })
                
        except Exception as e:
            print(f"❌ Erreur lors de la personnalisation : {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
@login_required
def course_detail(request, course_id):
    """Affiche un cours sauvegardé"""
    try:
        course = get_object_or_404(Course, id=course_id, created_by=request.user)
        course.increment_view_count()
        
        context = {
            'course': course,
            'generated_course': {
                'title': course.title,
                'topic': course.topic,
                'module': course.module,
                'content': course.content,
                'sources': course.sources
            }
        }
    except Course.DoesNotExist:
        messages.error(request, '❌ Cours non trouvé.')
        return redirect('courses:generator')
    
    return render(request, 'courses/course_detail.html', context)

@require_http_methods(["GET"])
def get_modules_api(request):
    """API pour récupérer la liste des modules disponibles"""
    modules = module_loader.get_available_modules()
    return JsonResponse({'modules': modules})

@require_http_methods(["GET"])
def get_sections_api(request, module_id):
    """API pour récupérer les sections d'un module"""
    sections = module_loader.get_module_sections(module_id)
    
    # Formater les sections pour l'API
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
    """Liste des cours sauvegardés de l'utilisateur"""
    courses = Course.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'courses': courses
    }
    return render(request, 'courses/my_courses.html', context)

@login_required
def delete_course(request, course_id):
    """Supprime un cours sauvegardé"""
    if request.method == 'POST':
        try:
            course = get_object_or_404(Course, id=course_id, created_by=request.user)
            course_title = course.title
            course.delete()
            messages.success(request, f'🗑️ Cours "{course_title}" supprimé avec succès !')
        except Course.DoesNotExist:
            messages.error(request, '❌ Cours non trouvé.')
        except Exception as delete_error:
            messages.error(request, f'❌ Erreur lors de la suppression : {delete_error}')
    
    return redirect('courses:my_courses')