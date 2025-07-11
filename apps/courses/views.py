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
        
        # Utiliser l'orchestrateur IA pour générer le cours
        orchestrator = get_orchestrator(request.user)
        
        # Passer le contexte du module à l'orchestrateur
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            if module_info:
                orchestrator.current_module = module_info['name']
        
        result = orchestrator.generate_course(topic, difficulty)
        
        if result['success']:
            try:
                # Nettoyer et parser le JSON retourné par l'IA
                content = result['content']
                print(f"🔍 Contenu brut reçu: {content[:200]}...")
                
                # Extraire le JSON de la réponse
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    print(f"🔍 JSON extrait: {json_str[:200]}...")
                    
                    course_data = json.loads(json_str)
                    print(f"🔍 Données parsées: {course_data.keys()}")
                    
                    # Traiter chaque section
                    processed_sections = []
                    for section in course_data.get('sections', []):
                        processed_content = process_section_content(section['content'])
                        processed_sections.append({
                            'type': section['type'],
                            'title': section['title'],
                            'content': processed_content
                        })
                    
                    context = {
                        'generated_course': {
                            'title': course_data.get('title', topic),
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
                    print("❌ Aucun JSON trouvé dans la réponse")
                    raise ValueError("Format JSON non trouvé dans la réponse")
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"❌ Erreur parsing JSON : {e}")
                # Fallback vers l'ancien système
                processed_content = process_fallback_content(result['content'])
                context = {
                    'generated_course': {
                        'title': topic,
                        'topic': topic,
                        'module': module,
                        'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                        'difficulty': result['difficulty'],
                        'sections': [{'title': '📖 Cours', 'content': processed_content, 'type': 'general'}],
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


def process_section_content(content):
    """Convertit le contenu d'une section en HTML formaté"""
    
    # Convertir les blocs de code Python
    def replace_code_block(match):
        code_content = match.group(1).strip()
        return f'''
        <div class="code-block-container">
            <div class="code-header">
                <span class="code-language">Python</span>
                <button class="copy-btn" onclick="copyCode(this)">
                    <i data-lucide="copy" class="w-4 h-4"></i>
                    Copier
                </button>
            </div>
            <pre class="code-block"><code class="language-python">{code_content}</code></pre>
        </div>
        '''
    
    # Remplacer les blocs de code
    content = re.sub(r'```python\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    content = re.sub(r'```\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    
    # Convertir les mots en gras avec couleur
    content = re.sub(r'\*\*(.*?)\*\*', r'<span class="keyword-highlight">\1</span>', content)
    
    # Convertir les listes à puces
    content = re.sub(r'^• (.*?)$', r'<li class="bullet-item">\1</li>', content, flags=re.MULTILINE)
    
    # Grouper les listes
    lines = content.split('\n')
    processed_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('<li class="bullet-item">'):
            if not in_list:
                processed_lines.append('<ul class="custom-list">')
                in_list = True
            processed_lines.append(line)
        else:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            if line:
                processed_lines.append(f'<p class="content-paragraph">{line}</p>')
    
    if in_list:
        processed_lines.append('</ul>')
    
    return '\n'.join(processed_lines)


def process_fallback_content(content):
    """Traite le contenu en cas d'échec du parsing JSON"""
    
    # Convertir les titres avec emojis
    content = re.sub(r'^## (.*?)$', r'<h2 class="section-title">\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.*?)$', r'<h1 class="main-title">\1</h1>', content, flags=re.MULTILINE)
    
    # Traiter le reste comme une section normale
    return process_section_content(content)


@login_required
def save_course(request):
    """Sauvegarde un cours généré"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            title = request.POST.get('title', 'Cours sans titre')
            topic = request.POST.get('topic', '')
            module = request.POST.get('module', 'general')
            difficulty = request.POST.get('difficulty', 'intermediate')
            sections_data = request.POST.get('sections_data', '[]')
            sources = request.POST.get('sources', '[]')
            
            # Parser les données JSON
            try:
                sections = json.loads(sections_data)
                sources_list = json.loads(sources)
            except json.JSONDecodeError:
                sections = []
                sources_list = []
            
            # Créer le cours en base
            course = Course.objects.create(
                title=title,
                topic=topic,
                module=module,
                difficulty=difficulty,
                content=json.dumps(sections),
                sources=sources_list,
                created_by=request.user
            )
            
            messages.success(request, f'Cours "{course.title}" sauvegardé avec succès !')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde : {e}")
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

@login_required
def my_courses(request):
    """Liste des cours sauvegardés de l'utilisateur"""
    courses = Course.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'courses': courses
    }
    return render(request, 'courses/my_courses.html', context)