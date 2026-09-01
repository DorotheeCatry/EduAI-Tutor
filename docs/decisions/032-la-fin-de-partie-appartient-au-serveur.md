# 032 — La fin d'une partie multijoueur est prononcée par le serveur

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C21 (E5) ; C20 (E5)

## Contexte

Après une partie d'essai à deux navigateurs, l'autrice a relevé :

> quand un des joueurs a terminé de répondre à la dernière question avant
> l'autre, ça lui fait déjà partie terminée, or je ne trouve pas ça ouf.

Le constat est exact, et la conséquence est plus lourde qu'un défaut de
confort : le gabarit appelait `showFinalResults()` deux secondes après **sa
propre** dernière réponse. Le joueur le plus rapide voyait donc « partie
terminée » et un classement **figé sur un état intermédiaire** — celui d'avant
la dernière réponse de l'autre. Il pouvait s'y croire vainqueur sans l'être.

## Le défaut que celui-ci cachait

Faire attendre le joueur qui a fini ne suffisait pas : l'arbitrage — qui attend
qui, et quand la partie s'achève — **ne vivait que dans `submit_answer`**. Une
partie ne pouvait donc être conclue que par un joueur en train de répondre.

Si le dernier participant attendu ferme son navigateur, plus aucune réponse
n'arrive. Personne ne reste pour prononcer la fin, et le joueur qui attend
attend indéfiniment. La conclusion locale masquait ce blocage en le
court-circuitant : **le défaut visible protégeait le défaut invisible.**

## Options

1. Attendre le serveur, et laisser l'arbitrage dans la seule soumission.
2. Attendre le serveur, et **arbitrer aussi dans le sondage d'état**.
3. Garder la conclusion locale, en rafraîchissant le classement une dernière
   fois avant de l'afficher.

## Option retenue

**La deuxième.**

## Raisons

**L'option 1 échange un défaut contre un pire.** Un classement faux se corrige
au rechargement ; une page qui attend une fin qui ne viendra jamais ne se
corrige pas.

**L'option 3 traite l'affichage, pas la question.** Le classement serait juste
à l'instant de son affichage, mais la fin de partie resterait prononcée par
chaque client pour lui-même : deux joueurs pourraient encore voir deux vérités
différentes, et rien ne garantirait que la dernière réponse soit arrivée.

**Le sondage est le seul signal qui survit à l'arrêt du jeu.** Il bat toutes
les deux secondes tant qu'une page est ouverte, indépendamment de toute
réponse. C'est exactement ce qu'il faut quand plus personne ne joue. La
présence, elle, expire au bout de quinze secondes : le joueur restant voit donc
la partie se clore une quinzaine de secondes après le départ de l'autre, sans
action de personne.

L'ordre compte : le battement de cœur du sondeur est enregistré **avant**
l'arbitrage, sans quoi le joueur qui sonde ne se compterait pas lui-même comme
présent.

## Conséquences

- `faire_avancer_la_partie(room)` est appelée par `submit_answer` **et** par
  `room_status_api`. Elle est idempotente : plusieurs clients sondent en
  parallèle.
- Le client affiche « Vous avez terminé — en attente des autres joueurs » et
  attend que la salle passe à `finished`.
- La clôture de la partie enregistre les sessions d'apprentissage de chaque
  participant (incident 012) et renseigne `finished_at`, qui ne l'était pas.
- Un podium affiche le vainqueur : son avatar, son pseudo, ses points. L'ordre
  du document suit le classement — 1er, 2e, 3e — et seule une classe `order-*`
  déplace le vainqueur au centre, pour qu'une synthèse vocale lise le classement
  dans le bon ordre. Le nom du vainqueur est annoncé en toutes lettres au-dessus
  du podium, et non porté par la seule position d'une image.

## Ce que ce choix laisse ouvert

Le sondage n'arbitre que **si quelqu'un sonde**. Une partie dont tous les
joueurs ferment leur navigateur en même temps reste `in_progress`
indéfiniment — plus personne ne la regarde, donc plus personne ne la conclut.
Une tâche périodique fermerait ces parties abandonnées ; elle n'est pas au
programme d'ici le 4 septembre, et aucun affichage ne dépend de leur statut.
