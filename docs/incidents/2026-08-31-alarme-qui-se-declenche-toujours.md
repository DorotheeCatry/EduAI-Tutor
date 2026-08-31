# Incident 009 — Une alarme qui se déclenche toujours est une alarme qu'on cesse de lire

**Date :** 30–31 août 2026
**Composant :** `apps/rag/empreinte_corpus.py`
**Gravité :** moyenne — le dispositif de contrôle était inexploitable ; aucun impact sur le service
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — livraison ; C20 (E5) — monitorage ; C10 (E3)

---

## 1. Déclenchement

**31/08, au premier transfert réel du corpus vers l'hébergeur.** Le contrôle
d'empreinte, écrit la veille précisément pour cette occasion, signale une
divergence :

```
poste    : bc6f07c1c0265ae56969f4e0edc2ab3573ed327a5c588c64f06ff5409f921a12
volume   : bc6f07c1c0265ae56969f4e0edc2ab3573ed327a5c588c64f06ff5409f921a12
attendue : 91c13a224db16436ffb05c563c8814ad2ffcad857db6f50516bf60c86628abde
```

Le fichier téléversé est **rigoureusement identique** à celui du poste — le
transfert est parfait. Et **aucun des deux** ne correspond à l'empreinte
enregistrée la veille dans `EMPREINTE.json`.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Corpus vectoriel | **aucun** — 21 189 et 387 fragments intacts, transfert exact |
| Service rendu | **aucun** — la recherche fonctionne |
| Dispositif de contrôle | **inexploitable** : il signale une divergence à chaque relevé |
| Décision 023 | Son unique contre-mesure ne tenait pas |

Ce dernier point est le vrai dommage. La décision 023 a fait voyager le corpus
hors de l'image — donc renoncé à l'atomicité corpus/code — **contre la promesse
qu'une divergence serait constatable**. L'instrument qui portait cette promesse
était faux.

---

## 3. Diagnostic

### 3.1 Écarter la cause évidente

Le corpus a-t-il changé entre le relevé et le transfert ? Non : les décomptes
sont identiques (21 189, 387), et le fichier du volume est au bit près celui du
poste. Rien n'a été réindexé.

### 3.2 Ce qui change sans que le corpus change

L'empreinte portait sur les **octets de `chroma.sqlite3`**. Or SQLite réécrit
son fichier à la simple lecture : pages de journal, compteurs internes, état du
moteur. Les recherches de vérification passées la veille sur le service local —
et le fait même de lire le corpus pour le mesurer — suffisent à modifier ces
octets.

La démonstration est immédiate. Deux relevés consécutifs, sans rien toucher au
corpus :

| Relevé | Empreinte du contenu | Empreinte des octets |
|---|---|---|
| 1 | `02183943…` | `a8406778…` |
| 2 | `02183943…` | `0693dc56…` |

**Le seul fait de mesurer changeait la mesure.**

### 3.3 Cause racine

Une confusion entre deux questions que le dispositif ne distinguait pas :

- « est-ce le même **fichier** ? » — utile juste après un transfert ;
- « est-ce le même **corpus** ? » — la seule qui intéresse le déploiement.

L'empreinte répondait à la première en prétendant répondre à la seconde.

### 3.4 Ce qui rend cet incident particulier

**Le module écartait explicitement ce travers, et le commettait deux lignes plus
loin.** Sa docstring justifiait de ne pas hacher les répertoires d'index :

> les répertoires d'index binaires accompagnant les collections sont réécrits
> par ChromaDB à des moments qui ne correspondent pas à un changement de
> contenu ; les inclure produirait une empreinte qui change sans que le corpus
> change, **donc une alerte à laquelle plus personne ne prêterait attention**.

Le raisonnement était juste. Il n'a simplement pas été appliqué à `chroma.sqlite3`,
qu'on supposait stable parce qu'on ne l'écrit pas — en oubliant que SQLite,
lui, l'écrit.

---

## 4. Résolution

L'empreinte porte désormais sur le **contenu logique** : les identifiants de
fragments de chaque collection, triés puis hachés, puis composés en une
empreinte globale dans un ordre fixe.

Trois propriétés, chacune éprouvée par un test :

| Propriété | Pourquoi elle est nécessaire |
|---|---|
| Stable entre deux lectures | Sans quoi l'alarme se déclenche toujours — le défaut corrigé |
| Indépendante de l'ordre de lecture | Rien ne garantit que ChromaDB rende ses identifiants dans le même ordre |
| Change si un fragment est ajouté | Sans quoi comparer ne prouve rien |

La somme des octets est conservée sous `empreinte_fichier`, à sa juste place :
elle répond à « est-ce le même fichier ? », question réellement utile juste
après un transfert, et c'est ainsi qu'elle a servi le 31/08 pour confirmer que
le téléversement était exact.

---

## 5. Tests en succès

| Vérification | Résultat |
|---|---|
| Deux relevés consécutifs, corpus inchangé | **empreinte logique identique**, empreinte des octets différente |
| `/ai/sante` sur le service déployé | rend l'empreinte, `02183943…` |
| Comparaison poste / serveur par le script de vérification | **« l'empreinte déployée est celle du poste »** |
| Suite de tests | 120 passés, dont 9 sur l'empreinte |

---

## 6. Ce que cet incident ajoute

C'est le troisième incident de ce projet portant sur un **instrument** et non
sur le service : la sonde de monitorage branchée sans effet (003), les tests
qui n'avaient jamais tourné dans les conditions de la chaîne (007), et
maintenant une empreinte qui mesurait la mauvaise chose.

Mais celui-ci se distingue des deux autres. La sonde ne produisait rien ; les
tests n'avaient jamais été exécutés. **Ici, l'instrument fonctionnait
parfaitement** : il produisait une valeur, à l'heure, sans erreur, et cette
valeur était vraie. Elle répondait simplement à une autre question que celle
qu'on lui posait.

**La leçon :** vérifier qu'un instrument produit une valeur ne dit rien de ce
qu'il mesure. Un contrôle dont l'alarme se déclencherait à chaque exécution est
pire qu'un contrôle absent — l'absence se remarque, tandis qu'une alarme
permanente s'apprend, et l'on finit par la traiter comme le bruit de fond d'un
système en bon état.

Le corollaire pratique tient en une question, à poser avant d'écrire tout
contrôle : **qu'est-ce qui doit rester constant pour que ce contrôle reste
silencieux ?** Si la réponse contient quoi que ce soit qui bouge sans que
l'objet surveillé change, le contrôle est à réécrire.

---

## 7. Reste à faire

- Rien sur ce dispositif : il est corrigé, éprouvé, et il a servi le jour même
  à valider le transfert du corpus vers les deux volumes.
- La même question — « qu'est-ce qui doit rester constant ? » — reste à poser
  aux seuils du monitorage (`MONITORAGE_SEUIL_ERREUR`, `MONITORAGE_SEUIL_LATENCE`).
  Depuis le déploiement, la latence du RAG dépasse largement le seuil de
  10 secondes prévu pour le poste : l'alerte de latence est donc **en train de
  devenir permanente**, ce qui est exactement le motif de cet incident. À
  trancher avec la réserve 7.
