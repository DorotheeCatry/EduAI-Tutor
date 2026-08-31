# Incident 010 — Un chemin complet, correct en apparence, que rien n'appelait

**Date :** 31 août 2026
**Composant :** `apps/quiz/`, `apps/agents/agent_orchestrator.py`, `apps/agents/agent_watcher.py`
**Gravité :** majeure — aucun résultat de quiz solo n'a jamais été enregistré
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C17 (E4) ; C20 (E5) — données du suivi ; C13 (E3) — CSRF

---

## 1. Déclenchement

Le chantier de la page d'accueil demandait, avant toute conception, de vérifier
**par le code et les données** ce que conservent les modèles d'exercice et de
quiz. La question portait sur le bloc « à revoir » : sur quoi peut-il se
fonder ?

La lecture a d'abord trouvé un libellé fautif :

```python
self.watcher.record_mistake(
    topic=session_id,  # Use session_id as temporary topic
    ...
)
```

Les erreurs de quiz étaient enregistrées sous un **identifiant de session** au
lieu de la notion. Le commentaire annonçait un provisoire ; il datait de la
création du fichier.

**Puis la vérification a montré pire.** Le gabarit du quiz solo n'appelle
jamais la vue d'enregistrement : `showFinalResults()` affiche le score dans une
boîte de dialogue, puis redirige vers le salon.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Résultats de quiz solo | **Aucun n'a jamais été enregistré**, depuis l'origine |
| `LearningSession` | Ouvertes à chaque génération, **jamais closes** — ni durée, ni score |
| `UserMistake` | **Zéro ligne**, sur les deux bases |
| `user.total_quizzes_completed` | Jamais incrémenté par un quiz solo |
| XP de fin de quiz | Jamais attribués |
| Bloc « à revoir » de la page d'accueil | **Sans source de données** |

Relevé sur la base déployée : 4 sessions ouvertes, 0 close, 0 erreur.

---

## 3. Diagnostic

### 3.1 La chaîne, telle qu'elle existait

| Maillon | État |
|---|---|
| Route `quiz:submit` | déclarée dans `urls.py` |
| Vue `submit_quiz` | écrite, décorée `@login_required` |
| `orchestrator.submit_quiz_results` | écrite, calculant score, erreurs et XP |
| `watcher.record_mistake` | écrite, écrivant bien en base |
| **Appel depuis le navigateur** | **absent** |

Tout était en place sauf le premier maillon. Le code n'était pas incomplet : il
était injoignable.

### 3.2 Les trois défauts que le code mort protégeait

Écrire les tests a révélé que la chaîne, si elle avait été appelée, **aurait
échoué de trois façons** :

| # | Défaut | Effet s'il avait été exécuté |
|---|---|---|
| 1 | `topic=session_id` | Erreurs enregistrées sous un nombre, inexploitables |
| 2 | `end_session` comparait `datetime.now()` — naïf — à `start_time` — conscient du fuseau, `USE_TZ = True` | `TypeError` à chaque clôture de session |
| 3 | La réponse renvoyait l'objet `LearningSession` | `TypeError: not JSON serializable`, erreur 500 |

Le deuxième mérite d'être souligné : **cette méthode n'a jamais pu aboutir
depuis qu'elle existe.** Aucun test, aucune exécution, aucune alerte — parce
qu'aucun appel.

### 3.3 Cause racine

Un chemin de code écrit d'un bout à l'autre, revu, correct en apparence, et
jamais exécuté. **Le code mort ne signale pas ses défauts : il les conserve.**

Ce n'est pas l'absence de tests qui est en cause — c'est qu'aucun test ne
partait de ce que l'utilisateur fait. Une couverture par fonction aurait pu
atteindre `submit_quiz_results` avec des données fabriquées et passer au vert
sur les trois défauts.

---

## 4. Résolution

**Le gabarit envoie désormais le résultat** avant de rediriger, avec le jeton
CSRF et `keepalive` — sans quoi le navigateur est en droit d'abandonner la
requête au moment où la page change, et le résultat serait perdu par
intermittence.

**Les réponses sont conservées, l'absence de réponse comprise.** Une question
laissée sans clic vaut `-1` et s'enregistre « Sans réponse » : confondre
l'abandon et l'erreur ferait proposer de réviser une notion jamais lue.

**Le sujet vient de la session, relue en base.** C'est la seule valeur dont le
serveur soit l'auteur : `create_quiz` l'y a écrite avec le sujet réellement
demandé.

**Le serveur corrige lui-même.** Les questions sont désormais conservées dans
`LearningSession.metadata` à la génération. Le corps de la requête n'apporte
que les réponses ; un client qui annoncerait un score ne serait pas cru, ces
champs n'étant pas lus.

**`@csrf_exempt` est retiré**, remplacé par `@require_POST`. Cette vue modifie
les statistiques du compte : sans protection CSRF, elle était déclenchable
depuis n'importe quelle page tierce ouverte dans le navigateur de l'apprenant.

Les défauts 2 et 3 sont corrigés au passage, avec le motif écrit sur place.

---

## 5. Tests en succès

Sept tests, portant sur ce qui est écrit en base et sous quel libellé — un test
qui se contenterait d'un code 200 aurait laissé passer les trois défauts.

| Test | Vérifie |
|---|---|
| Notion et non session | `topic == "les listes en Python"`, et `!= str(session.id)` |
| Sans réponse distinguée | `user_answer == "Sans réponse"` |
| Session close | `score == 100.0`, `end_time` renseigné, compteur à 1 |
| Score non fourni par le client | Un corps annonçant 100 % rend 0.0 |
| Session sans questions | Refus en 400, aucune erreur enregistrée |
| Session d'autrui | Refus en 400 |
| Méthode GET | 405 |

Suite complète : **133 tests**.

---

## 6. Ce que cet incident ajoute aux motifs

Il appartient à la **famille B** de `docs/motifs_incidents.md` — l'instrument
qui ne mesure pas ce qu'il prétend — et il en fournit la variante extrême :
l'instrument ne mesurait rien du tout, tout en ayant l'apparence complète d'un
instrument.

Il ouvre surtout la **troisième famille**, qui n'attendait qu'une occurrence
pour être déclarée :

| Date | Ce qui était écrit | Ce qui manquait |
|---|---|---|
| 31/08 | `language_preference`, choisi et enregistré | rien ne le lisait pour l'interface |
| 31/08 | `LANGUAGE_CODE = 'en'`, catalogue `fr` seul | aucune traduction n'était appliquée |
| **31/08** | **route, vue, orchestrateur, agent** | **aucun appel depuis le navigateur** |

**Famille C — écrit, joignable, jamais appelé.** Sa parade est la même que
celle des deux autres, appliquée au bon endroit : un test qui part de ce que
l'utilisateur fait, et qui vérifie l'effet sur les données. Pas de la présence
d'une fonction.

---

## 7. Reste à faire

- **Les notions par question.** Le générateur ne produit pas de notion par
  question : l'erreur est rattachée au sujet du quiz entier. Pour un quiz
  « les listes en Python », toutes les erreurs portent cette notion, ce qui
  suffit au bloc « à revoir » mais ne distingue pas l'indexation du découpage.
  Le faire suppose de modifier l'invite du coach et d'accepter un champ de plus
  par question.
- **Les quatre sessions ouvertes avant ce correctif** ne portent pas leurs
  questions et resteront non closes. Les rattraper supposerait de deviner ce
  qui a été demandé ; elles sont laissées telles quelles, et ce paragraphe est
  leur explication.
- **Le quiz multijoueur** conserve, lui, ses questions et ses réponses en base
  (`GameQuestion`, `GameAnswer`) — mais la réserve 1 rappelle qu'aucun client
  ne l'appelle non plus.
