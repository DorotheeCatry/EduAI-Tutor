# 016 — Mesurer les modèles avant de décider de leur affectation

**Date :** 28 août 2026
**Compétence visée :** C7 (épreuve E2) — comparaison de services d'IA
**Compétences concernées :** C6 (E2), C10 (E3), C20 (E5)

## Contexte

Le routage des quatre agents vers deux modèles Groq avait été acté en décision
001 sur des considérations générales — un modèle « de qualité » pour Researcher
et Pedagogue, un modèle « rapide » pour Coach et Watcher. Aucune mesure ne
l'étayait. Le référentiel demande une comparaison argumentée de services d'IA.

## Options

1. Justifier après coup le routage existant à partir des traces de production.
2. Écrire un protocole, le commiter, puis mesurer.
3. Faire noter la qualité par un modèle juge, pour automatiser la comparaison.

## Option retenue

**La deuxième**, avec un refus explicite de la troisième.

La première a été écartée parce qu'elle inverse l'ordre du raisonnement : en
partant des traces d'un routage déjà en place, on ne trouve que des critères qui
le confirment. Le protocole — six critères, une grille de notation, cent vingt
appels — a donc été écrit et commité seul, sans un chiffre, dans le commit
`8cb868f`. Les mesures sont arrivées dans un commit distinct. L'historique porte
la séparation ; elle n'est pas seulement affirmée dans le texte.

La troisième a été écartée parce qu'un modèle qui juge d'autres modèles a des
biais documentés — préférence pour les réponses longues, pour son propre style,
pour sa propre famille. Aucun ne serait défendable à l'oral. La qualité est donc
notée à la main, sur une grille écrite avant d'avoir vu une seule réponse, et
présentée sans le nom des modèles.

Aucune pondération n'agrège les six critères en un score unique : le classement
aurait l'apparence de l'objectivité et dépendrait entièrement de coefficients
choisis par le rédacteur. La décision nomme les critères qui l'emportent, agent
par agent.

## Raison

Trois faits mesurés, qu'aucune décision prise sans mesure ne pouvait connaître :

- **`qwen/qwen3.6-27b` est écarté.** Il émet un bloc de raisonnement visible sur
  30 appels sur 30 et ne le referme que 5 fois dans le budget de jetons commun.
  Une mesure complémentaire, à budget quadruplé et clairement étiquetée hors
  protocole, montre qu'il répond alors correctement — mais en consommant 2052
  jetons de sortie contre moins de 420 aux deux autres, pour un contenu rendu de
  longueur comparable. Le surcoût est une propriété du modèle, pas un effet du
  plafond qu'on lui avait imposé. Sans cette vérification, on l'aurait écarté
  par un raisonnement circulaire.

- **Le gros modèle est le plus concis.** `gpt-oss-120b` consomme 356 jetons de
  sortie en moyenne, `gpt-oss-20b` en consomme 416. Le rapport de coût entre les
  deux est donc bien plus resserré que le rapport des tailles ne le laissait
  attendre.

- **Le palier gratuit tient environ dix appels par minute** sur ce jeu de
  prompts. À 0,5 seconde d'intervalle, trois appels sur dix sont refusés ; à six
  secondes, aucun des quatre-vingt-dix. Pour une classe travaillant en même
  temps, la question du palier payant se pose avant celle du choix du modèle.

Le routage de la décision 001 est **confirmé** sur les critères mesurés. Il
n'est pas confirmé sur le critère de qualité, qui attend une notation à la main,
ni sur celui de souveraineté, qui reste sans réponse faute d'un modèle local en
état de marche.

## Conséquences

- La décision 001 n'est pas remplacée : elle est étayée. Le routage ne change pas.
- Deux cases du tableau restent vides et sont signalées comme telles plutôt que
  comblées : la qualité pédagogique et la souveraineté.
- Les montants en dollars restent des ordres de grandeur tant que
  `apps/monitoring/tarifs.json` porte `"a_verifier": true`. Le classement par
  coût vaut par ses rapports, non par ses valeurs.
- Le service Ollama hors d'état est requalifié : ce n'est pas une gêne de
  confort, c'est l'absence du seul repli souverain du projet.

## Détail

`docs/benchmark_modeles.md` — protocole, mesures, décision.
`docs/benchmark/` — mesures brutes, tableaux recalculables, grille de notation.
`benchmark/` — exécuteur et analyseur.
