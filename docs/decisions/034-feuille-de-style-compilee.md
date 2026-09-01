# 034 — La feuille de style est compilée, le CDN abandonné

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — déploiement ; C21 (E5)

## Contexte

La décision 033 avait posé un squelette en clair dans l'en-tête pour supprimer
le saut d'affichage. Retour de l'autrice, trois heures plus tard :

> pour le trésaut, c'est un peu mieux mais ça le fait encore.

**Mesure du reste :** sur la page du tableau de bord, entre l'état sans Tailwind
et l'état avec, **41 éléments sur 41 changent de position ou de taille**. Le
squelette avait figé le cadre — fond, colonnes, largeur de la barre latérale —
et rien d'autre. Couvrir le contenu de la même façon reviendrait à réécrire
Tailwind à la main.

La décision 033 traitait donc le symptôme le plus voyant, pas la cause. La
cause est que **l'application fabrique ses styles dans le navigateur**.

## Options

1. **Compiler la feuille** avec le binaire autonome de Tailwind, abandonner le CDN.
2. **Étendre le squelette** au contenu des pages.
3. **Mettre Node à niveau** et se servir de `django-tailwind`.
4. **Assumer et documenter.**

## Option retenue

**La première.**

## Raisons

**L'option 2 ne converge pas.** Chaque page ajouterait ses règles, chaque
modification de gabarit exigerait de les tenir à jour, et le squelette
finirait par être une copie partielle et périmée de Tailwind.

**L'option 3 est bloquée, et vérifiée comme telle.** `django-tailwind` est
installé, mais son nécessaire est en **Tailwind 4** alors que l'application est
rendue depuis toujours en **3.4.17** : la reconstruction produirait un rendu
différent, pas identique. Et elle échoue de toute façon — Node v12 sur cette
machine, Tailwind 3.4 en exige 14. Constaté en lançant la commande.

**Le binaire autonome lève les deux obstacles à la fois.** Il ne demande pas
Node, et il existe en 3.4.17 : exactement la version que servait le CDN.

**L'option 4 n'était plus défendable** après deux signalements de l'autrice sur
le même défaut.

## L'équivalence a été vérifiée, pas supposée

C'est le point qui a permis de basculer à trois jours du rendu.

La géométrie de **tous** les éléments a été relevée dans un navigateur, page par
page, feuille compilée contre CDN :

| Page | éléments comparés | écarts |
|---|---|---|
| Tableau de bord | 282 | 0 |
| Accueil | 172 | 0 |
| Salon de quiz | 180 | 0 |
| Exercices | 190 | 0 |
| Inscription | 45 | 0 |
| Connexion | 48 | 4, expliqués |

Les quatre écarts de la page de connexion portent sur des éléments animés
(`animation: float 6s infinite`) : ils tiennent à la phase de l'animation au
moment du cliché, et deux d'entre eux varient déjà d'un tir à l'autre **sur le
même fichier**. La reproductibilité a été mesurée avant de conclure.

**Deux défauts ont été trouvés par cette comparaison, et par elle seule :**

1. La règle de réservation des icônes, écrite `[data-lucide] { … }` dans la
   décision 033, a la même spécificité qu'une classe utilitaire et, placée
   après elle, l'emportait : toute icône déclarée `w-8 h-8` était ramenée à
   20 px. **Ce défaut était déjà en production**, introduit par le correctif
   précédent. `:where()` annule la spécificité.
2. Le champ `content` ne couvrait que les gabarits, alors que les widgets de
   formulaire déclarent leurs classes **en Python** — les pages de connexion et
   d'inscription auraient perdu leurs styles de champ.

Aucun des deux ne se voyait à la lecture du code.

## Conséquences

- `static/css/tailwind.css`, 34 Kio, versionnée comme les catalogues `.mo` :
  l'image de déploiement est bâtie sur le clone.
- **407 Kio de JavaScript en moins** par page, et une dépendance de moins au
  moment du rendu : l'apparence de l'application ne dépend plus qu'un CDN soit
  joignable.
- Les pages de connexion et d'inscription, qui portent leur propre en-tête,
  ont été basculées elles aussi — les oublier aurait laissé le saut sur les
  deux premières pages que voit un visiteur.
- Le squelette de la décision 033 est retiré : la feuille bloque le rendu, donc
  le premier affichage est déjà le bon. Ce qu'il apportait d'autre — fond
  sombre, gouttière de défilement, réservation des icônes — est repris dans la
  source de la feuille.
- `theme/tailwind-v3/construire.sh` reconstruit, et télécharge le binaire au
  besoin. Le binaire (43 Mio) n'est pas versionné.

## Ce que ce choix laisse ouvert

**Une feuille compilée peut prendre du retard sur les gabarits.** Une classe
ajoutée sans reconstruction ne produit aucun style, et rien ne le signale : la
page s'affiche, simplement de travers. C'est le risque propre à cette approche,
et il est réel — plus insidieux que celui qu'il remplace.

La parade n'est pas la vigilance mais un test : `test_coquille_interface.py`
relève **toutes** les classes des gabarits et vérifie que chacune existe dans la
feuille. Il en connaît douze exceptions, documentées, qui ne viennent pas de
Tailwind.

Lucide reste chargé depuis un CDN, en 632 Kio. Différer ce chargement a été
mesuré : aucun gain sur la fenêtre sans style. Le sortir du CDN est une autre
décision, à prendre après le 14 septembre.
