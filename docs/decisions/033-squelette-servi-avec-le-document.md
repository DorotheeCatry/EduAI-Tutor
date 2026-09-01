# 033 — La coquille est stylée avant l'arrivée du CDN

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — accessibilité et performance perçue ; C21 (E5)

## Contexte

> à chaque fois que je change de page avec la barre de nav latérale ou
> supérieure, j'ai l'écran qui saute, ce n'est pas fluide et ça m'énerve.

## Ce que la mesure a établi

Tailwind n'est pas chargé ici comme une feuille de style, mais comme un
**générateur qui s'exécute dans le navigateur** (`cdn.tailwindcss.com`,
407 Kio). Tant qu'il n'a pas tourné, aucune classe utilitaire ne veut dire quoi
que ce soit.

Durée de ce vide, mesurée en navigateur sans tête, cache chaud, sur une page
plus légère que celles de l'application : **environ 180 ms**, à chaque
chargement. Chaque navigation étant un chargement complet, cela vaut pour
chaque changement de page.

Ce que montre l'écran pendant ce temps, relevé sur la page réelle du tableau de
bord, Tailwind rendu injoignable :

| | fond | disposition de la coquille | barre latérale |
|---|---|---|---|
| avant | transparent, donc **blanc** | `block` | **1249 px** |
| après | `#111827` | `flex` | 64 px |

La barre latérale occupait donc toute la largeur de la fenêtre, sur fond blanc,
avant de se replier à 64 px sur fond sombre. Le « saut » n'est pas une
impression : c'est un changement de mise en page complet, deux fois par
navigation.

## Options

1. **Servir un squelette en clair** dans le document, avant le CDN.
2. **Compiler la feuille Tailwind** avec `django-tailwind`, déjà installé.
3. **Masquer le corps** jusqu'à ce que Tailwind ait tourné.

## Option retenue

**La première.**

## Raisons

**L'option 2 est la bonne à terme, et elle est bloquée.** Le projet a bien
`django-tailwind`, un dossier `theme/static_src` et une feuille compilée — mais
elle date du 22 décembre 2025, et la reconstruction échoue : Node v12 est
installé, Tailwind 3.4 exige Node 14 ou plus. Vérifié en lançant la commande,
pas supposé. Mettre à niveau Node trois jours avant le rendu, puis vérifier que
la feuille compilée couvre toutes les classes de toutes les pages, c'est
exactement le risque que le cahier des charges écarte.

**L'option 3 échange un défaut contre un autre** : la page ne sauterait plus,
elle resterait vide 180 ms. Sur une navigation qui se veut immédiate, un écran
vide se remarque autant qu'un saut, et il pénalise davantage une connexion
lente.

**L'option 1 est bornée et réversible.** Une quinzaine de règles, portant les
mêmes noms et les mêmes valeurs que celles de Tailwind : quand le générateur
prend la main, il ne change rien à ce qui est déjà à l'écran. Le jour où
l'option 2 devient possible, ce bloc se retire d'une seule suppression.

## Ce qui a été écarté par la mesure

**Différer le chargement de Lucide** (632 Kio, plus lourd que Tailwind) a été
mesuré : aucun gain sur la fenêtre sans style, le coût étant dominé par
l'exécution de Tailwind. Le changement n'a donc pas été fait — il aurait été
plausible, il n'était pas utile.

## Conséquences

- Le squelette couvre la coquille seulement : corps, disposition en colonnes,
  largeur de la barre latérale, hauteurs des barres d'onglets et d'état.
- La place des icônes Lucide est réservée : elles décalaient la mise en page
  une seconde fois en apparaissant.
- `scrollbar-gutter: stable` : la barre de défilement ne naît plus d'une page à
  l'autre.
- Quatre tests fixent ces règles, dont un qui vérifie que le bloc précède le
  chargement du CDN — placé après, il ne servirait à rien.

## Ce que ce choix laisse ouvert

**Cette duplication doit être tenue à jour.** Modifier la coquille sans
répercuter le changement dans le squelette fait revenir le saut, sur une
dimension moins voyante. C'est le prix assumé, et la raison pour laquelle le
bloc s'arrête à la coquille et ne descend pas dans le contenu des pages.

L'application reste dépendante de deux CDN pour son apparence, ce qui reste une
fragilité de déploiement à part entière : le corps du contenu, lui, est
toujours sans style pendant 180 ms.
