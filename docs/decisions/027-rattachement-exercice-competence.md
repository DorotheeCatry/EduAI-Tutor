# 027 — Le rattachement d'un exercice à une compétence est choisi, jamais déduit

**Date :** 31 août 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C4 (E1) — intégrité ; C13 (E3) — accessibilité ; C21 (E5)

## Contexte

La progression par compétences suppose de savoir **quelle compétence** un
exercice fait travailler. Or les exercices de ce produit sont engendrés par un
modèle de langage à partir d'un sujet libre, saisi par l'apprenant : « les
listes en python », « fonctions récursives », ce qu'il veut.

Il faut donc établir un lien entre un texte libre et une compétence du
référentiel — et c'est le vrai travail de ce chantier, comme le brief
l'annonçait.

## La question posée avant d'écrire

Le chantier impose de demander, avant tout modèle : **qui appelle ce code, et
par quel chemin l'apprenant y arrive**. Appliquée ici, elle se reformule :

> **Qui remplit ce rattachement, à quel moment, et que voit-on quand il est
> absent ?**

Sans cette question, le piège était visible : ajouter `Exercise.competence`,
nullable, et découvrir plus tard que **tous les exercices l'ont à `NULL`** —
une clé étrangère que rien ne renseigne, quatrième occurrence de la famille C
des motifs du projet, sous une forme particulièrement discrète.

## Options

1. **Déduire la compétence du sujet libre**, par mots-clés déclarés dans le
   référentiel.
2. **Demander au modèle de langage** de classer l'exercice engendré.
3. **Un choix explicite de l'apprenant** au moment de la génération.
4. Un rattachement obligatoire, sans échappatoire.

## Option retenue

**La troisième.** Le formulaire de génération propose les compétences du
référentiel actif, groupées par module, avec une option « Aucune — sujet libre,
hors référentiel » en tête.

## Raisons

**La déduction par mots-clés est écartée parce qu'un rattachement faux est pire
qu'un rattachement absent.** Un exercice sur « les listes » rangé sous
« Manipuler les types de base » ferait progresser une compétence qui n'a pas été
travaillée, et personne ne le verrait : la progression serait fausse et muette.
Un rattachement absent, lui, s'affiche.

**La classification par le modèle est écartée pour la même raison, aggravée.**
Elle est non déterministe, facturée, et le chantier l'exclut explicitement :
« rien de déclaratif, rien d'inféré par le modèle ». Deux générations du même
sujet pourraient tomber dans deux compétences différentes.

**Le rattachement obligatoire est écarté par l'usage.** Un apprenant doit
pouvoir s'exercer sur un sujet hors du référentiel de son organisme. Le rendre
obligatoire fermerait cet usage — ou pousserait à choisir une compétence au
hasard pour passer le formulaire, ce qui reviendrait à fabriquer la donnée
qu'on refuse.

**Le choix explicite n'est pas de la déclaration au sens interdit.** L'apprenant
déclare ce que l'exercice **porte**, pas où il **en est** : sa progression
reste mesurée sur des exercices réussis. C'est la distinction qui sépare cette
option de l'auto-évaluation abandonnée.

## Ce qui rend le choix fiable

Quand une compétence est choisie, **son intitulé devient le sujet transmis au
modèle**. Le sujet de l'exercice et la compétence qu'il vise désignent donc la
même chose par construction, au lieu d'être deux textes qu'on espère
concordants.

## Ce qu'on voit quand le rattachement est absent

C'est la moitié de la décision, et elle est affichée :

> ○ Hors référentiel — ne compte pas dans la progression

Sur la liste comme sur le détail de l'exercice. L'information est portée par le
texte et jamais par la seule couleur : un apprenant daltonien doit la lire.

Le formulaire l'annonce aussi, avant le choix : *« Seuls les exercices rattachés
à une compétence comptent dans votre progression. »*

## Les chemins qui ne rattachent pas, et pourquoi

| Chemin | Rattaché ? | Raison |
|---|---|---|
| Génération depuis la liste des exercices, compétence choisie | **oui** | Le chemin ordinaire |
| Génération depuis la liste, sujet libre | non | Choix de l'apprenant, affiché |
| Génération depuis un cours | non | Part du sujet d'un cours, texte libre ; aucun choix n'y est demandé |
| Exercices créés avant le 31/08/2026 | non | Aucune donnée ne permettrait de les rattacher sans deviner |

Aucun de ces cas n'est rattrapé après coup. Les rattraper supposerait
exactement la déduction que cette décision écarte.

## Conséquences

- `Exercise.competence` : clé étrangère `null=True`, `SET_NULL`. Retirer une
  compétence d'un référentiel ne supprime pas les exercices qui s'y
  rattachaient : ils redeviennent hors référentiel, ce qui est visible et
  exact.
- `apps/referentiel/services.py` : seul chemin d'accès au référentiel actif,
  rendant une liste vide plutôt que de lever quand aucun n'est actif — une page
  d'accueil ne doit pas tomber parce qu'un exploitant a oublié `--activer`.
- Huit tests partant du formulaire réel, dont un qui vérifie que la page
  **propose** les compétences : sans ce menu, la clé étrangère resterait vide
  partout.
- **Reste à faire, à l'étape suivante** : la règle de progression proprement
  dite — combien d'exercices réussis font passer un niveau — et le même
  rattachement pour les quiz, dont la session porte déjà un sujet.
