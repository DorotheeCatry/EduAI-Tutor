# 028 — La règle de progression, et le niveau qu'elle refuse de mesurer

**Date :** 31 août 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C4 (E1) — requêtes ; C13 (E3) — accessibilité ; C20 (E5)

## Contexte

La progression a une seule source : les résultats mesurés. Ni auto-évaluation,
ni notation par un formateur, ni inférence par le modèle — ces trois options
ont été écartées en amont du chantier.

Reste à dire ce qu'un résultat mesuré fait progresser, et comment. Contrainte
posée : **la règle doit être énonçable en une phrase par niveau, et vérifiable
par une requête.**

## La règle

> **Niveau 1 — imiter.** Un exercice rattaché à la compétence a été réussi.
>
> **Niveau 2 — adapter.** Trois exercices distincts rattachés à la compétence
> ont été réussis.
>
> **Niveau 3 — transposer.** Non mesuré en l'état.

## Pourquoi trois pour le niveau 2

**Trois plutôt que deux** : deux réussites peuvent tenir au hasard d'un énoncé
proche du premier.

**Trois plutôt que cinq** : au-delà, on mesure l'assiduité plus que la
compétence. L'argument a pesé pour une raison concrète — une démonstration
devrait produire cinq exercices réussis par compétence pour montrer un seul
niveau 2, ce qui n'est pas tenable dans le temps d'une soutenance.

## Le niveau 3, et pourquoi il n'est pas mesuré

C'est le point qui demandait une décision plutôt qu'un seuil.

« Transposer » suppose d'appliquer une notion à un **contexte non rencontré**.
Or un compteur d'exercices ne distingue pas cela d'une répétition. Trois
options ont été examinées.

| Option | Ce qu'elle mesurerait vraiment | Retenue ? |
|---|---|---|
| Un seuil plus élevé — six exercices | La même preuve, en plus grand nombre. Appeler « transposer » une accumulation, c'est mettre un mot fort sur un compteur | **non** |
| La réussite au premier essai | L'**autonomie** : produire sans tâtonner. Un vrai signal — mais rien n'établit qu'un énoncé engendré à partir du même libellé de compétence constitue un contexte nouveau. Le modèle produit des énoncés voisins pour une même compétence | **non** |
| Déclarer le niveau non mesurable, et l'afficher | Rien, et le dire | **oui** |

**Un niveau affiché comme non mesurable est plus honnête qu'un niveau atteint
par accumulation.** C'est la position du projet depuis une semaine : une donnée
qui informe sans prétendre certifier vaut mieux qu'une donnée qui certifie à
tort.

### Ce que le refus ne jette pas

La réussite au premier essai est **conservée comme indicateur affiché** —
« 2 réussis du premier coup » — sans donner de niveau. La donnée existe, elle
informe, elle ne prétend pas.

### Deux états distincts, et pas seulement par la couleur

`non_mesure` n'est pas `non_atteint`, et l'interface doit les distinguer par
autre chose qu'une nuance :

- **non atteint** : l'apprenant n'y est pas encore ;
- **non mesuré** : le dispositif ne sait pas conclure.

Les confondre ferait porter à l'apprenant une limite qui est la nôtre.

## Un exercice réussi à la douzième tentative

**Il compte, comme un autre, pour les niveaux 1 et 2.** Ce que les niveaux
mesurent est « sait produire », pas « sait produire vite ». Exiger la réussite
immédiate punirait l'apprentissage par essais, qui est la façon dont on apprend
à programmer.

**Il compte aussi, et d'abord, dans le bloc « à revoir ».** Les deux répondent à
des questions différentes : la progression demande *sait-il faire ?*, le bloc à
revoir demande *qu'est-ce qui a résisté ?* La même réussite laborieuse vaut donc
un niveau **et** une place en tête des notions à retravailler. Ce n'est pas une
contradiction, c'est ce qui rend le bloc utile.

## Les quiz ne font progresser aucun niveau

Les trois niveaux nomment des actes de **production** — imiter, adapter,
transposer. Un questionnaire mesure la **reconnaissance**.

**Faire attester une production par une reconnaissance n'aurait pas de sens.**

Ce que les quiz font, et qui n'est pas rien : ils alimentent le bloc « à
revoir », dont ils sont aujourd'hui la seule source. Ils révèlent une lacune ;
ils ne certifient pas une acquisition.

Ils sont désormais rattachables à une compétence, par le même choix explicite
que les exercices — non pour donner un niveau, mais pour que le bloc « à revoir »
nomme « Manipuler les listes » là où le reste de la page parle en compétences.
Un apprenant qui lit « niveau 2 sur manipuler les listes » puis « à revoir :
les listes en python » ne saurait pas s'il s'agit de la même chose.

## Une correction en cours de route : `attempts_count`

Ce compteur s'incrémente à **chaque** soumission, y compris après la réussite.
Un apprenant qui réussit du premier coup puis retravaille son code par curiosité
y affiche trois tentatives.

Il dit donc le **nombre total de soumissions**, jamais le nombre de tentatives
avant réussite. Employé tel quel, il aurait classé comme difficile un exercice
réussi immédiatement puis retravaillé.

La source correcte est la soumission : la première soumission d'un apprenant sur
un exercice est-elle une réussite ? C'est ainsi que l'indicateur de premier
essai est calculé, et c'est ainsi que le bloc « à revoir » devra compter.

## Les limites, écrites et non masquées

**Trois énoncés proches peuvent donner un niveau 2 sans variation réelle.**
Trois exercices « distincts » sont trois lignes distinctes en base ; rien ne
garantit que le modèle n'ait pas produit trois variantes du même problème sur
la même compétence. Le vérifier supposerait de comparer les contenus, ce qui
n'est pas ouvrable ici.

C'est une limite du dispositif, pas une négligence : le niveau 2 atteste que
trois exercices ont été résolus, pas que trois problèmes différents l'ont été.

**La difficulté n'entre pas dans la règle.** L'apprenant la choisit lui-même ;
en faire un critère allongerait la règle sans la rendre plus juste.

**Les exercices hors référentiel ne comptent pour rien**, ce que l'interface
annonce à l'endroit où on les voit.

## Conséquences

- `apps/referentiel/progression.py` : deux requêtes au total quel que soit le
  nombre de compétences, les décomptes ramenés en une fois puis rapprochés en
  mémoire.
- `LearningSession.competence` et `UserMistake.competence` : le quiz rattache,
  sans progresser.
- Douze tests, dont la moitié sont des cas **négatifs** — un quiz qui ferait
  progresser, un exercice hors référentiel qui compterait, une resoumission qui
  vaudrait un exercice de plus. Ce sont eux qui rendent vraie l'annonce faite à
  l'apprenant.
- Le consommateur de cette règle est la page d'accueil, à l'étape suivante. Si
  elle ne se faisait pas, ce module serait à retirer et non à laisser dormir.
