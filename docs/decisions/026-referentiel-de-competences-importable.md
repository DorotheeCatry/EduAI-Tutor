# 026 — Le référentiel de compétences est une donnée, jamais du code

**Date :** 31 août 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C4 (E1) — modélisation et chargement ; C13 (E3) — accessibilité ; C19 (E5)

## Contexte

La progression par compétences suppose un cadre : quelles compétences,
regroupées comment, atteintes à quels paliers. Ce cadre appartient à
l'organisme de formation, pas au produit — et le produit doit pouvoir servir un
autre organisme sans être modifié.

## Options

1. **Des constantes dans le code**, ou une migration de données.
2. **Des fixtures Django** (`loaddata`).
3. **Un fichier importé par une commande dédiée**, avec validation.
4. Un appel à une API de l'organisme.

## Option retenue

**La troisième.** Trois modèles — `Referentiel`, `Module`, `Competence` — et une
commande `importer_referentiel` qui charge un fichier JSON.

## Raisons

**Les constantes rendent l'argument de généricité invérifiable.** Tant qu'un
intitulé de compétence vit dans un gabarit ou une constante, « un autre
organisme charge son référentiel » est une affirmation, pas une propriété. Un
test le vérifie désormais : il échoue si un intitulé du référentiel livré
apparaît dans un fichier Python ou un gabarit.

**Les fixtures ne valident rien.** `loaddata` accepte ce qu'on lui donne et
écrit clé primaire par clé primaire ; un rechargement duplique ou écrase selon
l'humeur des identifiants. La commande, elle, valide **tout le fichier avant la
première écriture** — un import qui échoue au milieu laisserait un référentiel
amputé dont personne ne saurait qu'il l'est, motif de l'incident 001.

**L'API de l'organisme est écartée par le cadre.** Le produit ne connaît aucun
organisme tiers, et en dépendre à l'exécution ferait tomber la page d'accueil
avec lui.

## JSON, et pas YAML

Le chantier autorisait « JSON ou YAML ». **JSON seul est retenu.** `pyyaml`
n'est présent dans l'environnement que par transitivité, à travers les
dépendances de LangChain : s'en servir reviendrait à s'appuyer sur une
dépendance non déclarée, qui disparaîtrait au premier ménage de verrou. La
déclarer serait une dépendance de plus à quatre jours du rendu, que le cahier
des charges écarte.

Un fichier YAML se convertit en JSON en une commande, et le format d'entrée
n'est pas ce que ce référentiel démontre.

## Trois niveaux, dont les libellés sont modifiables

L'échelle du produit est « imiter, adapter, transposer ». Un référentiel importé
peut la **renommer** — le fichier porte un champ `niveaux` — mais pas la
rallonger : le nombre est fixé à trois.

**C'est une limite, et elle est assumée.** La règle de progression et
l'affichage sont bâtis sur exactement trois paliers ; les rendre variables
supposerait de rendre variables la règle et l'interface. Un organisme dont
l'échelle compte quatre paliers devra modifier le code.

Le libellé n'est pas décoratif : c'est lui qui permet de ne pas distinguer les
niveaux par la seule couleur, exigence d'accessibilité du chantier.

## Le fichier fait autorité

Ce qu'il ne contient plus est **supprimé** de la base. Conserver les compétences
retirées ferait cohabiter ce que l'organisme maintient et ce qu'il a abandonné,
sans qu'on puisse les distinguer.

L'identité est le `code`, jamais la clé primaire : relancer le même import ne
duplique rien. Le référentiel se corrige et se recharge, comme le pipeline de
données du bloc 1.

## Un seul référentiel actif, garanti par la base

Plusieurs référentiels coexistent — remplacer en supprimant effacerait la
progression rattachée à l'ancien. Un seul est actif, et c'est une
`UniqueConstraint` conditionnelle qui l'impose, non une convention de code :
une convention se contourne par l'administration, un shell ou un import
concurrent.

Un import sans `--activer` laisse le référentiel inactif, **et la commande
l'écrit** : un référentiel chargé mais invisible serait exactement la donnée
présente et sans effet que ce projet documente.

## Qui appelle ce code, et par quel chemin

La question a été posée **avant** d'écrire les modèles, comme le chantier
l'exige — un référentiel importable que rien n'affiche serait la quatrième
occurrence de la famille C.

| Consommateur | Chemin | Disponible |
|---|---|---|
| Commande d'import | ligne de commande, exploitant | **maintenant** |
| Administration Django | `/admin/`, personne autorisée | **maintenant** |
| Tests | commande réelle sur le fichier réellement livré | **maintenant** |
| Bloc « où j'en suis » de l'accueil | apprenant, première page après connexion | étape 4 |
| Bloc « ce que je fais maintenant » | apprenant | étape 4 |
| Page Performance | apprenant | étape 4 |

**Ce que cela veut dire honnêtement :** entre cette étape et l'étape 4, le
référentiel n'a aucun consommateur côté apprenant. L'administration lui en
donne un côté exploitant, ce qui n'est pas rien mais ne suffit pas. Si l'étape 4
ne se faisait pas, ces modèles seraient du code écrit, joignable et jamais
appelé — et il faudrait alors les retirer plutôt que les laisser dormir.

## Conséquences

- `apps/referentiel/` : trois modèles, une commande, une administration en
  lecture seule sur ce qui vient du fichier — l'éditer ferait diverger la base
  de sa source, et le prochain import écraserait la retouche sans le dire.
- `apps/referentiel/donnees/eduai-2026.json` : le référentiel livré, **4 modules
  et 21 compétences**, établi sur les modules du corpus du projet et sur celui
  d'aucun organisme tiers.
- Quinze tests, partant de la commande réelle sur le fichier réellement livré.
- Le rattachement d'un exercice ou d'un quiz à une compétence n'est pas ici :
  c'est l'étape suivante, et c'est le point où la famille C guette le plus.
