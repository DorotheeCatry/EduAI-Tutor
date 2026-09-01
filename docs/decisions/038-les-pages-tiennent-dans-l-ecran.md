# 038 — Les pages tiennent dans l'écran, ce sont les cartes qui défilent

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — accessibilité ; C21 (E5)

## Contexte

> chaque page et chaque contenu de page doit tenir sur l'écran affiché,
> scroller doit vraiment pas être quelque chose sur les pages principales à
> part pour les cours, les exos.

## Ce que la mesure a trouvé, et qui était pire

Relevé en navigateur, écran de 1366×768 :

| Page | Visible | Contenu | Écart |
|---|---|---|---|
| Référentiel | 593 px | **2090 px** | 1497 px |
| Accueil | 593 px | 768 px | 175 px |

Le problème n'était pas le défilement : **il n'y en avait pas.** `<main>` est
en `overflow-hidden`, et les conteneurs de page portaient `overflow-y-auto`
**sans hauteur contrainte**. Un tel conteneur ne défile pas : il grandit, et se
fait couper.

Quinze cents pixels de progression par compétence étaient donc **invisibles et
inatteignables** sur la page qui existe pour les montrer. Le défaut ne se
signalait pas : la page s'affichait, simplement tronquée.

**`overflow-y-auto` sans hauteur est une intention, pas un comportement.**

## Options

1. **Réduire les contenus** jusqu'à ce qu'ils tiennent.
2. **Figer l'ossature de la page** et confier le défilement aux cartes.
3. Laisser la page défiler.

## Option retenue

**La deuxième, après avoir commencé par la première.**

La compaction a bien eu lieu et elle était nécessaire : la liste des vingt et
une compétences est passée de lignes empilées — 1690 px — à une grille de
vignettes de 300 px, sans rien retirer. Le temps d'étude, qui occupait une
bande entière pour dire qu'il n'est pas mesuré, est devenu la cinquième carte
des décomptes.

Mais la compaction seule ne suffit pas, et pour une raison de méthode : **une
mise en page ajustée au pixel tient sur l'écran où on l'a mesurée et déborde
sur le suivant.** Après trois passes de resserrement, l'accueil tenait à
1920×1080 et débordait encore de 113 px sur un portable.

La page porte donc `h-full flex flex-col overflow-hidden`, et ses cartes
`overflow-y-auto min-h-0`. Résultat mesuré :

| Page | Portable, 625 px | 1080p, 937 px |
|---|---|---|
| Accueil | page fixe, une carte défile | **rien ne défile** |
| Référentiel | page fixe, une carte défile | **rien ne défile** |
| Partie de quiz | page fixe | **rien ne défile** |

**`min-h-0` n'est pas un détail** : sans lui, un enfant de conteneur flexible
refuse de rétrécir sous la taille de son contenu, le débordement remonte à la
page, et l'ossature figée ne fige plus rien. Un test le vérifie, parce que cela
ne se voit qu'à l'écran.

## La lisibilité du quiz

Sur un portable de 625 px, l'ossature de la page de jeu — rembourrage, en-tête,
pied — mangeait 132 px des 418 disponibles, laissant 120 px pour l'énoncé. Une
question qu'il faut faire défiler pour lire n'est pas une question qu'on lit.
Les rembourrages sont resserrés et l'énoncé garde la priorité sur le reste.

## Ce que ce choix laisse ouvert

**Le salon de quiz garde une liste qui défile** : le nombre de salles ouvertes
ne dépend pas de nous. La carte défile, la page non — c'est le comportement
recherché pour une liste, pas une exception à la règle.

**Les cours et les exercices continuent de défiler**, comme demandé : un
énoncé ou un cours généré n'a pas de longueur bornée.

**Rien ne mesure ceci en intégration continue.** Les tests vérifient que chaque
page traite explicitement son débordement — `h-full` et une règle d'`overflow`
— mais la hauteur réellement occupée demande un navigateur. Une régression de
mise en page reste donc détectable à l'œil, pas par la chaîne.
