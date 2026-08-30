# 023 — Le corpus vectoriel sur volume persistant, et l'empreinte qui le rend vérifiable

**Date :** 30 août 2026
**Compétence visée :** C13 (épreuve E3) — livraison et déploiement
**Compétences concernées :** C19 (E5) — chaîne de livraison ; C10 (E3) ; C20 (E5)

**Cette décision révise la décision 021.** Elle en retient le raisonnement et
en renverse la conclusion, pour un fait que la 021 n'avait pas considéré.

## Le fait nouveau

`apps/rag/chroma` est dans `.gitignore` — 219 Mio de corpus vectoriel, produits
hors ligne, jamais versionnés. C'était déjà vrai le 29 août.

Ce qui change, c'est ce qu'on demande maintenant à la chaîne : **publier les
images depuis GitHub Actions**, pour satisfaire le critère C19, qui exige que
l'étape de livraison soit *intégrée et exécutée une fois les étapes de
packaging validées*.

Or une chaîne GitHub Actions part d'un clone du dépôt. Elle ne voit donc jamais
le corpus. Une image qu'elle construit ne peut pas l'embarquer.

Les deux exigences sont incompatibles telles quelles :

| Exigence | Conséquence |
|---|---|
| Corpus embarqué dans l'image (décision 021) | l'image doit être construite là où le corpus existe : le poste |
| Étape de livraison intégrée à la chaîne (C19) | l'image doit être construite là où le corpus n'existe pas : la chaîne |

Un détail le confirme, et il est instructif : le travail `image` de la chaîne
vérifie depuis le 28/08 que le vector store n'est **pas** dans l'image. Ce
contrôle passe à chaque exécution — non parce que l'exclusion fonctionne, mais
parce qu'un clone ne contient pas le corpus. **Un contrôle qui ne peut pas
échouer ne contrôle rien** ; il l'annonçait déjà, personne ne l'avait lu.

## Options

1. Maintenir la 021 : images construites et poussées à la main depuis le poste,
   la chaîne ne publiant rien.
2. Faire du corpus une image de conteneur à lui seul, poussée depuis le poste,
   que les images applicatives recopient à la construction en CI.
3. **Volume persistant chez l'hébergeur, corpus téléversé une fois**, monté par
   les services au démarrage — c'est-à-dire l'option 3 de la décision 021,
   qu'elle avait écartée.

## Option retenue

**La troisième.**

## Raisons

**La première sacrifie le critère.** Une livraison manuelle n'est pas une étape
de chaîne : c'est ce que C19 demande précisément de dépasser. Elle imposerait
en outre de pousser près de cinq gigaoctets depuis une connexion domestique à
chaque livraison.

**La deuxième tient techniquement**, et elle préservait l'atomicité du couple
corpus/code. Elle a été écartée pour deux motifs. Le dépôt est **public** : le
paquet du registre le serait par défaut, et 82 documents du corpus portent une
licence non vérifiée (décision 020) — leur redistribution ouverte créerait une
obligation que ce projet a justement décidé de ne pas prendre. Et elle ajoute
un artefact, un tag et une étape de plus à comprendre, six jours avant le
rendu, pour un gain qui se traite autrement.

**La troisième découple ce qui a des rythmes différents.** Le code change
plusieurs fois par jour ; le corpus change quand une réindexation hors ligne
aboutit, c'est-à-dire rarement, et jamais depuis la chaîne. Les faire voyager
ensemble oblige à retransporter 219 Mio à chaque correction de gabarit.

## L'objection de la décision 021, et sa réponse

La 021 écartait le volume en une phrase, et elle avait raison de s'en méfier :

> Il suppose un téléversement manuel de 219 Mio, hors de la chaîne de
> livraison, dont rien ne garantit ensuite qu'il corresponde au code déployé.
> Le corpus et l'application pourraient diverger sans que rien ne le signale —
> le motif exact des cinq incidents déjà documentés par ce projet.

L'objection est juste et elle n'est pas levée : **avec un volume, corpus et
code ne sont plus atomiques.** Ce qui change, c'est qu'une divergence cesse
d'être silencieuse.

Le corpus porte désormais une **empreinte** — `apps/rag/chroma/EMPREINTE.json`,
produite par `apps/rag/empreinte_corpus.py` — qui relève la date d'indexation,
la somme SHA-256 de `chroma.sqlite3`, le modèle d'embarquement, et le décompte
de fragments de chaque collection. Elle est téléversée avec le corpus, et
`/ai/sante` la restitue.

Deux conséquences concrètes :

- un corpus réindexé mais non téléversé se voit : la sonde annonce une date et
  un décompte qui ne sont pas ceux du poste ;
- un volume vide ou mal monté se voit aussi : la sonde passe en `degrade`, ce
  qu'elle faisait déjà pour un corpus absent.

**Ce que cela ne fait pas :** empêcher la divergence. Cela la rend constatable
en une requête, ce qui est le maximum qu'un dispositif découplé puisse offrir.
La procédure de mise à jour du corpus, dans `docs/chaine_livraison.md`, se
termine par cette vérification.

## Ce qui reste vrai de la décision 021

Tout le reste, et notamment ce qui n'avait rien à voir avec le transport :

- **La réindexation demeure hors ligne.** Dix-sept heures d'embarquement ne
  tiennent pas dans un démarrage de conteneur, quel que soit l'endroit d'où
  vient le corpus. C'était l'apport principal de la 021, il est intact.
- **Le corpus est monté en écriture** (décision 018) : SQLite écrit son journal
  WAL et ses verrous, faute de quoi la moindre lecture échoue.
- **Un déploiement n'actualise pas le corpus.** Il ne le faisait pas davantage
  quand il fallait reconstruire l'image.

## Conséquences

- `.dockerignore` exclut de nouveau `apps/rag/chroma`. C'est le second
  renversement de cette ligne en deux jours ; le commentaire sur place porte
  les deux dates et les deux motifs, plutôt qu'un seul état sans histoire.
- Les images perdent 219 Mio chacune, et la chaîne peut les construire.
- Le contrôle « le vector store n'est pas dans l'image » du travail `image`
  reprend un sens : il redevient capable d'échouer si une exclusion se perd,
  au moins pour une construction lancée depuis un poste où le corpus existe.
- Les deux services montent le volume sur `apps/rag/chroma` — chemin écrit en
  dur dans quatre modules, non paramétré, et qu'il n'est pas question de rendre
  configurable six jours avant le rendu.
- Le volume est **partagé par les deux services** s'ils tournent dans le même
  projet d'hébergement ; à défaut, il est téléversé deux fois. La question se
  tranche au provisionnement, elle est documentée dans la chaîne de livraison.
