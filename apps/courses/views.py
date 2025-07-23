from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.agents.agent_orchestrator import get_orchestrator
from apps.rag.module_loader import module_loader
from .models import Course
import re

def test_template(request):
    """Vue de test pour vérifier les templates"""
    return render(request, 'test.html')

@login_required
def course_generator(request):
    """Vue principale pour la génération de cours"""
    
    print(f"DEBUG: course_generator called, method: {request.method}")
    print(f"DEBUG: user authenticated: {request.user.is_authenticated}")
    
    if request.method == 'POST':
        topic = request.POST.get('topic')
        module = request.POST.get('module', '')
        
        if not topic:
            messages.error(request, 'Veuillez saisir un sujet pour générer le cours.')
            context = {'modules': module_loader.get_available_modules()}
            return render(request, 'courses/generate.html', context)
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        
        # Passer le contexte du module à l'orchestrateur
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            if module_info:
                orchestrator.current_module = module_info['name']
        
        result = orchestrator.generate_course(topic)
        
        if result['success']:
            # Ajouter de l'XP pour la génération de cours
            xp_result = request.user.add_xp(15, 'course_generation')
            
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
                'modules': module_loader.get_available_modules(),
                'xp_result': xp_result
            }
        else:
            context = {
                'error': result.get('error', 'Erreur lors de la génération du cours'),
                'topic': topic,
                'modules': module_loader.get_available_modules()
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    # GET request - afficher le formulaire
    context = {
        'modules': module_loader.get_available_modules()
    }
    print(f"DEBUG: Rendering template with context: {context}")
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
            
            # Ajouter de l'XP pour sauvegarder un cours
            xp_result = request.user.add_xp(10, 'course_save')
            request.user.total_courses_completed += 1
            request.user.save()
            
            messages.success(request, f'✨ Cours "{course.title}" sauvegardé avec succès !')
            messages.success(request, f'Cours "{course.title}" sauvegardé avec succès !')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as save_error:
            print(f"❌ Erreur lors de la sauvegarde : {save_error}")
            messages.error(request, f'Erreur lors de la sauvegarde : {save_error}')
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
        
        # Nettoyer le contenu des emojis
        content = course.content
        
        # Supprimer tous les emojis du contenu
        import re
        # Pattern pour supprimer les emojis Unicode
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"  # emoticons
                                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                   u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                   u"\U00002702-\U000027B0"
                                   u"\U000024C2-\U0001F251"
                                   "]+", flags=re.UNICODE)
        content = emoji_pattern.sub('', content)
        
        # Supprimer les emojis textuels courants
        text_emojis = [
            '📖', '🎯', '🔍', '⚙️', '💡', '🚀', '📚', '📝', '🔁', '🧠', '🎓', '💻', '🌟', '✨',
            '🔥', '💪', '🎉', '👍', '👏', '🚀', '📊', '📈', '📉', '🔧', '⭐', '🏆', '🎪', '🎨',
            '🎵', '🎶', '🎸', '🎹', '🎺', '🎻', '🥁', '🎤', '🎧', '📻', '📺', '📱', '💻', '🖥️',
            '⌨️', '🖱️', '🖨️', '💾', '💿', '📀', '💽', '💻', '📱', '☎️', '📞', '📟', '📠', '📡'
        ]
        for emoji in text_emojis:
            content = content.replace(emoji, '')
        
        # Extraire le titre du markdown si présent
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        display_title = title_match.group(1) if title_match else course.title
        
        context = {
            'course': course,
            'generated_course': {
                'title': display_title,
                'topic': course.topic,
                'module': course.module,
                'module_name': course.module.replace('_', ' ').title() if course.module != 'general' else None,
                'content': content,
                'sources': course.sources
            }
        }
    except Course.DoesNotExist:
        messages.error(request, 'Cours non trouvé.')
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
        except Course.DoesNotExist:
            messages.error(request, 'Cours non trouvé.')
        except Exception as delete_error:
            messages.error(request, f'Erreur lors de la suppression : {delete_error}')
    
    return redirect('courses:my_courses')