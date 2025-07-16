@@ .. @@
     def _format_course_content(self, content: str) -> str:
         """Formate le contenu du cours pour l'affichage HTML"""
         
+        # Nettoyer les balises HTML dans les blocs de code
+        import re
+        
+        # Supprimer les balises HTML des blocs de code Python
+        def clean_code_blocks(match):
+            code_content = match.group(1)
+            # Supprimer toutes les balises HTML du code
+            cleaned_code = re.sub(r'<[^>]+>', '', code_content)
+            return f'```python\n{cleaned_code}\n```'
+        
+        content = re.sub(r'```python\n(.*?)\n```', clean_code_blocks, content, flags=re.DOTALL)
+        
         # Conversion des titres markdown en HTML avec classes CSS
-        content = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
+        content = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
         content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
         content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
         content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
         
+        # Ajouter des espaces dans les numérotations
+        content = re.sub(r'(Exemple)(\d+)', r'\1 \2', content)
+        content = re.sub(r'(Exercice)(\d+)', r'\1 \2', content)
+        content = re.sub(r'(Example)(\d+)', r'\1 \2', content)
+        content = re.sub(r'(Exercise)(\d+)', r'\1 \2', content)
+        
         # Formatage des sections d'exemples
-        content = re.sub(
-            r'(Exemple\s*\d*\s*:?\s*[^\n]+)',
-            r'<div class="example-section"><div class="example-title">💡 \1</div>',
-            content
-        )
+        def format_example_section(match):
+            title = match.group(1).strip()
+            return f'<div class="example-section"><div class="example-title">{title}</div>'
+        
+        content = re.sub(r'(Exemple\s+\d+\s*:?\s*[^\n]+)', format_example_section, content)
         
         # Formatage des sections d'exercices
-        content = re.sub(
-            r'(Exercice\s*\d*\s*:?\s*[^\n]+)',
-            r'<div class="exercise-section"><div class="exercise-title">🎯 \1</div>',
-            content
-        )
+        def format_exercise_section(match):
+            title = match.group(1).strip()
+            return f'<div class="exercise-section"><div class="exercise-title">{title}</div>'
+        
+        content = re.sub(r'(Exercice\s+\d+\s*:?\s*[^\n]+)', format_exercise_section, content)
         
         # Formatage des blocs de code Python
         def format_code_block(match):
@@ .. @@
         
         # Fermeture des divs pour les sections
         content = re.sub(r'(</div>\s*)(Exemple|Exercice)', r'\1</div>\n\2', content)
+        
+        # Ajouter des sections principales pour une meilleure structure
+        content = re.sub(
+            r'(## [^\n]+)',
+            r'<div class="main-section"><div class="main-section-title">\1</div>',
+            content
+        )
+        
+        # Fermer les sections principales
+        content = re.sub(r'(</div>\s*)(## )', r'\1</div>\n\2', content)
         
         return content