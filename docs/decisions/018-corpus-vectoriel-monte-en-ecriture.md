# 018 — Le corpus vectoriel monté en écriture, faute de pouvoir faire autrement

**Date :** 29 août 2026
**Compétence visée :** C13 (épreuve E3) — sécurité et conteneurisation
**Compétences concernées :** C9 (E2), C10 (E3), C21 (E5)

## Contexte

Le conteneur du service IA montait le corpus vectoriel en lecture seule :

```yaml
- ./apps/rag/chroma:/app/apps/rag/chroma:ro
```

Ce `:ro` n'était pas une valeur par défaut : c'était une protection posée
volontairement. Le service IA **consulte** le corpus, il n'a aucune raison
légitime de le modifier, et le montage en lecture seule transformait cette
règle d'usage en garantie tenue par le noyau — hors d'atteinte d'une
régression, d'une dépendance compromise ou d'une injection.

Elle rendait `/ai/recherche` inutilisable. Chaque appel répondait 503, avec au
journal : `attempt to write a readonly database` (incident `f033fe55185d`,
reproduit le 29/08 sous `88ce29eda658`).

La cause n'est pas dans le code du projet. ChromaDB persiste ses données dans
SQLite, et **SQLite écrit sur son support même pour une lecture** : journal
WAL, fichier de verrous, éventuels index temporaires. Le moteur n'ouvre donc
pas la base du tout. La protection ne dégradait pas la fonction : elle
l'annulait.

## Options

1. Retirer le `:ro` et monter le corpus en écriture.
2. Copier le corpus dans l'image au moment de la construction, et le laisser
   dans la couche accessible en écriture du conteneur.
3. Faire tourner ChromaDB comme service distinct, seul détenteur du volume en
   écriture, le service IA ne l'atteignant plus que par HTTP.

## Option retenue

**La première.** Le montage devient `./apps/rag/chroma:/app/apps/rag/chroma`.

## Raison

La deuxième option ferait entrer 140 Mio dans l'image, à reconstruire à chaque
réindexation, et ferait perdre à chaque redémarrage les écritures de service de
SQLite — sans rien protéger de plus : le processus écrirait alors sur sa propre
couche, tout aussi librement.

La troisième est la bonne réponse d'architecture, et elle reste la cible. Elle
rétablirait la protection en la déplaçant : le service IA n'aurait plus aucun
accès au système de fichiers du corpus, seulement à une API de lecture. Mais
elle ajoute un service à configurer, à surveiller et à déployer, à six jours du
rendu et pendant le chantier de mise en ligne. Ce n'est pas le moment de
l'ouvrir.

## Ce qui est perdu, et pourquoi c'est acceptable ici

La perte est réelle et il faut la nommer : **le conteneur du service IA peut
désormais écrire dans `apps/rag/chroma`.** Un défaut du code ou d'une
dépendance pourrait corrompre ou vider le corpus.

Trois éléments bornent la conséquence, sans l'annuler :

| Élément | Effet sur le risque |
|---|---|
| Le corpus est **reconstructible** par réindexation depuis `eduai_data` | Une corruption coûte du temps de calcul, pas de la donnée |
| Il ne contient **aucune donnée personnelle** — uniquement du contenu documentaire déjà public | Aucune conséquence RGPD |
| Le service **n'expose aucune route d'écriture** vers le corpus | Il n'existe pas de chemin prévu pour l'altérer depuis l'extérieur |

Ce qui reste hors de portée de ces bornes, c'est l'altération non prévue —
précisément ce que le `:ro` couvrait. Le risque est donc accepté, pas éliminé.

## Conséquences

- Le compromis est écrit dans `docker-compose.yml`, à l'endroit du montage, et
  non seulement ici : c'est là qu'on le relira avant de « rétablir » le `:ro`.
- L'incident `2026-08-29-corpus-vectoriel-monte-en-lecture-seule.md` conserve la
  reproduction et la vérification.
- La séparation de ChromaDB en service dédié est notée comme suite possible,
  après la soutenance. Elle rendrait la protection sans casser la fonction.
- **Leçon générale :** une protection qui empêche la fonction qu'elle protège
  n'est pas une protection sévère, c'est une panne. Le montage était en place
  depuis sa création sans qu'aucune recherche n'ait été passée depuis le
  conteneur — la protection n'avait jamais été éprouvée dans les conditions où
  elle servait.
