import re
from typing import Dict, Any
from langchain_community.llms import Ollama
from .prompts import COURSE_GENERATION_PROMPT

class CourseGenerator:
    def __init__(self):
        self.llm = Ollama(model="mistral")
    
    def generate_course(self, topic: str) -> Dict[str, Any]:
        """Génère un cours complet sur un sujet donné"""
        try:
            # Génération du contenu via LLM
            prompt = COURSE_GENERATION_PROMPT.format(topic=topic)
            raw_content = self.llm.invoke(prompt)
            
            # Formatage pour l'affichage HTML
            formatted_content = self._format_course_content(raw_content)
            
            return {
                'title': f"Cours : {topic}",
                'content': formatted_content,
                'topic': topic,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'title': f"Erreur - {topic}",
                'content': f"<p class='error'>Erreur lors de la génération : {str(e)}</p>",
                'topic': topic,
                'status': 'error'
            }
    
    def _format_course_content(self, content: str) -> str:
        """Formate le contenu du cours pour l'affichage HTML"""
        
        # 1. NETTOYER LES BALISES HTML DANS LES BLOCS DE CODE
        def clean_code_blocks(match):
            code_content = match.group(1)
            # Supprimer toutes les balises HTML du code
            cleaned_code = re.sub(r'<[^>]+>', '', code_content)
            # Supprimer les attributs de classe restants
            cleaned_code = re.sub(r'class="[^"]*"', '', cleaned_code)
            return f'```python\n{cleaned_code}\n```'
        
        content = re.sub(r'```python\n(.*?)\n```', clean_code_blocks, content, flags=re.DOTALL)
        
        # 2. CORRIGER LES NUMÉROTATIONS (ajouter des espaces)
        content = re.sub(r'\b(Exemple)(\d+)', r'\1 \2', content)
        content = re.sub(r'\b(Exercice)(\d+)', r'\1 \2', content)
        content = re.sub(r'\b(Example)(\d+)', r'\1 \2', content)
        content = re.sub(r'\b(Exercise)(\d+)', r'\1 \2', content)
        
        # 3. CONVERSION DES TITRES MARKDOWN EN HTML
        content = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
        content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # 4. FORMATAGE DES SECTIONS D'EXEMPLES
        def format_example_section(match):
            title = match.group(1).strip()
            # Supprimer les deux points à la fin s'ils existent
            title = re.sub(r'\s*:\s*$', '', title)
            return f'<div class="example-section"><div class="example-title">{title}</div>'
        
        content = re.sub(r'^(Exemple\s+\d+[^:\n]*):?\s*$', format_example_section, content, flags=re.MULTILINE)
        
        # 5. FORMATAGE DES SECTIONS D'EXERCICES
        def format_exercise_section(match):
            title = match.group(1).strip()
            # Supprimer les deux points à la fin s'ils existent
            title = re.sub(r'\s*:\s*$', '', title)
            return f'<div class="exercise-section"><div class="exercise-title">{title}</div>'
        
        content = re.sub(r'^(Exercice\s+\d+[^:\n]*):?\s*$', format_exercise_section, content, flags=re.MULTILINE)
        
        # 6. FORMATAGE DES BLOCS DE CODE PYTHON
        def format_code_block(match):
            code_content = match.group(1).strip()
            return f'<div class="code-block"><pre><code class="language-python">{code_content}</code></pre></div>'
        
        content = re.sub(r'```python\n(.*?)\n```', format_code_block, content, flags=re.DOTALL)
        
        # 7. FORMATAGE DU TEXTE EN GRAS
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        
        # 8. FORMATAGE DES LISTES
        content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        content = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', content, flags=re.DOTALL)
        content = re.sub(r'</ul>\s*<ul>', '', content)
        
        # 9. FORMATAGE DES PARAGRAPHES
        lines = content.split('\n')
        formatted_lines = []
        in_section = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Vérifier si on est dans une section spéciale
            if '<div class="example-section">' in line or '<div class="exercise-section">' in line:
                in_section = True
                formatted_lines.append(line)
            elif '</div>' in line and in_section:
                formatted_lines.append('</div>')
                in_section = False
            elif line.startswith('<h') or line.startswith('<div') or line.startswith('<ul') or line.startswith('<li'):
                formatted_lines.append(line)
            elif not in_section and not line.startswith('<'):
                formatted_lines.append(f'<p>{line}</p>')
            else:
                formatted_lines.append(line)
        
        content = '\n'.join(formatted_lines)
        
        # 10. FERMETURE AUTOMATIQUE DES SECTIONS
        # Compter les ouvertures et fermetures de sections
        example_opens = content.count('<div class="example-section">')
        example_closes = content.count('</div>')
        
        # Ajouter les fermetures manquantes à la fin
        missing_closes = example_opens + content.count('<div class="exercise-section">') - example_closes
        if missing_closes > 0:
            content += '</div>' * missing_closes
        
        return content