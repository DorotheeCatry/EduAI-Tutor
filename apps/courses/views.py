from django.shortcuts import render
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.agents.orchestrator import get_orchestrator
from apps.rag.module_loader import module_loader
from .models import Course
import json
import re

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
            # Parser le JSON retourné par l'IA
            try:
                # Nettoyer le contenu pour extraire le JSON
                content = result['content']
                
                # Chercher le JSON dans la réponse
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    course_json = json.loads(json_match.group())
                    
                    # Traiter chaque section pour convertir le Markdown en HTML
                    processed_sections = []
                    for section in course_json.get('sections', []):
                        processed_content = process_markdown_content(section['content'])
                        processed_sections.append({
                            'type': section['type'],
                            'title': section['title'],
                            'content': processed_content
                        })
                    
                    context = {
                        'generated_course': {
                            'title': course_json.get('title', topic),
                            'topic': topic,
                            'module': module,
                            'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                            'difficulty': result['difficulty'],
                            'sections': processed_sections,
                            'sources': result['sources']
                        },
                        'modules': module_loader.get_available_modules()
                    }
                else:
                    raise ValueError("Format JSON non trouvé dans la réponse")
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"Erreur parsing JSON : {e}")
                # Fallback vers l'ancien système
                processed_content = process_markdown_content(result['content'])
                context = {
                    'generated_course': {
                        'title': topic,
                        'topic': topic,
                        'module': module,
                        'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                        'difficulty': result['difficulty'],
                        'sections': [{'title': 'Cours', 'content': processed_content, 'type': 'general'}],
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


def process_markdown_content(content):
    """Convertit le contenu Markdown en HTML avec coloration syntaxique"""
    
    # Convertir les titres
    content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
    content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
    
    # Convertir les blocs de code avec wrapper pour le bouton copy
    def replace_code_block(match):
        code_content = match.group(1)
        return f'''<div class="code-block-wrapper">
            <button class="copy-code-btn" onclick="copyCode(this)">Copier</button>
            <pre><code class="language-python">{code_content}</code></pre>
        </div>'''
    
    content = re.sub(r'```python\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    content = re.sub(r'```\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    
    # Convertir le texte en gras
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    
    # Convertir les listes à puces
    content = re.sub(r'^• (.*?)$', r'<li>\1</li>', content, flags=re.MULTILINE)
    
    # Grouper les listes consécutives
    lines = content.split('\n')
    processed_lines = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('<li>'):
            if not in_list:
                processed_lines.append('<ul>')
                in_list = True
            processed_lines.append(line)
        else:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            processed_lines.append(line)
    
    if in_list:
        processed_lines.append('</ul>')
    
    content = '\n'.join(processed_lines)
    
    # Convertir les paragraphes
    paragraphs = content.split('\n\n')
    processed_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if para and not para.startswith('<') and not para.endswith('>'):
            processed_paragraphs.append(f'<p>{para}</p>')
        else:
            processed_paragraphs.append(para)
    
    return '\n'.join(processed_paragraphs)


@login_required
def save_course(request):
    """Sauvegarde un cours généré"""
    if request.method == 'POST':
        try:
            course_data = json.loads(request.POST.get('course_data', '{}'))
            
            # Créer le cours en base
            course = Course.objects.create(
                title=course_data.get('title', 'Cours sans titre'),
                topic=course_data.get('topic', ''),
                module=course_data.get('module', 'general'),
                difficulty=course_data.get('difficulty', 'intermediate'),
                content=json.dumps(course_data.get('sections', [])),
                sources=course_data.get('sources', []),
                created_by=request.user
            )
            
            messages.success(request, f'Cours "{course.title}" sauvegardé avec succès !')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la sauvegarde : {e}')
            return redirect('courses:generator')
    
    return redirect('courses:generator')


@login_required
def course_detail(request, course_id):
    """Affiche un cours sauvegardé"""
    try:
        course = Course.objects.get(id=course_id, created_by=request.user)
        course.increment_view_count()
        
        # Parser le contenu JSON
        try:
            sections = json.loads(course.content)
        except:
            sections = [{'title': 'Contenu', 'content': course.content, 'type': 'general'}]
        
        context = {
            'course': course,
            'generated_course': {
                'title': course.title,
                'topic': course.topic,
                'module': course.module,
                'difficulty': course.difficulty,
                'sections': sections,
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