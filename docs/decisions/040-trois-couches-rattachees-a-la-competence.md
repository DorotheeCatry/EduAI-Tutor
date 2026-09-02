# 040 — Trois couches, toutes rattachées à la compétence

**Date :** 2 septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C10 (E3) ; C13 (E3) — quotas

## Le déplacement

Jusqu'ici, l'application produisait un cours à la demande, de bout en bout.
C'est ce qui limitait sa valeur : **un cours engendré entre en concurrence avec
une documentation officielle qui sera toujours meilleure**, et qui est déjà dans
le corpus depuis la sixième source.

Ce chantier déplace le rôle du modèle. Il ne produit plus le contenu : il
produit **la version personnelle d'un contenu existant**. L'apprenant part d'un
cours de référence, l'enrichit là où il bute, et repart avec une fiche que
personne d'autre n'a — parce que personne d'autre n'a buté aux mêmes endroits.

## La décision

**Trois couches, et toutes se rattachent à la compétence, jamais au cours.**

| Couche | Modèle | Propriétaire | Cycle de vie |
|---|---|---|---|
| Cours de référence | `CoursDeReference` | l'organisme | remplaçable |
| Fiche | `FicheDApprenant` | l'apprenant | survit au remplacement |
| Ajouts | `AjoutDeFiche` | l'apprenant | survivent avec elle |

**`FicheDApprenant` ne porte aucune clé étrangère vers un cours.** C'est le
point entier de ce découpage. Une clé étrangère ferait disparaître le travail de
l'apprenant le jour où le formateur publie le sien — l'inverse exact de ce que
le dispositif cherche. Un test le défend, parce que c'est exactement le genre de
lien qu'on ajoute plus tard par commodité.

**`Course` n'est pas remplacé.** Il reste la génération sur sujet libre, hors
référentiel — une entrée parmi trois. L'accueil et la page Référentiel comptent
déjà ses lignes ; le refondre aurait coûté sans rien apporter.

## Chaque ajout porte sa question, pas seulement sa réponse

Un ajout né de « développe cette partie » sur une section qui n'existe plus dans
le cours suivant serait incompréhensible si l'on n'avait gardé que la réponse.
La question survit au cours ; la section, non.

C'est aussi pourquoi `section_visee` est **un texte, pas une clé étrangère** :
elle désigne une section d'un document remplaçable.

## Le quota, et le cas qu'il fallait trancher

**Un enrichissement proposé par le parcours ne décompte rien**, et l'affiche :
« proposé par votre parcours, offert ».

L'apprenant ne l'a pas demandé. Lui voir baisser son compteur sans geste de sa
part est le genre de chose qu'on ne comprend qu'après l'avoir subi deux fois —
et qui fait croire à une fuite.

**Le défaut reste le décompte.** `answer_question(..., sans_quota=False)` : il
faut lever le drapeau pour ne pas payer, jamais l'inverse. Une dépense non
imputée doit être un cas déclaré, pas un oubli — ce projet en a déjà trouvé deux
qui ne l'étaient pas.

Et le décompte reste **au goulot unique de l'orchestrateur**. Le refaire dans la
couche de service aurait rouvert la porte par laquelle ces deux dépenses étaient
passées.

## Conséquences

- Une fiche est créée **à la demande**, au premier enrichissement, et non à
  l'inscription : vingt et une fiches vides diraient à l'apprenant qu'il a
  commencé vingt et un travaux qu'il n'a pas ouverts.
- Les exercices réalisés s'affichent dans la fiche sans rien enregistrer de
  neuf : leur rattachement à la compétence existe depuis la décision 027.
- L'onglet « Course Generator » devient « Cours », à trois entrées. L'entrée
  naturelle vers un cours reste le parcours, depuis l'accueil : ce catalogue
  n'est pas la porte principale.
