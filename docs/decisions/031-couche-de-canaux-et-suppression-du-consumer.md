# 031 — Le multijoueur reste en sondage HTTP, et le serveur WebSocket est supprimé

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — déploiement ; C21 (E5) ; C20 (E5)

## Ce que l'inventaire a trouvé

Le chantier partait d'une prémisse : le quiz multijoueur serait « un serveur
sans client ». L'inventaire l'a corrigée.

| Implémentation | Client | Écrit en base | État |
|---|---|---|---|
| Consumer WebSocket, 465 lignes, boucle de jeu complète | **aucun** | jamais exécuté | code mort |
| Sondage HTTP, toutes les 2 secondes | oui | **oui** | fonctionne |

`room_detail.html` interroge `/quiz/api/room/<code>/status/`,
`multiplayer_game.html` interroge `/quiz/api/room/<code>/quiz/` et y poste les
réponses. Cette voie crée les réponses, calcule les points, met à jour les
scores et fait avancer la partie.

**Il ne manquait donc pas un client : il existait deux implémentations
parallèles du même jeu, dont une seule était atteinte.**

Une seconde affirmation du brief a été vérifiée et corrigée : le consumer
n'appelait plus l'orchestrateur « sans utilisateur ». Il impute la génération à
`room.host` depuis le commit `ff13de7` du 28/08.

## Options

1. **Garder le sondage HTTP** et supprimer le consumer.
2. **WebSocket + Redis déployé** — rouvre la décision 020, ajoute un service.
3. **WebSocket en local seulement**, multijoueur documenté comme non déployé.

## Option retenue

**La première.**

## Raisons

**Le sondage fonctionne, et il écrit en base.** Remplacer du code éprouvé par
du code jamais exécuté, à quatre jours du rendu, c'est échanger du connu contre
de l'inconnu.

**Le sondage n'a aucune dépendance d'infrastructure.** Il traverse plusieurs
travailleurs, ne demande ni Redis ni couche de canaux, et se déploie tel quel.
`InMemoryChannelLayer` ne fonctionne que dans un processus unique ;
`channels-redis` est déclaré et inutilisé ; Redis n'est pas déployé
(décision 020).

**Le vrai défaut du multijoueur n'était pas sa latence de deux secondes.**
C'était qu'il ne mesurait pas le temps honnêtement, n'enregistrait aucune
erreur et ne se rattachait à aucune compétence. Redis aurait résolu un problème
que personne n'avait, et le temps passé dessus aurait été pris sur ces trois-là.

**L'option 3 est celle qui a été écartée le plus fermement.** Deux
comportements selon l'environnement est exactement la famille A du registre des
motifs — « vérifié dans un contexte, employé dans un autre » — que ce projet a
payée trois fois en une semaine.

## La suppression, et pourquoi elle n'est pas un détail

`apps/quiz/consumers.py` et `apps/quiz/routing.py` sont **supprimés**, et le
routage WebSocket retiré de `asgi.py`.

Les laisser dormir aurait été pire que les écrire. **465 lignes de code jamais
exécuté sont une invitation à croire qu'une fonctionnalité existe** — et ce
projet a déjà payé cette croyance : la chaîne d'enregistrement du quiz solo
était écrite, routée, complète, et n'était appelée par personne (incident 010).
Les tests écrits pour la brancher ont révélé qu'elle aurait échoué de trois
façons si elle avait tourné un jour.

C'est la **famille C sous sa forme la plus coûteuse** : non pas un chemin
oublié, mais **deux implémentations parallèles du même jeu**, dont l'une
attirait le regard — un consumer complet, moderne, avec sa boucle de jeu — et
dont l'autre, moins flatteuse, était celle qui tournait.

Un lecteur du dépôt, jury compris, aurait conclu de la présence du consumer que
le multijoueur fonctionne en temps réel. Il fonctionne, mais autrement.

Le fichier reste dans l'historique Git : rien n'est perdu, et le jour où Redis
sera déployé, `git show` le rendra.

## Ce que ce choix laisse ouvert

**La latence de deux secondes** entre la réponse du dernier participant et le
passage à la question suivante. Perceptible, sans conséquence sur l'équité :
le temps de réponse est mesuré par le serveur depuis l'affichage de la
question, pas depuis le sondage.

**Une requête par client toutes les deux secondes.** Pour une partie de dix
personnes, cinq requêtes par seconde — négligeable au regard d'une génération
de quiz.

## Conséquences

- `consumers.py` et `routing.py` supprimés ; `asgi.py` ne sert plus que HTTP,
  tout en restant ASGI — le déploiement lance `uvicorn`, et passer à WSGI
  ferait taire un jour une fonctionnalité asynchrone sans le dire.
- `channels-redis` reste déclaré dans les dépendances et inutilisé. À retirer
  après le 14 septembre, avec `channels` si plus rien ne l'emploie.
- La décision 020 n'est pas rouverte : Redis reste hors périmètre, et la raison
  qu'elle donnait — « le seul consommateur WebSocket n'a aucun client » — est
  désormais close par la suppression du consommateur lui-même.
- Quatre corrections accompagnent ce choix sur la voie retenue : horodatage
  serveur, erreurs enregistrées, rattachement au référentiel, présence des
  participants.
