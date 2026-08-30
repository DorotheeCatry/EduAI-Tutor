# Incident 007 — Quatre tests verts en local, rouges à leur première exécution en intégration continue

**Date :** 30 août 2026
**Composant :** `tests/test_effacement_compte.py`, `tests/test_quotas.py`
**Gravité :** mineure — aucun impact sur le service ; la chaîne d'intégration était rouge
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C18 (E4) — tests automatisés ; C13 (E3) — sécurité du transport ; C19 (E5) — chaîne de livraison

---

## 1. Déclenchement

**30/08, dans l'après-midi.** Première poussée de la branche
`feat/bloc3-deploiement-railway` vers GitHub : trente-sept commits accumulés en
local depuis le 28/08. La chaîne d'intégration s'exécute pour la première fois
sur ce travail.

Le travail de test `pytest` échoue. Quatre tests, tous ceux qui passent par le
client HTTP de Django :

| Fichier | Test | Attendu | Obtenu |
|---|---|---|---|
| `test_effacement_compte.py` | confirmation incorrecte | 200 | **301** |
| `test_effacement_compte.py` | confirmation exacte | 302 | **301** |
| `test_effacement_compte.py` | écran de confirmation | 200 | **301** |
| `test_quotas.py` | décompte affiché sur la page | 200 | **301** |

Le `301` pointe vers `https://testserver/`. La même suite passait sur le poste
de développement, et avait été exécutée quelques minutes plus tôt : 111 tests
verts.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Application en service | **aucun** — le comportement testé fonctionne, c'est le test qui ne l'atteignait pas |
| Chaîne d'intégration | rouge, travail `tests` en échec, travail `image` non exécuté |
| Couverture réelle | **quatre vues jamais éprouvées hors DEBUG**, donc jamais dans les conditions de la production |
| Réglages de sécurité | aucun : ils faisaient exactement ce qui est écrit dans la décision 008 |

---

## 3. Diagnostic

### 3.1 Ce que le 301 dit

`SECURE_SSL_REDIRECT` renvoie toute requête en clair vers son équivalent HTTPS,
**avant que la vue ne s'exécute**. Le client de test de Django émet par défaut
des requêtes en `http://testserver`. La redirection répond donc à sa place, et
la vue testée n'est jamais atteinte.

### 3.2 Pourquoi en intégration continue et pas en local

`eduai_project/settings.py` conditionne les réglages de transport :

```python
DEBUG = os.environ.get("DJANGO_DEBUG", "False").strip().lower() in ("1", "true", "oui")
...
if not DEBUG:
    SECURE_SSL_REDIRECT = True
```

| Environnement | `DJANGO_DEBUG` | `DEBUG` | `SECURE_SSL_REDIRECT` |
|---|---|---|---|
| Poste de développement | `True`, dans `.env` | `True` | inactif |
| Intégration continue | **non défini** | `False` | **actif** |
| Hébergeur | non défini | `False` | actif |

Le défaut de la variable est `False` : c'est un choix délibéré de la
décision 008 — un réglage de sécurité absent doit interrompre ou protéger, pas
basculer silencieusement sur la valeur permissive. **Ce défaut a fonctionné
comme prévu.**

### 3.3 Cause racine

Ce n'est pas un défaut de configuration. C'est un **écart entre l'environnement
où les tests ont été écrits et celui où ils s'exécutent** : ils ont été rédigés
et vérifiés en local avec `DEBUG=True`, et n'avaient **jamais tourné en
intégration continue** — les trente-sept commits n'étaient pas poussés.

La configuration et les tests étaient chacun corrects dans leur contexte. Ce
qui manquait, c'est la rencontre des deux.

---

## 4. Résolution

Les quatre appels passent `secure=True` au client de test, qui émet alors une
requête `https://testserver` que la redirection laisse passer.

```python
reponse = client.get("/auth/profile/supprimer/", secure=True)
```

### L'option écartée, et pourquoi

Une surcharge de réglages (`@override_settings(SECURE_SSL_REDIRECT=False)`)
aurait rendu les tests verts avec autant de facilité. Elle a été écartée : elle
fait passer le test **en supprimant la protection qu'il traverse**, alors que
`secure=True` éprouve le chemin réel — la production est servie en HTTPS,
derrière le proxy de l'hébergeur.

La différence n'est pas cosmétique. Avec la surcharge, plus aucun test
n'exercerait la pile de sécurité du transport, et sa désactivation accidentelle
ne serait signalée par rien.

---

## 5. Tests en succès

| Vérification | Résultat |
|---|---|
| `DJANGO_DEBUG=False uv run pytest tests/test_effacement_compte.py tests/test_quotas.py` | **32 passés** |
| `DJANGO_DEBUG=False uv run pytest` — suite complète en conditions d'intégration | **111 passés** |
| `uv run pytest` — suite complète en conditions locales | 111 passés |
| `uv run ruff check .` | aucun écart |

La suite complète a été rejouée avec `DJANGO_DEBUG=False` et non seulement les
quatre tests corrigés : c'était l'occasion de vérifier qu'aucun autre test ne
dépendait de `DEBUG`. Aucun ne le fait.

---

## 6. Ce que cet incident ajoute aux précédents

C'est la deuxième occurrence du motif de l'incident 003, sous une forme moins
grave et plus visible.

| Incident | Vérifié dans un contexte | Utilisé dans un autre |
|---|---|---|
| 003, 28/08 | une sonde de monitorage, en script | dans une requête HTTP — aucune trace produite |
| **007, 30/08** | **quatre tests, avec `DEBUG=True`** | **en intégration continue, `DEBUG=False` — 301** |

Le premier était silencieux et a coûté vingt-deux heures de traces. Celui-ci
s'est annoncé lui-même, au premier passage de la chaîne, en trente secondes.
**C'est exactement ce à quoi sert l'intégration continue**, et c'est aussi ce
qui rend l'incident instructif : la chaîne existait depuis le 28/08, elle n'a
rien pu dire tant que rien n'y était poussé.

**La leçon :** une chaîne d'intégration ne protège que le code qui lui parvient.
Trente-sept commits retenus en local, c'est trente-sept commits non vérifiés,
quelle que soit la qualité de la chaîne.

---

## 7. Reste à faire

- **Pousser plus souvent.** Le déclencheur de la chaîne est déjà `push` sur
  toute branche : il ne manquait que le push. Aucune modification technique
  n'est nécessaire, seulement une habitude.
- **Rejouer la suite avec `DJANGO_DEBUG=False`** avant d'annoncer qu'elle
  passe. C'est une commande, elle reproduit les conditions de la chaîne et
  celles de l'hébergeur, et elle est consignée dans
  `docs/strategie_tests.md`.
- Ce contrôle vaudra aussi pour le déploiement : les réglages activés hors
  DEBUG — redirection, HSTS, cookies `Secure` — sont ceux dont l'étape de
  vérification sur l'URL publique doit constater l'effet réel.
