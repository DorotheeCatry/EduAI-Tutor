from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from apps.agents.orchestrator import get_orchestrator
from apps.rag.module_loader import module_loader
import json

@login_required
def course_generator(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        difficulty = request.POST.get('difficulty')
        module = request.POST.get('module', '')
        
        # Construire le sujet complet
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            module_name = module_info['name'] if module_info else module
            full_topic = f"{topic}"
        else:
            full_topic = topic
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        # Passer le contexte du module à l'orchestrateur
        if module and module != 'general':
            orchestrator.current_module = module_info['name'] if module_info else module
        
        result = orchestrator.generate_course(full_topic, difficulty)
        
        if result['success']:
            # Convertir le contenu Markdown en HTML pour un meilleur rendu
            import re
            content = result['content']
            
            # Convertir les titres Markdown en HTML
            content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
            content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
            
            # Convertir les blocs de code
            content = re.sub(r'```python\n(.*?)\n```', r'<pre><code>\1</code></pre>', content, flags=re.DOTALL)
            content = re.sub(r'```\n(.*?)\n```', r'<pre><code>\1</code></pre>', content, flags=re.DOTALL)
            
            # Convertir les listes à puces
            content = re.sub(r'^• (.*?)$', r'<li>\1</li>', content, flags=re.MULTILINE)
            content = re.sub(r'(<li>.*?</li>)', r'<ul>\1</ul>', content, flags=re.DOTALL)
            content = re.sub(r'</ul>\s*<ul>', '', content)  # Fusionner les listes consécutives
            
            # Convertir les paragraphes
            content = re.sub(r'\n\n', '</p><p>', content)
            content = f'<p>{content}</p>'
            
            # Nettoyer les balises vides
            content = re.sub(r'<p></p>', '', content)
            content = re.sub(r'<p>\s*</p>', '', content)
            
            context = {
                'generated_course': {
                    'topic': topic,
                    'module': module,
                    'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                    'difficulty': result['difficulty'],
                    'content': content,
                    'sources': result['sources']
                },
                'modules': module_loader.get_available_modules()
            }
        else:
            context = {
                'error': result.get('error', 'Erreur lors de la génération du cours'),
                'topic': topic,
                'difficulty': difficulty,
                'modules': module_loader.get_available_modules()
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    context = {
        'modules': module_loader.get_available_modules()
    }
    return render(request, 'courses/generate.html', context)


@login_required
def course_detail(request, course_id):
    # Logique pour afficher un cours spécifique
    context = {
        'course': {
            'id': course_id,
            'title': 'Cours exemple',
            'content': 'Contenu du cours...'
        }
    }
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