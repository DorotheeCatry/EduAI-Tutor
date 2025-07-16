@@ .. @@
 COURSE_GENERATION_PROMPT = """
 Tu es un expert pédagogue en programmation. Génère un cours complet et structuré sur le sujet : "{topic}".
 
RÈGLES DE FORMATAGE CRITIQUES :
- Utilise UNIQUEMENT du markdown pur
- JAMAIS de balises HTML dans le contenu
- Dans les blocs de code Python : AUCUNE balise HTML, AUCUN attribut class
- Numérotations avec espaces obligatoires : "Exemple 1", "Exercice 1"
- Titres d'exemples et exercices sur une ligne séparée
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
   - Titre sur une ligne, description en dessous
 
 Consignes de style :
 - Utilise un ton pédagogique et encourageant
- Code Python PROPRE sans aucune balise HTML
+- Code Python propre avec commentaires (SANS balises HTML)
 - Exemples concrets et variés
-- Progression logique du simple au complexe
- Titres d'exemples/exercices sur des lignes séparées

EXEMPLE DE FORMATAGE CORRECT :

#### Exemples pratiques

Exemple 1 : Boucle simple

Voici comment utiliser une boucle for basique :

```python
for i in range(5):
    print(i)
```

Exercice 1 : Premier exercice

Créez une boucle qui affiche les nombres de 1 à 10.
+- Espaces obligatoires dans les numérotations
 
 Génère maintenant le cours complet :
 """