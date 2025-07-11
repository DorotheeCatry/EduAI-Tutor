from django.shortcuts import render, redirect, get_object_or_404
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
                print(f"🔍 Contenu brut reçu: {content[:500]}...")
                
                # Extraire le JSON de la réponse avec regex plus robuste
                json_patterns = [
                    r'\{[^{}]*"title"[^{}]*"sections"[^{}]*\[[^\]]*\][^{}]*\}',  # Pattern simple
                    r'\{.*?"title".*?"sections".*?\[.*?\].*?\}',  # Pattern avec lazy matching
                    r'\{(?:[^{}]|{[^{}]*})*\}',  # Pattern récursif
                ]
                
                course_data = None
                for pattern in json_patterns:
                    json_match = re.search(pattern, content, re.DOTALL)
                    if json_match:
                        try:
                            json_str = json_match.group()
                            print(f"🔍 JSON extrait avec pattern: {json_str[:200]}...")
                            course_data = json.loads(json_str)
                            print(f"✅ JSON parsé avec succès: {list(course_data.keys())}")
                            break
                        except json.JSONDecodeError as e:
                            print(f"❌ Erreur parsing avec ce pattern: {e}")
                            continue
                
                if course_data and 'sections' in course_data:
                    # Traiter chaque section
                    processed_sections = []
                    for section in course_data.get('sections', []):
                        processed_content = process_section_content(section.get('content', ''))
                        processed_sections.append({
                            'type': section.get('type', 'general'),
                            'title': section.get('title', 'Section'),
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
                    print("❌ Aucun JSON valide trouvé, utilisation du fallback")
                    raise ValueError("Format JSON non trouvé dans la réponse")
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"❌ Erreur parsing JSON : {e}")
                # Fallback vers l'ancien système avec contenu structuré
                processed_content = process_fallback_content(result['content'])
                context = {
                    'generated_course': {
                        'title': topic.title(),
                        'topic': topic,
                        'module': module,
                        'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                        'difficulty': result['difficulty'],
                        'sections': [
                            {
                                'title': '📖 Introduction', 
                                'content': f"<p>Dans ce cours, nous allons explorer <strong>{topic}</strong> en détail.</p>",
                                'type': 'introduction'
                            },
                            {
                                'title': '🔍 Contenu du Cours', 
                                'content': processed_content, 
                                'type': 'content'
                            }
                        ],
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
    """Convertit le contenu d'une section en HTML formaté magnifiquement"""
    
    # Convertir les blocs de code Python avec header magnifique
    def replace_code_block(match):
        code_content = match.group(1).strip()
        return f'''
        <div class="code-container">
            <div class="code-header">
                <div class="code-language-badge">
                    <i class="code-icon">🐍</i>
                    <span>Python</span>
                </div>
                <button class="copy-button" onclick="copyCode(this)">
                    <i data-lucide="copy" class="w-4 h-4"></i>
                    <span>Copier</span>
                </button>
            </div>
            <div class="code-content">
                <pre><code class="language-python">{code_content}</code></pre>
            </div>
        </div>
        '''
    
    # Remplacer les blocs de code
    content = re.sub(r'```python\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    content = re.sub(r'```\n(.*?)\n```', replace_code_block, content, flags=re.DOTALL)
    
    # Convertir les mots en gras avec style magnifique
    content = re.sub(r'\*\*(.*?)\*\*', r'<span class="keyword-highlight">\1</span>', content)
    
    # Convertir les listes à puces avec style moderne
    content = re.sub(r'^• (.*?)$', r'<li class="modern-list-item">\1</li>', content, flags=re.MULTILINE)
    
    # Grouper les listes avec container moderne
    lines = content.split('\n')
    processed_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('<li class="modern-list-item">'):
            if not in_list:
                processed_lines.append('<ul class="modern-list">')
                in_list = True
            processed_lines.append(line)
        else:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            if line:
                processed_lines.append(f'<p class="content-text">{line}</p>')
    
    if in_list:
        processed_lines.append('</ul>')
    
    return '\n'.join(processed_lines)


def process_fallback_content(content):
    """Traite le contenu en cas d'échec du parsing JSON avec style moderne"""
    
    # Convertir les titres avec style moderne
    content = re.sub(r'^## (.*?)$', r'<h2 class="section-subtitle">\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.*?)$', r'<h1 class="section-title">\1</h1>', content, flags=re.MULTILINE)
    
    # Traiter le reste comme une section normale
    return process_section_content(content)


@login_required
def save_course(request):
    """Sauvegarde un cours généré avec style"""
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
                sections = json.loads(sections_data) if sections_data != '[]' else []
                sources_list = json.loads(sources) if sources != '[]' else []
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
            
            messages.success(request, f'✨ Cours "{course.title}" sauvegardé avec succès !')
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde : {e}")
            messages.error(request, f'❌ Erreur lors de la sauvegarde : {e}')
            return redirect('courses:generator')
    
    return redirect('courses:generator')


@login_required
def course_detail(request, course_id):
    """Affiche un cours sauvegardé avec style magnifique"""
    try:
        course = get_object_or_404(Course, id=course_id, created_by=request.user)
        course.increment_view_count()
        
        # Parser le contenu JSON
        try:
            sections = json.loads(course.content)
        except:
            sections = [{'title': '📖 Contenu', 'content': course.content, 'type': 'general'}]
        
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
    """Liste des cours sauvegardés de l'utilisateur avec style moderne"""
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
        except Exception as e:
            messages.error(request, f'❌ Erreur lors de la suppression : {e}')
    
    return redirect('courses:my_courses')