# 042 — Les supports de cours entrent au dépôt, les ressources restent dehors

**Date :** 2 septembre 2026
**Compétence visée :** C19 (épreuve E5) — traçabilité et reproductibilité
**Compétences concernées :** C17 (E4) ; C4 (E1) — licences ; C1 (E1)

## Contexte

L'import des cours de référence (`importer_cours`) lit deux choses : les
supports markdown de `data/contents/courses/` et l'index qui les range en
sous-modules. **Ni l'un ni l'autre n'était versionné** : `.gitignore` excluait
`data/` en entier, et `data/contents` n'avait jamais été suivi.

**Un import qui ne peut pas s'exécuter sur un clone neuf est une preuve
inaccessible.** La chaîne d'intégration applique déjà ce principe pour le
schéma de la base — elle le rejoue depuis zéro à chaque exécution, avec ce
commentaire : *« un schéma qui ne se crée plus depuis zéro n'est pas
reproductible, et le jury doit pouvoir monter le projet à partir du seul
dépôt »*. Le corpus de cours relevait de la même exigence et y échappait.

## La décision

| Répertoire | Poids | Versionné |
|---|---|---|
| `data/contents/courses/` | 2,0 Mo | **oui** |
| `data/contents/index/` | 12 Ko | **oui** |
| `data/contents/resources/` | 93 Mo | non |
| `data/raw/`, `data/processed/` | 21 Mo | non — sorties du pipeline |

Git ne peut pas réinclure un fichier dont un répertoire parent est exclu : ce
sont donc les **contenus** de `data/` qui sont exclus, et les deux répertoires
retenus réinclus explicitement.

## Pourquoi `resources` reste dehors, et ce n'est pas qu'une question de poids

Quatre-vingt-treize mégaoctets suffiraient à hésiter. Ce n'est pas la raison
principale.

**Ces fichiers portaient la licence `A_VERIFIER`** — et ils ne la portent
plus. La vérification a été faite le 04/09/2026, en lisant les fichiers
eux-mêmes puis les conditions de leurs éditeurs.

**Dix-neuf des vingt-deux sont des aides-mémoire de DataCamp** : leur première
page porte la mention « Learn … online at www.DataCamp.com ». Ils sont
librement téléchargeables sur le site de l'éditeur, et ses conditions
d'utilisation accordent un usage personnel et non commercial en interdisant
expressément la reproduction et la redistribution. Ils portent donc la licence
`DATACAMP`, avec `redistribution_autorisee = FALSE`.

**Un vingtième vient de `gto76/python-cheatsheet`**, dont le dépôt ne déclare
aucune licence — l'API de GitHub rend `license: null`. En droit d'auteur,
l'absence de licence n'est pas une permission : c'est la réservation de tous
les droits. Il porte la licence `SANS-LICENCE`, distincte de `A_VERIFIER` à
dessein — la première dit « on a cherché et il n'y a rien », la seconde « on
n'a pas encore cherché ». Les confondre effacerait le travail de vérification.

**Gratuit à télécharger n'est pas libre de droits.** C'est la distinction que
cette vérification inscrit dans la base, et c'est elle qui justifie que
`resources/` reste hors du dépôt : le poids n'était que la raison secondaire.


Les supports de cours, eux, sont écrits par l'organisme : leur origine est
claire, et les verser au dépôt ne redistribue rien qui ne lui appartienne.

## Ce que le versionnement rend visible

Un clone neuf peut désormais lancer `importer_cours` et obtenir les sept cours
de référence. Il rend aussi visible un état qui ne l'était pas :

| Module du référentiel | Supports |
|---|---|
| `01_python` | **42 fichiers** |
| `03_sql` | 1 fichier `.pptx`, sans index |
| Les neuf autres | **aucun** |

**Sept compétences sur vingt et une ont un cours ; quatorze n'en ont pas.**

**Ce n'est pas un manque du dispositif, c'est un arbitrage de délai.** Les
supports des dix autres modules n'ont pas été écrits, et le pipeline les
ingérerait sans la moindre modification : le rattachement se déclare dans le
fichier de correspondance, l'import est idempotent, et rien dans le code ne
suppose que seul le module Python existe. Ce qui manque est du contenu
pédagogique, pas un mécanisme.

C'est précisément la situation que le double statut de la décision 041 prévoit :
un cours provisoire donne de quoi commencer, en disant clairement ce qu'il est,
en attendant que le formateur publie le sien. Les quatorze compétences sans
support ne sont donc pas des impasses — elles sont l'état d'attente que ce
mécanisme a été conçu pour couvrir.

Le versionnement ne crée pas ce manque — il le rend constatable depuis le
dépôt, au lieu de dépendre de ce qu'il y a sur une machine.

## Conséquences

- `docs/provenance-ressources.md` reçoit une entrée pour les supports de cours,
  et une pour `resources` — déclaré comme non redistribué, avec son motif.
- Le dépôt passe d'environ 24 à 26 Mo.
- Les sorties du pipeline (`data/raw`, `data/processed`) restent dehors : ce
  sont des artefacts reproductibles, pas des sources.
