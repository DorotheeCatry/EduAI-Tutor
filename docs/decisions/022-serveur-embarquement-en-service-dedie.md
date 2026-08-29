# 022 — Un service d'embarquement dédié, et le corpus enfin interrogé

**Date :** 29 août 2026
**Compétence visée :** C13 (épreuve E3) — déploiement
**Compétences concernées :** C9 (E2), C10 (E3), C1 à C4 (E1)

## Contexte

Deux constats faits en préparant le déploiement, liés par le même composant.

**Premier constat : le RAG ne pouvait pas fonctionner hors du poste de
développement.** Chaque recherche embarque la requête avant de chercher dans le
corpus, et cet embarquement est fait par Ollama. `apps/rag/utils.py` figeait
l'adresse à `localhost:11434` — exact sur la machine de développement, faux
partout ailleurs. Chez l'hébergeur, il n'y a rien sur la boucle locale.

Le point dur n'est pas l'adresse, corrigée en une ligne : c'est que **le corpus
a été indexé avec `mxbai-embed-large`**. Interroger ces vecteurs avec un autre
modèle ne donne pas de moins bons résultats — il en donne des dénués de sens,
les deux espaces vectoriels n'ayant aucun rapport. Le modèle d'embarquement
n'est donc pas un réglage : c'est une contrainte posée par l'indexation.

**Second constat : le corpus du pipeline n'était lu par personne.** Le vector
store porte deux collections. `eduai_knowledge_base` compte 387 fragments issus
des supports de formation ; `eduai_corpus_documentaire` en compte **21 189**,
produits par les cinq sources du pipeline (C1 à C4) et filtrés par licence.

Les cinq chemins RAG du projet — chercheur, pédagogue, service IA,
`/ai/recherche`, sonde de santé — interrogeaient tous la première. Les 21 189
fragments étaient produits, versionnés, embarqués dans l'image, et jamais
ouverts.

## Options — l'embarquement en production

1. Un service d'embarquement dédié chez l'hébergeur.
2. Ollama installé dans la même image que l'application.
3. Déployer sans RAG, en s'appuyant sur le repli direct au modèle.

## Option retenue

**La première.** Un troisième service, sur une image dérivée d'`ollama/ollama`
avec le modèle embarqué à la construction.

## Raisons

Installer Ollama dans l'image applicative ferait passer celle-ci de 5,7 à
environ 7 Gio, **deux fois** — l'application web et le service IA en ont tous
deux besoin — et mettrait deux processus dans un conteneur, dont l'un
redémarrerait silencieusement l'autre en cas de panne.

Déployer sans RAG était l'option gratuite, et c'est ce qui la rend tentante.
Elle a été écartée parce que le repli existant appelle le modèle sans aucune
source : les cours seraient générés, ils ne seraient plus documentés. Le RAG
est le cœur de C10 ; le retirer de la démonstration publique reviendrait à
démontrer autre chose que ce qui est évalué.

Le service dédié coûte un service de plus à provisionner et à payer. En
échange, aucune ligne de code applicatif ne change, aucune réindexation n'est
nécessaire, et le modèle est figé dans une image versionnée.

## Le modèle est téléchargé à la construction

`ollama pull` a lieu dans le `Dockerfile`, pas au démarrage. Un téléchargement
au premier démarrage ferait échouer la première recherche de chaque
déploiement, le temps que 670 Mio arrivent — et échouerait tout court si le
registre amont était indisponible ce jour-là. Construit dans l'image, le modèle
est là, ou l'image n'existe pas.

La version d'Ollama est figée à `0.32.15`, celle du poste sur lequel le corpus
a été indexé, et non `latest`.

## Le corpus documentaire devient celui de la recherche

`/ai/recherche` interroge désormais `eduai_corpus_documentaire`. Les agents
Django — chercheur et pédagogue — restent sur `eduai_knowledge_base`.

**Ce sont deux questions différentes.** « Que dit la documentation sur les
listes ? » appelle le corpus collecté. « Quel contexte donner au Pédagogue pour
composer un cours ? » appelle les supports de formation, qui suivent le
programme. Les confondre reviendrait à faire composer les cours à partir de
fils Stack Overflow.

**Mesuré, pas supposé.** Sur la requête « les listes en python », les distances
des trois meilleurs fragments :

| Collection | Distances | Contenu rendu |
|---|---|---|
| `eduai_corpus_documentaire` | 0,286 — 0,290 — 0,293 | Documentation Python, fil Stack Overflow avec réponse acceptée |
| `eduai_knowledge_base` | 0,600 — 0,606 — 0,633 | Supports de formation |

Le corpus collecté répond mieux, et il rend visible ce que le pipeline du Bloc 1
produit : un jury qui interroge `/ai/recherche` voit les cinq sources à
l'œuvre, au lieu d'un corpus de 387 fragments sans rapport avec le pipeline.

La sonde `/ai/sante` annonçait le nom de l'autre collection, en dur. Elle
décrivait donc un corpus que la recherche n'interroge pas — le projet a déjà
documenté ce que coûte un instrument qui décrit autre chose que le service
rendu (incident 003). Elle est corrigée.

## Conséquences

- Trois images à publier : application web, service IA, serveur d'embarquement.
- `OLLAMA_BASE_URL` devient obligatoire en production, sur les deux services
  applicatifs. Sa valeur par défaut reste la boucle locale, qui est juste en
  développement.
- Le service d'embarquement **ne doit recevoir aucun domaine public** : il n'a
  ni authentification ni limitation de débit, et n'en a pas besoin tant qu'il
  reste sur le réseau privé de l'hébergeur.
- Le corpus embarqué dans l'image (décision 021) cesse d'être un poids mort :
  ses 219 Mio servent désormais la recherche.
- Reste à mesurer : la latence d'embarquement sur le processeur de l'hébergeur.
  Sur le poste de développement, 3,67 s au premier appel puis 0,07 s ensuite.
