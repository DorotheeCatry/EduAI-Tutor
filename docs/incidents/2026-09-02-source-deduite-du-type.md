# Incident 017 — Une source déduite de son type, et trois conséquences

**Date :** 2 septembre 2026
**Composant :** `data_pipeline/load/chargeur.py`, `data_pipeline/transform/`
**Gravité :** majeure — le chargement de la sixième source était impossible ; deux défauts latents ont été révélés
**Statut :** résolu et vérifié en base
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C4 (E1) ; C3 (E1) ; C1 (E1)

---

## 1. Déclenchement

Le chargement de la sixième source s'est arrêté net :

```
Chargement impossible : Plusieurs sources déclarent le même type : ['scraping'].
Le rattachement d'un document à sa source devient ambigu ; le chargeur doit
être adapté avant de continuer.
```

**Le chargeur avait raison de refuser.** Il rattachait chaque document à sa
source **en déduisant celle-ci de son type** — ce qui suppose une source par
type. S6 est un second scraping : la déduction devenait ambiguë, et le refus
valait mieux qu'un rattachement au hasard.

C'est la même confusion que celle de l'incident 015 quelques heures plus tôt :
**cinq types exigés par C1, transcrits comme un nombre de sources.** Deux
endroits différents du dépôt, la même erreur, le même jour.

## 2. La correction, et pourquoi elle ne consiste pas à lever la garde

Le document porte désormais son `code_source`, tiré du nom du fichier brut
(`s6_documentation_bibliotheques.jsonl` → `s6`) : ce nom désigne l'extracteur
sans ambiguïté, là où le type ne le fait plus.

**La garde n'a pas été levée : la déduction qu'elle protégeait a été
supprimée.** Elle serait redevenue dangereuse à la septième source. Ce qui
subsiste est un repli, employé seulement pour les corpus transformés avant ce
champ, et seulement quand le type désigne une source et une seule.

## 3. Deux défauts latents que cette correction a révélés

`source_par_type` est un dictionnaire **indexé par type**. Depuis que deux
sources partagent « scraping », la seconde y écrase la première : **S2 avait
disparu de ses valeurs**. Deux endroits l'employaient encore.

### Le bilan de S2 rejeté

```
Document écarté — bilan s2 : la source « s2 » n'est pas déclarée dans la table source
Campagnes d'extraction enregistrées : 5
```

S2 est déclarée. Le message était faux, et la conséquence réelle : **cinq
campagnes d'extraction enregistrées au lieu de six**, la traçabilité de S2
perdue pour ce chargement.

### Les documents de S2 hors du marquage des disparus

Plus grave, et invisible. Le marquage des documents retirés d'une source
construisait sa liste par la même carte : le journal disait « tous ceux des
sources s1, s3, s5, s6 ont été revus » — **S2 manquait**.

Un document retiré de la documentation Python serait donc **resté en base,
présenté comme courant**, sans que rien ne le signale. La décision 013 —
marquer plutôt que purger — reposait sur un marquage qui, pour cette source,
ne se serait plus fait.

Constaté : la base portait 235 documents S2 pour 234 dans le corpus. Après
correction, 234, et l'écart s'est refermé de lui-même.

## 4. Vérification

```
s1  1273   s2   234   s3   380   s5  4948   s6  1005      total 7840
6 campagnes · 1 211 mots-clés · 20 544 rattachements · 0 rejet · 0 retiré
```

Les quatre licences de S6 ont trouvé leur code — aucun `SANS_CORRESPONDANCE`
dans le rapport de transformation.

## 5. Ce qu'on en retient

**Une déduction est une hypothèse qui ne se déclare pas.** « La source se déduit
du type » n'était écrit nulle part comme une règle : c'était une commodité, vraie
tant qu'il y avait une source par type. Elle a tenu cinq sources, puis elle a
cassé — et pas seulement là où elle a levé une erreur.

**Ce qui a bien fonctionné : la garde a refusé plutôt que de choisir.** Sans
elle, les 1 005 documents de S6 auraient été rattachés à S2, ou l'inverse, et le
jeu de données aurait été faux sans qu'aucun message ne l'annonce. Une garde qui
bloque un chantier est désagréable ; c'est exactement le jour où elle sert.

**Et la leçon de l'incident 015 se répète : un nombre venu du référentiel ne
doit pas être transcrit sans dire lequel des deux comptes il borne.** Cinq
types de sources n'est pas cinq sources.
