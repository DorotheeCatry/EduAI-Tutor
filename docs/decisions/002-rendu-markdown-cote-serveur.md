# 002 — Rendu du Markdown des cours côté serveur

**Date :** 25/08/2026
**Statut :** adoptée
**Compétences concernées :** C17 (E4), C9 (E2)

## Contexte

Les agents renvoient les cours en Markdown. Ce Markdown n'était jamais converti
côté serveur : `markdown2` était importé dans `apps/courses/views.py` sans
jamais être appelé, le contenu brut était injecté dans le gabarit via
`{{ course.content|safe }}`, puis un parseur d'une quinzaine d'expressions
régulières tentait de le reformater dans le navigateur.

Trois défauts en découlaient, constatés à l'usage puis reproduits :

1. La règle qui traitait `**gras**` précédait celle qui produisait `<strong>` et
   consommait toutes les occurrences. Chaque mot en gras au milieu d'une phrase
   devenait un titre `<h3>` de niveau bloc, coupant le paragraphe en trois.
   C'est le symptôme qui a motivé la correction.
2. L'enveloppement en paragraphes s'appliquait après la génération des titres et
   des listes, plaçant des `<h2>` et des `<ul>` à l'intérieur de `<p>`. Le
   navigateur refermait ces `<p>` d'office, d'où des marges verticales
   incohérentes.
3. Aucune règle ne traitait les tableaux : ils s'affichaient en barres
   verticales brutes.

S'y ajoutait une faille : `|safe` désactive l'échappement sur une sortie de
modèle de langage, alors que le sujet saisi par l'apprenant alimente le prompt.
Une injection amenant le modèle à produire `<script>` ou un attribut `onerror`
s'exécutait dans la page.

## Options envisagées

**A — Corriger l'ordre des expressions régulières.** Coût immédiat faible, mais
laisse un parseur Markdown maison à maintenir, ne traite ni les tableaux ni la
hiérarchie des titres, et ne corrige pas la faille XSS.

**B — Installer le plugin Tailwind Typography et garder le parseur.** Améliore
l'apparence sans traiter la cause : la conversion resterait fautive, et la
dépendance suppose une recompilation Tailwind à dix jours du rendu.

**C — Convertir avec `markdown2` côté serveur et supprimer le parseur.**
Retenue.

## Décision

La conversion est faite dans `render_markdown()`, dans `apps/courses/views.py`,
avec les extras `fenced-code-blocks`, `highlightjs-lang`, `tables`,
`break-on-newline` et `cuddled-lists`. `markdown2` était déjà déclaré comme
dépendance : aucune n'est ajoutée.

`safe_mode="escape"` neutralise le HTML brut produit par le modèle et ferme la
faille XSS. L'extra `tables` produit des `<table>` à en-têtes `<th>`,
restituables par un lecteur d'écran — exigence d'accessibilité transversale des
grilles.

Le gabarit reçoit désormais deux valeurs distinctes : `content`, le Markdown, qui
alimente le formulaire d'enregistrement et reste le format stocké en base ; et
`content_html`, réservé à l'affichage. La base continue donc de contenir du
Markdown, ce qui laisse le rendu modifiable sans migration de données.

Le JavaScript ne conserve qu'une fonction de décoration, `decorateCodeBlocks()`,
qui ajoute l'en-tête de langage et le bouton de copie aux `<pre><code>` produits
par `markdown2`. Elle construit les nœuds via `textContent` plutôt que par
concaténation de HTML.

Les styles du contenu sont écrits explicitement dans le gabarit, préfixés par
`#course-content`. Le plugin Tailwind Typography n'étant pas installé, les
classes `prose` présentes dans le balisage ne produisaient presque aucun effet ;
s'appuyer sur elles aurait imposé une recompilation Tailwind.

## Conséquences

**Positives.** Le rendu est déterministe et vérifiable côté serveur, sans
dépendre de l'exécution d'un script dans le navigateur. Le flash de Markdown
brut lié au `setTimeout` de 100 ms disparaît. Les tableaux et la hiérarchie de
titres deviennent corrects, ce qui sert directement les critères
d'accessibilité. La faille XSS est fermée.

**Négatives.** Les styles du contenu sont désormais écrits à la main dans le
gabarit plutôt que dérivés du système de design. C'est un compromis assumé :
installer Tailwind Typography relève d'un changement de dépendance, exclu d'ici
le 4 septembre.

**Suivi.** Les cours déjà enregistrés sont stockés en Markdown et bénéficient du
nouveau rendu sans reprise de données.
