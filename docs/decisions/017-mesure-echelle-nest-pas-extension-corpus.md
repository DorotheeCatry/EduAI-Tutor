# 017 — Une mesure de passage à l'échelle n'étend pas le corpus

**Date :** 28 août 2026
**Compétence visée :** C2 (épreuve E1), C4 (épreuve E1)
**Compétences concernées :** C1 (E1), C21 (E5)

## Contexte

La conversion Spark du dump Stack Overflow complet — 99 118,6 Mio de
`Posts.xml` — a abouti le 28 août en 43 min 32 s et retenu **355 113
documents**. Le corpus S5 du projet, issu du dump Data Science, en compte
**4 948**.

Le fichier produit était donc immédiatement chargeable, et rien n'empêchait de
le verser dans `eduai_data`.

## Options

1. Charger les 355 113 documents : le corpus passe de 6 836 à environ 186 000.
2. Conserver le corpus S5 tel quel et traiter la mesure comme une preuve.
3. Charger un échantillon des 355 113, pour « profiter » du travail.

## Option retenue

**La deuxième.** Le corpus S5 reste celui de Data Science.

## Raison

La conversion du dump complet répond à une question de **performance** — la
requête réécrite tient-elle à grande échelle ? — et non à une question de
**contenu**. Sa réponse est un chiffre : 45,75 Mio/s, 384 fois la version
initiale. Ce chiffre est la preuve attendue pour C2.

Charger le résultat confondrait deux choses distinctes. Le corpus serait
multiplié par cinquante-trois, ce qui n'est pas un ajustement mais **un
changement de produit** : volumétrie de la base, temps d'indexation dans le
vector store, équilibre entre les cinq sources, coût d'embarquement, pertinence
des recherches — tout serait déplacé. Or aucune de ces conséquences n'a été
évaluée, et aucun besoin ne les demande.

**Un artefact de mesure ne devient pas un livrable parce qu'il existe.** C'est
la formulation générale du principe, et elle vaut au-delà de ce cas.

La troisième option est écartée pour la même raison, aggravée : un échantillon
choisi après coup, sans critère écrit avant, introduirait dans le corpus un
biais de sélection dont on ne saurait plus rendre compte.

## Conséquences

- Le corpus S5 reste à 4 948 documents ; le corpus total à 6 836.
- Le résultat du dump complet vit hors du dépôt, dans
  `/media/apprenant/Stockage/eduai-data/sorties-complet/`. Il n'est ni versionné
  ni chargé. Les mesures qui en découlent sont, elles, consignées : incident
  `2026-08-28-conversion-spark-non-scalable.md`, § 5.4 et 5.5.
- **Un garde-fou est posé dans l'extracteur** : traiter un dump autre que celui
  de référence sans `--sortie` est désormais refusé, avec le code de retour 2.
  Le fichier de sortie et le bilan étant nommés d'après l'extracteur et non
  d'après le dump, l'écrasement silencieux du corpus était possible — et il
  s'est produit deux fois. Une consigne dans une aide en ligne se relit ; une
  erreur de commande à minuit ne se relit pas.
- Si l'extension du corpus devenait souhaitable, elle ferait l'objet d'une
  décision propre, avec son évaluation d'impact. Elle n'est pas exclue ; elle
  n'est pas décidée.
