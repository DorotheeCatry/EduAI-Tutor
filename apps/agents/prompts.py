@@ .. @@
 COURSE_GENERATION_PROMPT = """
 Tu es un expert pédagogue en programmation. Génère un cours complet et structuré sur le sujet : "{topic}".
 
+IMPORTANT - Règles de formatage strictes :
+- Utilise UNIQUEMENT du markdown pur, JAMAIS de balises HTML
+- Pour les titres, utilise : # ## ### #### 
+- Dans les blocs de code Python, n'inclus JAMAIS de balises HTML
+- Assure-toi que les numérotations ont des espaces : "Exemple 1", "Exercice 1" (pas "Exemple1")
+
 Structure obligatoire :
 1. **Introduction** (#### Introduction)
    - Présentation du concept
@@ -70,7 +76,7 @@ Structure obligatoire :
    - Au moins 3 exemples pratiques numérotés
    - Format : "Exemple 1 : [titre descriptif]"
    - Code Python avec commentaires explicatifs
-   - Résultat attendu
+   - Résultat attendu ou explication
 
 4. **Exercices pratiques** (#### Exercices pratiques)
    - Au moins 2 exercices progressifs
@@ .. @@
 
 Consignes de style :
 - Utilise un ton pédagogique et encourageant
-- Code Python propre avec commentaires
+- Code Python propre avec commentaires (SANS balises HTML)
 - Exemples concrets et variés
-- Progression logique du simple au complexe
+- Progression logique du simple vers le complexe
+- Espaces obligatoires dans les numérotations
 
 Génère maintenant le cours complet :
 """