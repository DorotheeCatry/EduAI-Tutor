# Démarche de conduite du projet

**Date :** 28 août 2026
**Compétence visée :** C16 (épreuve E4) — démarche de gestion de projet
**Compétences concernées :** C19 (E4) — traçabilité ; C18 (E4)

---

## Avertissement

**Ce document décrit la démarche réellement suivie, pas une démarche agile
reconstituée.**

Le projet a été mené par une seule personne, sans outil de gestion de projet,
sans sprints, sans backlog priorisé, sans cérémonies. Écrire un historique de
sprints qui n'a pas eu lieu serait facile et vérifiable en quelques minutes par
un jury qui ouvrirait l'historique Git. Ce qui suit est donc ce qui s'est
produit, mesuré dans le dépôt, suivi de ce qui manque au regard d'une démarche
agile complète.

---

## 1. Le rythme réel

L'historique compte **474 commits**, répartis en deux phases séparées par une
interruption de treize mois.

| Phase | Période | Commits | Objet |
|---|---|---|---|
| **1 — construction** | 10 au 24 juillet 2025 | 272 | Développement de l'application : agents, RAG, interface, quiz, exercices |
| **interruption** | 25 juillet 2025 au 24 août 2026 | 0 | — |
| **2 — mise en conformité** | 25 au 28 août 2026 | 120 | Alignement sur le référentiel : pipeline de données, bases, deux API, tests, monitorage, documentation |

**L'interruption est un fait du projet, pas un accident à masquer.** Elle
explique la forme de la seconde phase : il ne s'agissait pas de continuer un
développement mais de reprendre une application existante et fonctionnelle pour
la mettre en conformité avec un référentiel. Cela a déterminé une règle de
travail explicite — **ne pas reconstruire ce qui marche** — et l'interdiction de
toute restructuration de l'arborescence pendant la seconde phase.

Cela explique aussi une découverte du redémarrage : l'environnement était
inutilisable, l'interpréteur du projet pointant vers un binaire absent de la
machine. Un projet repris après treize mois ne redémarre pas là où il s'est
arrêté.

---

## 2. Le découpage : par chantier, pas par sprint

Le travail a été découpé en **chantiers**, chacun correspondant à une compétence
ou à un groupe de compétences du référentiel. Un chantier a une entrée — ce qui
manque — et une sortie — la preuve produite.

**20 branches de chantier** existent dans le dépôt, nommées
`<type>/<bloc>-<sujet>` :

```
feat/pipeline-extraction-c1        feat/bdd-postgresql-c4
feat/bloc2-monitorage-c20          feat/bloc2-benchmark-modeles-c7
feat/bloc2-indexation-corpus-c10   docs/bloc2-veille-c6
docs/transversal-matrice-tracabilite   docs/bloc3-cadrage-c14-c16
perf/bloc1-mesure-comparative-c2   ...
```

**Pourquoi le chantier plutôt que le sprint.** Un sprint est une boîte de temps
qui contient ce qu'on y met ; il suppose une équipe, une vélocité mesurée et un
engagement collectif. Aucun des trois n'existe ici. Le chantier est une boîte de
**périmètre** : il se termine quand la preuve est produite et vérifiée, pas
quand deux semaines se sont écoulées. C'est un découpage adapté à la contrainte
réelle du projet — la couverture de vingt et une compétences, chacune
indispensable, aucune sacrifiable.

**La règle de fin de chantier** : la fusion dans `main` n'a lieu que lorsque le
chantier est testé et fonctionnel. Un crochet de pré-commit refuse les commits
directs sur `main`.

---

## 3. La traçabilité des arbitrages

Trois mécanismes, tous versionnés, remplacent ce qu'un outil de gestion de
projet aurait porté.

### 3.1 Le journal de décisions — 17 entrées

Toute décision d'architecture non triviale donne lieu à une entrée courte :
contexte, options envisagées, option retenue, raison, conséquences. **Les
options écartées y figurent avec leur motif d'exclusion** — c'est ce qui
distingue une décision d'une justification a posteriori.

La règle d'écriture est stricte sur un point : **la décision s'écrit pendant la
session où elle est prise**, avant de passer à la suite. Reconstituer un
arbitrage de mémoire trois jours plus tard produit une rationalisation, pas une
trace.

### 3.2 Les messages de commit portant la compétence

**118 des 120 commits de la seconde phase** portent la ou les compétences entre
crochets : `feat(extract): ajoute l'extracteur API [C1]`.

Ce n'est pas une convention décorative : elle rend l'historique interrogeable
par compétence.

```bash
git log --grep="\[C7\]" --oneline
```

La convention a été adoptée le **25 août 2026**, au redémarrage. Les 272 commits
de la première phase ne la portent pas. Cela se voit, et il vaut mieux le dire
que le laisser découvrir : la traçabilité par compétence couvre la phase de mise
en conformité, non la phase de construction initiale.

### 3.3 Les notes de session — 4 entrées

En fin de session : ce qui a été fait, les difficultés rencontrées, les choix
effectués, les compétences touchées. Elles sont la matière première des rapports
écrits, et évitent de reconstituer une semaine de travail de mémoire.

Leur rubrique la plus utile n'est pas « ce qui a été fait » mais **« difficultés
rencontrées »** : c'est celle qui se perd le plus vite, et celle qu'un jury
interroge.

---

## 4. La qualité, en continu

| Mécanisme | Effet |
|---|---|
| **78 tests `pytest`** | Rejoués à chaque poussée |
| **Intégration continue à trois travaux** | Qualité du code, tests sur PostgreSQL réel, construction et inspection de l'image. Aucun en `continue-on-error` |
| **4 dossiers d'incident** | Déclenchement, périmètre, diagnostic, résolution, tests en succès |
| **Contrôles de non-régression** | Chaque incident produit un test qui le garde de revenir |

Le lien entre incident et test est le point le plus proche d'une **rétrospective**
que le projet ait produit : un incident est analysé, sa cause nommée, et un
contrôle écrit pour qu'il ne se reproduise pas. C'est une rétrospective par
défaut, déclenchée par la panne plutôt que par le calendrier — voir § 6.

---

## 5. Les points de validation

Le projet n'a pas de revue par un pair, mais il a des **points d'arrêt
explicites** entre chantiers : un chantier terminé est présenté, ses chiffres
vérifiés, et le suivant n'est engagé qu'ensuite. Deux règles s'y attachent.

**Avant toute modification touchant plus de trois fichiers : proposer un plan et
attendre validation.** Elle a évité plusieurs restructurations inutiles à
échéance courte.

**Vérifier l'effet, pas l'intention.** Un chantier n'est pas clos parce que le
code est écrit, mais parce que son effet est constaté — le nombre de lignes sur
le disque, le compte en base, la trace dans le journal. Cette règle est née des
incidents, et elle a changé la manière dont les chantiers se terminent.

---

## 6. Ce qui manque au regard d'une démarche agile complète

Énoncé franchement, parce qu'une limite assumée vaut mieux qu'une limite
découverte par le jury.

| Manquant | Ce que cela coûte réellement |
|---|---|
| **Aucune rétrospective formalisée** | Il n'existe aucun moment où l'on s'arrête pour examiner la *manière de travailler* indépendamment d'une panne. Les seules rétrospectives du projet sont les dossiers d'incident, donc **déclenchées par l'échec** : ce qui va mal assez pour casser quelque chose est examiné, ce qui va médiocrement ne l'est jamais |
| **Aucune estimation** | Aucune charge n'a été estimée avant d'être engagée, donc aucun écart entre prévu et réalisé n'est mesurable, donc aucune capacité à prévoir ne se construit. Le coût s'est vu : la conversion Spark a tourné 14 h 19 avant qu'on s'aperçoive qu'elle n'aboutirait jamais — une estimation grossière du rapport entre le jeu d'essai et le jeu réel, un facteur 800, l'aurait signalé avant le lancement |
| **Aucune revue par un pair** | Personne ne relit le code. Les tests et l'analyse statique en couvrent une partie, mais ni l'un ni l'autre ne détecte une mauvaise décision de conception — seulement une régression. C'est le manque le plus important des trois |
| **Aucun backlog priorisé ni tableau de tâches** | La priorisation s'est faite par la couverture du référentiel et le délai, tenue de tête et dans la matrice de traçabilité. Elle a fonctionné pour un projet de quatre jours à un contributeur ; elle ne passerait pas à l'échelle |
| **Aucune démonstration à un commanditaire** | Les parties prenantes de l'analyse du besoin — apprenants, formateurs, direction — sont identifiées mais n'existent pas comme interlocuteurs réels. Aucun retour d'usage n'a été recueilli, et le journal de monitorage le confirme : 4 appels au modèle, tous issus de vérifications |

### Le manque qui a réellement coûté

Sur les cinq, **l'absence d'estimation** est celui dont le coût est chiffrable :
quatorze heures de calcul perdues sur un traitement qui ne pouvait pas aboutir.
La leçon en a été tirée et appliquée aussitôt — la reprise a été mesurée par
paliers de 123 Mio, 2 Gio puis 10 Gio, avec une projection avant de lancer le
dump complet, et la projection s'est révélée conservatrice de 20 %.

C'est la seule pratique de la démarche à s'être **corrigée en cours de projet**
plutôt qu'à être adoptée d'emblée, et c'est pour cette raison qu'elle mérite
d'être signalée : elle montre par où la démarche a évolué, ce qu'un tableau de
pratiques appliquées depuis le début ne montrerait pas.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `decisions/` | Les 17 arbitrages, avec options écartées |
| `journal/` | Les notes de session |
| `incidents/` | Les 4 dossiers, et les rétrospectives par défaut qu'ils constituent |
| `traceabilite.md` | L'instrument de priorisation |
| `cadre_technique.md` | L'outillage évoqué au § 4 |
