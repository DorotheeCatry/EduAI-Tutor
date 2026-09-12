# 047 — Un gabarit d'invite explicite, et une seule recherche par réponse

**Date :** 12/09/2026
**Compétences :** C10 (épreuve E3), C13 (E3), C17 (E4), C4 (E1)

## Contexte

Dans la partie cours, Koda répondait à côté : un développement sur le sujet
général plutôt qu'une réponse à la demande, et une longueur sans rapport avec
la question. La décision 044 avait déjà ajouté une consigne de proportion à
l'invite de l'enrichissement ; elle n'a pas suffi, et l'examen du chemin
complet en donne la raison.

`RetrievalQA.from_chain_type` était appelé sans `prompt`. LangChain retombe
alors sur son gabarit intégré :

> Use the following pieces of context to answer the question at the end. If you
> don't know the answer, just say that you don't know…

Il est en anglais, ne dit rien de la longueur, et ordonne de s'appuyer sur le
contexte trouvé quel qu'il soit. Les consignes ajoutées par les appelants
arrivaient dans le champ `question` de ce gabarit — donc **sous** une consigne
qui disait déjà autre chose.

Deuxième défaut, découvert en remontant le même chemin. L'enrichissement de
fiche interrogeait `eduai_corpus_documentaire`, collait les quatre fragments
obtenus dans une invite d'environ cinq mille caractères, et passait cette
invite entière à `answer_question`. Elle y repartait dans `RetrievalQA`, qui
s'en servait comme **requête de recherche** : on cherchait des documents avec
un texte contenant déjà quatre documents. Les fragments ainsi ramenés étaient
du bruit, et venaient de surcroît de la collection pédagogique — pas de celle
dont les sources étaient affichées à l'apprenant.

Troisième point, indépendant : le raccourci qui répond aux politesses sans
appeler le modèle (décision 044) n'existait que sur `courses:enrichir`. Le
panneau flottant, présent sur toutes les pages, envoyait le même « bonjour » au
modèle et décomptait une génération. Et la liste des tournures ne connaissait
ni les abréviations (`bjr`, `slt`, `cc`) ni l'enchaînement le plus courant de
tous — « bonjour, ça va ? », deux formules connues collées, dont aucune ne
correspondait au message entier.

## Options

1. **Renforcer encore les consignes dans l'invite des appelants** — continuer
   dans la voie de la décision 044.
2. **Poser un gabarit explicite sur la chaîne**, et faire porter à chaque
   appelant seulement ce qui lui est propre.
3. **Remplacer `RetrievalQA`** par une chaîne composée à la main.

## Option retenue

La deuxième, en trois gestes.

`apps/agents/prompts/researcher_rag.txt` porte les consignes — langue,
périmètre, proportion, conduite à tenir quand la documentation ne répond pas —
et `gabarit_de_reponse()` le charge pour `RetrievalQA`.

`answer_question` accepte `extraits` : un appelant qui a déjà sa documentation
la fournit, et aucune seconde recherche n'a lieu. L'appel reste au même goulot,
celui qui décompte le quota et déclare l'agent au monitorage.

Le champ `question` transmis au modèle ne porte plus que les mots de
l'apprenant. Le cadre — la compétence travaillée — est rangé avec le contexte,
là où il appartient.

## Raisons

**Une consigne placée sous une autre consigne ne gagne pas.** C'est ce qui
explique que la décision 044 n'ait pas tenu : elle écrivait la bonne règle au
mauvais endroit. La règle de proportion appartient au gabarit, pas à la
demande, parce que c'est une propriété de Koda et non de telle question.

**Une requête de recherche n'est pas une invite.** Les confondre était sans
symptôme visible — ni erreur, ni journal — et la seule trace en était une
réponse hors sujet. C'est la forme de panne la plus coûteuse à diagnostiquer,
et un test la surveille désormais.

**Les sources affichées doivent être celles qui ont servi.** Montrer les
fragments d'une collection et répondre à partir d'une autre n'est pas une
imprécision : c'est une attribution fausse, sur un corpus dont l'usage est
précisément conditionné à l'attribution (décision 041).

**Remplacer `RetrievalQA` aurait été un chantier, pas un correctif.** La
bibliothèque accepte un gabarit ; il suffisait de le lui donner. À dix jours de
la soutenance, la solution qui tient en un argument vaut mieux que celle qui
tient en un module.

**Un dispositif qui ne tient que sur une des deux portes d'entrée ne tient
pas.** Le raccourci des politesses est désormais posé sur les deux, avec la
même fonction de reconnaissance — et non deux listes qui divergeraient.

## Limite connue

La règle de proportion est une consigne d'invite : elle oriente le modèle, elle
ne le contraint pas. Rien ne mesure la longueur des réponses produites, et rien
ne la refuse. C'est assumé — un contrôle de longueur côté serveur couperait des
réponses au milieu, ce qui serait pire que long.
