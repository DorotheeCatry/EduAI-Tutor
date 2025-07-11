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
import unicodedata

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
                print(f"🔍 Contenu brut reçu: {str(content)[:500]}...")
                
                # Fonction pour nettoyer le JSON des caractères de contrôle
                def clean_json_string(json_str):
                    """Nettoie le JSON des caractères de contrôle invalides"""
                    if isinstance(json_str, dict):
                        return json_str
                    
                    # Convertir en string si nécessaire
                    json_str = str(json_str)
                    
                    # Extraire le JSON des blocs markdown si présent
                    if '```' in json_str:
                        json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', json_str, re.DOTALL)
                        if json_blocks:
                            json_str = json_blocks[0].strip()
                            print(f"🔍 JSON extrait des blocs markdown")
                    
                    # Supprimer les caractères de contrôle invalides
                    # Garder seulement \n, \r, \t qui sont valides en JSON
                    cleaned = ""
                    for char in json_str:
                        if ord(char) < 32:  # Caractères de contrôle
                            if char in ['\n', '\r', '\t']:
                                cleaned += char
                            else:
                                cleaned += ' '  # Remplacer par un espace
                        else:
                            cleaned += char
                    
                    # Nettoyer les guillemets problématiques
                    cleaned = cleaned.replace('"', '"').replace('"', '"')
                    cleaned = cleaned.replace(''', "'").replace(''', "'")
                    
                    # Supprimer les caractères Unicode problématiques
                    try:
                        cleaned = unicodedata.normalize('NFKD', cleaned)
                    except Exception as normalize_error:
                        print(f"⚠️ Erreur normalisation Unicode: {normalize_error}")
                    
                    return cleaned
                
                # Essayer de parser le JSON directement
                course_data = None
                try:
                    # Si c'est déjà un dict (cas où l'IA retourne directement du JSON)
                    if isinstance(content, dict):
                        course_data = content
                        print("✅ Contenu déjà en format dict")
                    else:
                        # Nettoyer le contenu avant parsing
                        cleaned_content = clean_json_string(content)
                        print(f"🧹 Contenu nettoyé: {cleaned_content[:200]}...")
                        
                        # Essayer de parser comme JSON
                        course_data = json.loads(cleaned_content)
                        print("✅ JSON parsé directement")
                        
                except (json.JSONDecodeError, TypeError) as direct_parse_error:
                    print(f"❌ Parsing JSON direct échoué: {direct_parse_error}, tentative d'extraction...")
                    
                    # Extraire le JSON avec regex plus robuste
                    try:
                        cleaned_content = clean_json_string(content)
                        json_patterns = [
                            r'\{[^{}]*"title"[^{}]*"sections"[^{}]*\[[^\]]*\][^{}]*\}',
                            r'\{.*?"title".*?"sections".*?\[.*?\].*?\}',
                            r'\{(?:[^{}]|{[^{}]*})*\}',
                        ]
                        
                        for pattern in json_patterns:
                            json_match = re.search(pattern, cleaned_content, re.DOTALL)
                            if json_match:
                                try:
                                    json_str = json_match.group()
                                    # Nettoyer encore le JSON extrait
                                    json_str = clean_json_string(json_str)
                                    print(f"🔍 JSON extrait: {json_str[:200]}...")
                                    course_data = json.loads(json_str)
                                    print(f"✅ JSON parsé avec regex: {list(course_data.keys())}")
                                    break
                                except json.JSONDecodeError as regex_parse_error:
                                    print(f"❌ Erreur parsing avec regex: {regex_parse_error}")
                                    continue
                    except Exception as extraction_error:
                        print(f"❌ Erreur lors de l'extraction: {extraction_error}")
                
                # Si on a réussi à parser le JSON
                if course_data and isinstance(course_data, dict) and 'sections' in course_data:
                    print(f"✅ Structure JSON valide trouvée avec {len(course_data['sections'])} sections")
                    
                    # Traiter chaque section
                    processed_sections = []
                    for i, section in enumerate(course_data.get('sections', [])):
                        if isinstance(section, dict):
                            processed_content = process_section_content(section.get('content', ''))
                            processed_sections.append({
                                'type': section.get('type', f'section_{i}'),
                                'title': section.get('title', f'Section {i+1}'),
                                'content': processed_content
                            })
                        else:
                            print(f"⚠️ Section {i} n'est pas un dict: {type(section)}")
                    
                    context = {
                        'generated_course': {
                            'title': course_data.get('title', topic.title()),
                            'topic': topic,
                            'module': module,
                            'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                            'difficulty': result['difficulty'],
                            'sections': processed_sections,
                            'sources': result['sources']
                        },
                        'modules': module_loader.get_available_modules()
                    }
                    print(f"✅ Cours structuré créé avec {len(processed_sections)} sections")
                else:
                    print("❌ Structure JSON invalide, utilisation du fallback")
                    raise ValueError("Structure JSON invalide")
                    
            except Exception as main_error:
                print(f"❌ Erreur complète de parsing: {main_error}")
                # Fallback complet - créer un cours simple mais bien formaté
                processed_content = create_fallback_course(result['content'], topic)
                context = {
                    'generated_course': {
                        'title': f"Cours sur {topic.title()}",
                        'topic': topic,
                        'module': module,
                        'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                        'difficulty': result['difficulty'],
                        'sections': processed_content,
                        'sources': result['sources']
                    },
                    'modules': module_loader.get_available_modules()
                }
                print("✅ Fallback course créé")
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


def create_fallback_course(content, topic):
    """Crée un cours de fallback bien structuré même si le JSON parsing échoue"""
    
    # Nettoyer le contenu et extraire le JSON si dans des blocs markdown
    clean_content = str(content)
    
    # Extraire le JSON des blocs markdown si présent
    if '```' in clean_content:
        json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', clean_content, re.DOTALL)
        if json_blocks:
            clean_content = json_blocks[0].strip()
            print(f"🔍 Fallback: JSON extrait des blocs markdown")
    
    # Nettoyer les caractères de contrôle
    clean_content = clean_content.replace('\n', ' ').replace('\r', ' ')
    
    # Supprimer les caractères de contrôle
    clean_content = ''.join(char if ord(char) >= 32 or char in ['\n', '\r', '\t'] else ' ' for char in clean_content)
    
    # Essayer une dernière fois de parser le JSON nettoyé
    try:
        if clean_content.strip().startswith('{') and '"title"' in clean_content and '"sections"' in clean_content:
            course_data = json.loads(clean_content)
            if isinstance(course_data, dict) and 'sections' in course_data:
                print("✅ Fallback: JSON parsé avec succès !")
                processed_sections = []
                for section in course_data.get('sections', []):
                    if isinstance(section, dict):
                        processed_content = process_section_content(section.get('content', ''))
                        processed_sections.append({
                            'type': section.get('type', 'section'),
                            'title': section.get('title', 'Section'),
                            'content': processed_content
                        })
                return processed_sections
    except Exception as fallback_error:
        print(f"❌ Fallback JSON parsing échoué: {fallback_error}")
    
    # Essayer d'extraire des sections basiques
    sections = []
    
    # Section Introduction
    sections.append({
        'type': 'introduction',
        'title': '📖 Introduction',
        'content': f'<p>Dans ce cours, nous allons explorer <span class="keyword">{topic}</span> en detail.</p>'
    })
    
    # Section principale avec le contenu
    # Limiter le contenu pour éviter l'affichage de JSON brut
    if len(clean_content) > 500 and ('{' in clean_content or '"type"' in clean_content):
        # Si ça ressemble à du JSON, créer un contenu générique
        processed_content = f'<p>Ce cours couvre les aspects essentiels de <span class="keyword">{topic}</span>.</p><p>Nous explorerons les concepts fondamentaux, la syntaxe, et des exemples pratiques.</p>'
    else:
        processed_content = process_section_content(clean_content[:500])
    
    sections.append({
        'type': 'content',
        'title': '🔍 Contenu Principal',
        'content': processed_content
    })
    
    # Section exemples si on trouve du code
    if any(keyword in clean_content.lower() for keyword in ['def ', 'print(', 'import ', '=']):
        sections.append({
            'type': 'examples',
            'title': '💡 Exemples',
            'content': f'''
            <p>Voici quelques exemples pratiques :</p>
            <div class="code-block">
                <div class="code-header">
                    <span class="code-language">🐍 Python</span>
                    <button class="copy-btn" onclick="copyCode(this)">
                        <i data-lucide="copy"></i> Copier
                    </button>
                </div>
                <pre><code class="language-python"># Exemple de base pour {topic}
print("Hello, {topic}!")

# Voici un exemple simple
variable = "exemple"
print(variable)</code></pre>
            </div>
            '''
        })
    
    return sections


def process_section_content(content):
    """Convertit le contenu d'une section en HTML formaté"""
    if not content:
        return '<p>Contenu en cours de génération...</p>'
    
    # Convertir les blocs de code Python
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
    
    # Convertir les mots en gras
    content = re.sub(r'\*\*(.*?)\*\*', r'<span class="keyword-highlight">\1</span>', content)
    
    # Convertir les listes à puces
    content = re.sub(r'^• (.*?)$', r'<li class="modern-list-item">\1</li>', content, flags=re.MULTILINE)
    content = re.sub(r'^\* (.*?)$', r'<li class="modern-list-item">\1</li>', content, flags=re.MULTILINE)
    
    # Grouper les listes
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
                # Éviter d'afficher du JSON brut
                if not (line.startswith('{') or line.startswith('"') or 'type":' in line):
                    processed_lines.append(f'<p class="content-text">{line}</p>')
    
    if in_list:
        processed_lines.append('</ul>')
    
    result = '\n'.join(processed_lines)
    
    # Si le résultat est vide ou trop court, ajouter un contenu par défaut
    if len(result.strip()) < 50:
        result = '<p class="content-text">Contenu en cours de génération. Veuillez réessayer.</p>'
    
    return result


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
            
        except Exception as save_error:
            print(f"❌ Erreur lors de la sauvegarde : {save_error}")
            messages.error(request, f'❌ Erreur lors de la sauvegarde : {save_error}')
            return redirect('courses:generator')
    
    return redirect('courses:generator')


@login_required
def course_detail(request, course_id):
    """Affiche un cours sauvegardé"""
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