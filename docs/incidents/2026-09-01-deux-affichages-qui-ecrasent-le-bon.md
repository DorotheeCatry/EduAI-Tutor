# Incident 013 — Deux affichages qui écrasent le bon

**Date :** 1er septembre 2026
**Composant :** `apps/quiz/templates/quiz/room_detail.html`, `apps/quiz/templates/quiz/multiplayer_game.html`
**Gravité :** moyenne — le salon d'attente ne montrait pas les arrivées ; le podium disparaissait
**Statut :** résolu, en attente de confirmation à l'usage
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétence concernée :** C17 (E4)

---

## 1. Déclenchement

Deux signalements de l'autrice, à quelques minutes d'intervalle, pendant une
partie d'essai :

> quand un joueur rejoint ma partie, le nombre de joueurs ne se met pas à jour

> c'est super le podium, le problème c'est qu'il s'enlève très vite

Deux symptômes sans rapport apparent. Ils partagent pourtant une forme : **un
affichage écrit au mauvais endroit, ou au mauvais moment.**

## 2. Premier cas — le sondage visait le mauvais titre

Le salon d'attente interrogeait le serveur toutes les deux secondes, puis
écrivait le résultat ainsi :

```js
const playersTitle = document.querySelector('h3');
playersTitle.textContent = `Players (${data.player_count}/…)`;
```

`querySelector('h3')` rend le **premier** `h3` du document. Sur cette page,
c'est celui des réglages de la partie, situé plus haut. Le sondage réécrivait
donc « Réglages de la partie » toutes les deux secondes, pendant que le compteur
des joueurs, lui, gardait la valeur rendue par le serveur au chargement.

Le sondage fonctionnait, la donnée était juste, elle arrivait à l'heure : elle
était déposée ailleurs.

**Un second défaut se cachait derrière le premier.** Même corrigé, le compteur
seul aurait menti par omission : la **liste des participants** n'était pas
rafraîchie du tout. Le nombre serait passé de 1 à 2 sans que le nouveau venu
apparaisse. La liste se reconstruit désormais à chaque sondage, à partir des
participants que l'API renvoyait déjà.

## 3. Second cas — une course entre deux affichages

Le podium s'affichait, puis disparaissait au bout de deux secondes.

L'enchaînement, une fois déplié :

1. le joueur répond à la dernière question ;
2. la correction s'affiche, et un délai de deux secondes est armé ;
3. **entre-temps**, le sondage du classement — qui bat toutes les deux secondes,
   indépendamment — constate que la partie est finie et affiche le podium ;
4. le délai armé à l'étape 2 expire et affiche l'écran d'attente, **par-dessus
   le podium** ;
5. plus rien ne ramène le podium : le sondage ne le montre que lorsqu'il
   *découvre* la fin, et la partie est déjà marquée finie de son côté.

Deux affichages, deux horloges, aucune préséance. La correction n'est pas un
délai mieux choisi — ce serait rendre la course moins probable, pas l'abolir —
mais **une préséance déclarée** : une fois la partie close, aucun affichage
tardif ne s'impose. `attendreLaFinDeLaPartie` et `showQuestion` renoncent si la
partie est finie.

## 4. Ce que ces deux cas ont en commun

Ce n'est pas la famille B — les instruments mesuraient juste. C'est un motif
d'**affichage** :

> **La donnée était bonne, l'instant ou l'endroit ne l'était pas.**

Dans les deux cas, la partie logique fonctionnait et rien n'échouait. Un test
d'API aurait été vert pour le salon : le serveur renvoyait bien deux joueurs.
Ce qui manquait était le lien entre la donnée juste et l'endroit où elle
s'écrit.

**La parade retenue est la même des deux côtés : nommer sa cible.** Le titre
des joueurs se désigne par un identifiant, jamais par sa position dans le
document ; la fin de partie se désigne par un état, jamais par un délai
supposé écoulé.

## 5. Ce que les tests fixent

- Le salon ne contient plus aucun sélecteur de balise nue ; le titre porte un
  identifiant. Le premier écrit de ce test a d'ailleurs échoué sur le
  **commentaire** qui décrit le défaut : un test qui interdit de citer ce qu'on
  a corrigé est un test mal écrit, il ignore désormais les lignes de
  commentaire.
- Le sondage nomme les joueurs présents, et pas seulement leur nombre.
- Les deux fonctions d'affichage tardif renoncent quand la partie est close.
