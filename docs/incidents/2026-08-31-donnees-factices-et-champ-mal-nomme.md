# Incident 011 — Quatre pages qui affichaient des chiffres inventés, et un champ dont le nom ment

**Date :** 31 août 2026
**Composants :** `apps/tracker/`, `apps/revision/`, `apps/quiz/`, `apps/exercises/models.py`
**Gravité :** majeure — l'interface présentait comme mesuré ce qui était fabriqué
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C17 (E4) ; C20 (E5) ; C11 (E3) — indicateurs

---

## 1. Déclenchement

Le chantier de la page d'accueil signalait un tableau de bord affichant
« Python Basics 85 % » sur un compte à zéro cours, et demandait de **vérifier
s'il y en avait ailleurs**. Le motif se répète rarement une seule fois.

Il y en avait ailleurs. Quatre endroits, et le tableau de bord n'était pas le
pire.

---

## 2. L'inventaire

| Emplacement | Ce qui s'affichait | Comment c'était produit |
|---|---|---|
| `tracker/views.py` | Temps d'étude | `total_courses * 25` — « ~25 min par cours » |
| `tracker/views.py` | Temps aujourd'hui | `total_study_minutes // 10`, plafonné à 2 h 30 |
| `tracker/views.py` | **Taux de réussite** | **`60 + xp // 50`** — un taux de réussite calculé sur l'expérience gagnée |
| `tracker/views.py` | Semaine d'activité | Sept jours dérivés du temps simulé, par soustractions |
| `tracker/views.py` | Score des cours suivis | `70 + xp // 30 + rang * 5`, avec un « il y a 2 h » inventé |
| `tracker/views.py` | Sujets étudiés | **Trois exemples inventés ajoutés** quand l'apprenant n'en avait pas assez |
| `tracker/views.py` | Objectifs de la semaine | `total_courses_completed % 4` — un modulo présenté comme un décompte |
| `revision/flashcards.html` | **Toute la page** | Séance inventée, 24 cartes maîtrisées, 92 % de réussite, 7 jours de série, 1 h 23 de révision. La vue ne passait **aucune** donnée |
| `quiz/quiz_lobby.html` | Statistiques du compte | 127 quiz, 85 % d'exactitude, 12 jours, 3 h 42 — en dur, identiques pour tous |

**Le champ `total_study_time_minutes` existe et n'est écrit par aucun code du
projet.** Il n'était lu que pour retomber immédiatement sur la simulation.

---

## 3. Diagnostic

### 3.1 Ce n'est pas de la maquette oubliée

Une valeur en dur dans un gabarit se comprend : c'est une maquette qu'on n'a
pas branchée. Mais `success_rate = min(95, 60 + (user.xp // 50))` est un
**calcul**, écrit en Python, commenté « Between 60% and 95% ». Quelqu'un a
voulu que le chiffre ait l'air vivant.

C'est ce qui rend ce cas plus grave qu'un texte de remplissage : un nombre qui
bouge avec l'usage est cru.

### 3.2 Pourquoi cela ne se voyait pas

Parce que les valeurs étaient **plausibles**. 85 %, 3 h 42, 12 jours de série :
rien qui alerte. Un zéro se remarque, un chiffre vraisemblable non.

Et parce que les pages concernées ne sont pas celles qu'on ouvre en
développant : on code le générateur, les exercices, les quiz. Le tableau de
bord et la page de révision, on les regarde le jour de la démonstration.

### 3.3 Le champ mal nommé — la variante discrète

Un dernier cas, découvert en écrivant la règle de progression :

```python
progress.attempts_count += 1          # à CHAQUE soumission
if all_passed and not progress.is_completed:
    ...
```

`attempts_count` s'incrémente à chaque soumission, y compris **après** la
réussite. Il compte donc les soumissions, jamais les tentatives avant réussite.

**Son nom dit l'inverse de ce qu'il contient**, et nous l'avons supposé dans le
mauvais sens — l'autrice comme moi — en concevant le bloc « à revoir ». Employé
tel quel, il aurait classé comme difficile un exercice réussi du premier coup
puis retravaillé par curiosité.

Le champ est correct : il compte ce qu'il compte, sans erreur. C'est **son nom
qui induit en erreur**, ce qui en fait la forme la plus discrète de la
famille B — un instrument juste, dont l'étiquette désigne autre chose.

---

## 4. Résolution

**Rien n'est estimé.** Ce qui est mesuré est affiché, ce qui ne l'est pas est
**annoncé comme non mesuré** — le même traitement que le niveau 3 du
référentiel (décision 028).

| Page | Ce qu'elle affiche désormais |
|---|---|
| Performance | Cours créés, exercices réussis, quiz terminés, score moyen, progression par compétence. Temps d'étude : « non mesuré », avec la raison |
| Révision | Les notions qui ont résisté, mêmes données que le bloc « à revoir » de l'accueil. Le produit n'a pas de système de cartes : il n'y a pas de séance à proposer |
| Salon de quiz | Quiz terminés et score moyen, tous deux mesurés. Exactitude et temps total retirés, faute d'être enregistrés |
| Accueil | Construit dès l'origine sur des données mesurées, avec un état vide par bloc |

Le nombre de tentatives avant réussite se calcule sur les **soumissions
antérieures à la réussite**, jamais sur `attempts_count`. Le motif est écrit à
chaque endroit qui le lit.

---

## 5. Tests en succès

| Test | Vérifie |
|---|---|
| Aucune valeur factice sur quatre pages | « Python Basics », « 85% », « 92% », « 127 », « 3h 42m »… absents de l'accueil, de Performance, de Révision et du salon |
| Temps d'étude annoncé non mesuré | La page le dit au lieu de le simuler |
| Un quiz non terminé n'est pas une activité | Une session ouverte ne compte pas |
| Réussite du premier coup absente de « à revoir » | Le critère porte bien sur les tentatives |

Suite complète : **180 tests**.

---

## 6. Ce que cet incident ajoute aux motifs

Il appartient à la **famille B** — l'instrument ne mesure pas ce qu'il prétend —
et il en fournit les deux extrêmes.

**Le plus grossier** : un taux de réussite calculé sur l'expérience gagnée. La
valeur n'a aucun rapport avec ce que son étiquette annonce.

**Le plus discret** : un champ qui compte exactement ce qu'il compte, dont
seul le nom trompe. Aucune ligne de code n'est fausse ; c'est la lecture qui
l'est, et elle l'a été deux fois, par deux personnes, le même jour.

**La leçon s'ajoute aux deux questions de la famille B** : après « de quoi cette
valeur est-elle l'effet ? » et « qu'est-ce qui doit rester constant ? », il faut
poser **« le nom de ce champ décrit-il ce qu'il contient ? »**. Un nom est une
promesse, et personne ne relit une promesse tenue.

---

## 7. Reste à faire

- **Renommer `attempts_count`** en `soumissions_count`, ou lui adjoindre une
  propriété `tentatives_avant_reussite`. Un renommage touche une migration, un
  modèle, plusieurs vues et un gabarit : à faire après le 14 septembre. D'ici
  là, le motif est écrit partout où le champ est lu.
- **Mesurer le temps d'étude**, ou retirer le champ `total_study_time_minutes`.
  Un champ jamais écrit est une promesse en attente, et ce dossier vient de
  montrer ce que coûtent les promesses en attente.
- La page `revision/review.html` n'a pas été examinée ; elle est atteignable et
  mérite le même passage.
