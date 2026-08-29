# 021 — Le corpus vectoriel embarqué dans l'image, non indexé au démarrage

**Date :** 29 août 2026
**Compétence visée :** C13 (épreuve E3) — livraison et déploiement
**Compétences concernées :** C10 (E3), C17 (E4), C20 (E5)

## Contexte

Le RAG s'appuie sur un corpus vectoriel ChromaDB stocké dans
`apps/rag/chroma` : **21 189 fragments** dans `eduai_corpus_documentaire`,
387 dans `eduai_knowledge_base`, pour **219 Mio sur le disque**.

En local, `docker-compose` monte le dossier de l'hôte dans le conteneur.
Aucun hébergeur ne monte un dossier venu du poste de développement : il faut
décider comment le corpus arrive sur le serveur.

## Options

1. Indexer au premier démarrage, depuis `eduai_data`.
2. Embarquer le corpus dans l'image de conteneur.
3. Provisionner un volume persistant chez l'hébergeur et y téléverser le corpus
   une fois.

## Option retenue

**La deuxième.** Le corpus est copié dans l'image, dans sa propre couche.

## Raisons

**L'indexation au démarrage est écartée par le calcul, pas par principe.**
L'embarquement des fragments passe par le modèle d'embarquement local, à une
vingtaine de fragments par minute sur la machine de développement. 21 189
fragments demandent donc **plus de dix-sept heures**. Aucun démarrage de
conteneur ne peut porter cela : l'hébergeur déclarerait le service défaillant
et le redémarrerait bien avant la fin — indéfiniment, chaque tentative
recommençant à zéro. Ce n'est pas une option lente, c'est une option qui
n'aboutit jamais.

**Le volume persistant est écarté pour son coût d'exploitation, pas pour son
prix.** Il suppose un téléversement manuel de 219 Mio, hors de la chaîne de
livraison, dont rien ne garantit ensuite qu'il corresponde au code déployé. Le
corpus et l'application pourraient diverger sans que rien ne le signale — le
motif exact des cinq incidents déjà documentés par ce projet.

**L'image rend le couple corpus/code atomique.** Un déploiement livre les deux
ensemble ou n'en livre aucun. Il n'y a pas d'état intermédiaire où
l'application tournerait sur un corpus qui n'est pas le sien.

## Le coût, chiffré

| Poste | Effet |
|---|---|
| Taille de l'image | **+219 Mio** par image qui copie le dépôt (application web et service IA) |
| Construction | La copie du corpus est isolée dans sa propre couche, avant celle du code : elle n'est rejouée que si le corpus change, pas à chaque retouche de gabarit |
| Publication au registre | Une couche de 219 Mio à téléverser lors de la première publication, réutilisée ensuite tant que le corpus ne change pas |
| Déploiement | La couche est retéléchargée par l'hébergeur au premier déploiement seulement |
| Exécution | Aucun surcoût : SQLite lit le fichier là où il est |

## Ce que cela impose : la réindexation devient hors ligne

C'est la contrepartie, et elle est ferme. **Le corpus déployé ne peut plus être
modifié sur le serveur.** Toute réindexation — ajout de sources, changement de
modèle d'embarquement, correction de découpage — suit désormais ce chemin :

1. réindexer **sur le poste de développement**, hors ligne, avec le temps que
   cela demande ;
2. reconstruire l'image ;
3. publier la nouvelle image ;
4. redéployer.

Il n'existe aucun raccourci, et c'est délibéré : un corpus modifiable en
production serait un corpus dont plus personne ne saurait dire de quelle
indexation il provient.

Deux conséquences pratiques à connaître avant de s'en étonner :

- **Un déploiement n'actualise pas le corpus** si l'image n'a pas été
  reconstruite après une réindexation. Le fichier date de sa construction.
- **Les écritures de service de SQLite** — journal WAL, verrous — ont lieu dans
  la couche modifiable du conteneur et disparaissent à chaque redémarrage.
  C'est sans conséquence : elles ne portent aucune donnée, seulement l'état
  transitoire du moteur. Elles doivent en revanche être **possibles**, ce qui
  interdit de remonter le corpus en lecture seule (décision 018).

## Conséquences

- `.dockerignore` n'exclut plus `apps/rag/chroma`, avec le motif du
  renversement écrit sur place.
- Le `Dockerfile` de l'application web copie le corpus dans une couche dédiée,
  avant la copie du code.
- En développement, `docker-compose` monte toujours le dossier de l'hôte
  par-dessus : la copie embarquée est masquée et le corpus reste celui du
  disque. Le comportement local est inchangé.
- À consigner dans la documentation de la chaîne de livraison : la réindexation
  est une opération hors ligne, suivie d'une reconstruction d'image.
- **Complément du 29/08, même journée.** Au moment d'écrire cette décision, la
  majeure partie des 219 Mio embarqués n'était lue par aucun chemin de code :
  les cinq points d'accès RAG interrogeaient une collection de 387 fragments,
  pas les 21 189 du pipeline. L'argument du coût tenait donc sur un corpus
  inutilisé. La décision 022 branche la recherche documentaire sur le corpus du
  pipeline ; les 219 Mio servent désormais ce pour quoi ils sont transportés.
