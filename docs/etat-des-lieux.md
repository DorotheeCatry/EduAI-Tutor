# EduAI Tutor — état des lieux au regard du référentiel RNCP 37827

Document de contexte. Il décrit l'état réel du dépôt à la date de rédaction,
mesuré contre les exigences de `docs/cahier-des-charges.md`, et distingue **ce qui est vérifié**
de ce qui est simplement constaté par lecture du code.

Toutes les données chiffrées ci-dessous ont été obtenues par exécution ou par
`grep` sur le dépôt, pas par estimation.

---

## 1. Rappel du cadre

EduAI Tutor est une plateforme éducative web à architecture multi-agents
(Researcher, Pedagogue, Coach, Watcher) avec RAG, servant de support
d'évaluation pour la certification RNCP 37827 « Développeur en intelligence
artificielle ».

**Échéances :** rendu des 5 livrables écrits le **4 septembre 17h**, soutenance
le **14 septembre**.

**Contrainte structurante :** aucun bloc de compétences n'est sacrifiable. La
priorité est la **couverture des 21 compétences**, pas la profondeur sur
quelques-unes. Une compétence couverte modestement vaut mieux qu'une compétence
absente.

**Interdits jusqu'au 4 septembre :** pas de restructuration de l'arborescence,
pas de changement de dépendance majeure, pas de refactoring de confort, pas de
fonctionnalité non exigée par le référentiel.

---

## 2. L'application fonctionne — vérifié

C'est le point acquis, et il ne l'était pas il y a peu : l'environnement était
inutilisable (`.venv/bin/python` pointait vers un interpréteur absent de la
machine). Après `uv sync` :

| Vérification | Résultat |
|---|---|
| Interpréteur | Python 3.13.13, Django 5.2.12 |
| `manage.py check` | `System check identified no issues (0 silenced)` |
| Migrations | **15 fichiers, toutes appliquées** |
| Dérive modèles / migrations | `makemigrations --check` → `No changes detected` |
| Pages HTTP | **13 pages authentifiées répondent en 200**, aucune 500 |
| Données réelles | 19 utilisateurs, 4 cours, 5 exercices, 22 salles de quiz |
| Vector store | Chroma opérationnel, **387 documents** dans `eduai_knowledge_base` |
| Corpus | `data/contents/` — **95 Mo**, 41 `.md`, 21 `.pdf`, 12 `.avif`, 1 `.ipynb`, 1 `.pptx`, sur 11 modules |

Pages contrôlées en 200 : accueil, générateur de cours, mes cours, lobby quiz,
création de salle, chat, exercices, progression, dashboard, flashcards,
révision, profil, admin.

### Ce qui reste bloqué sur la couche IA

L'interface fonctionne, mais **la génération IA ne peut pas s'exécuter**, pour
trois causes indépendantes :

1. **Le modèle codé en dur n'existe plus.**
   `meta-llama/llama-4-scout-17b-16e-instruct` renvoie `404 model_not_found` —
   Groq l'a retiré de son catalogue. Il est écrit en dur dans trois fichiers
   (`agent_researcher.py:9`, `agent_pedagogue.py:11`, `agent_coach.py:12` et
   `:25`), sans constante ni entrée de configuration.
2. **Tous les modèles disponibles sont bloqués au niveau du projet Groq.**
   Les six modèles de chat du catalogue (`gpt-oss-120b`, `gpt-oss-20b`,
   `qwen3.6-27b`, `compound`, `compound-mini`, `allam-2-7b`) renvoient
   `403 model_permission_blocked_project`. La clé API est valide — le listing
   des modèles passe en 200. Le déblocage se fait dans la console Groq
   (*settings → project → limits*) et **ne peut pas être fait depuis le code**.
3. **Ollama est absent de la machine.** Le RAG l'utilise pour les embeddings
   (`mxbai-embed-large`, `apps/rag/utils.py`). Sans lui, la recherche
   documentaire échoue et les agents basculent sur leur repli LLM direct — qui
   est lui-même bloqué par le point 2.

Anomalie mineure : `data_science_index.json` est vide et ignoré au démarrage.
Le générateur ne propose que 3 modules (`general`, `ressources`, `python`) au
lieu de 4.

---

## 3. Couverture du référentiel — l'écart

Le dépôt est **une application, pas un dossier de certification**. Le Bloc 3
dispose d'un vrai support ; le Bloc 2 a du code mais aucune preuve
d'évaluation ; le Bloc 1 est à construire intégralement.

### Bloc 1 — épreuve E1, C1 à C5 : absent

| Compétence | État | Constat |
|---|---|---|
| **C1** — 5 types de sources | **0 sur 5** | Aucun extracteur. `grep` sur `requests`, `BeautifulSoup`, `pyspark`, `pandas`, `psycopg`, `read_csv`, `read_parquet` sur tout le code applicatif → **un seul fichier**, et c'est la *liste noire* d'imports interdits du bac à sable (`apps/exercises/security.py:36`). Aucune de ces dépendances n'est déclarée. |
| **C2** — requêtes | absent | Aucun `.sql`, aucun `.spark.sql`. Pas de Spark. Le référentiel exige **deux langages** : SQL sur PostgreSQL **et** Spark SQL. |
| **C3** — transformation | absent | Pas de pipeline de nettoyage ou d'homogénéisation identifiable. Le chunking RAG ne remplit pas ce critère. |
| **C4** — base de données | **non conforme** | **SQLite**, pas PostgreSQL (`settings.py:131-136`). Pas de MCD, pas de MPD, pas de dictionnaire de données. |
| **C5** — API du jeu de données | absent | Inexistante. |

**Point critique sur C4 :** les 15 migrations existent sur le disque mais
`.gitignore:230` contient `**/migrations/`, donc `git ls-files | grep migrations`
renvoie **0**. Quelqu'un qui clone le dépôt n'obtient aucun schéma. C'est la
modification d'une seule ligne au rendement le plus élevé de tout le projet.

**RGPD (C4) :** `grep` sur `anonym|rgpd|gdpr|retention|purge|consent` → **0 hit**.
Sont pourtant collectés : e-mail (identifiant de connexion), `bio` en texte
libre, avatar uploadé, et **l'adresse IP de chaque soumission de code**
(`ExerciseSubmission.ip_address`, remplie en `apps/exercises/views.py:120`).
Aucune route de suppression de compte, aucun export, aucune durée de
conservation, aucune politique de confidentialité. Le public visé est
exclusivement adulte (cf. `docs/decisions/005`), ce qui écarte le régime de
consentement parental mais laisse entières les obligations de minimisation, de
conservation et d'effacement. L'adresse IP est une donnée à caractère personnel
quel que soit l'âge : sa finalité n'étant pas établie, elle sera supprimée et
non conservée sous une durée.

**Sur le corpus :** `data/contents/` est du matériel de cours personnel. Il
alimente correctement le RAG, mais **ne constitue pas une source C1** : un seul
type, pas de licence documentée, pas de contrainte de source, pas de manifeste
de provenance.

### Bloc 2 — service IA

- **DRF est installé et jamais utilisé.** `grep` sur
  `serializers|ViewSet|APIView|@api_view|Router` dans tout le code applicatif →
  **0 hit**. La seule trace est la ligne `'rest_framework',` dans
  `INSTALLED_APPS` (`settings.py:83`). **C9 est donc absent**, et la séparation
  API données / API service IA exigée par `docs/cahier-des-charges.md` reste sans objet.
- Les 5 points de terminaison JSON sont artisanaux (`JsonResponse` +
  `json.loads(request.body)`) : **3 désactivent la CSRF** (`@csrf_exempt`),
  **2 sont ouverts aux anonymes** (`apps/courses/views.py:154-179`), **aucun
  throttling**, aucune pagination, aucun schéma OpenAPI. OWASP API Top 10 :
  ni implémenté, ni documenté.
- **Aucune évaluation du modèle** : pas de métrique, pas de jeu de test, pas de
  mesure de latence ou de coût, pas de `recall@k`, pas de LLM-as-judge. Les
  seules occurrences de `score` concernent le score de jeu des apprenants.
- **Aucune veille, aucun benchmark de modèles.**
- Trois fichiers de preuve sont **vides (0 octet)** : `apps/agents/agent_base.py`,
  `apps/agents/chains/rag_chain.py`, `apps/agents/prompts/watcher.txt`.

### Bloc 3

- **C17 — application web Django : acquis.** ~4 500 lignes de Python, 9 apps,
  39 routes, auth custom (`KodaUser`, login par e-mail), quiz multijoueur
  temps réel via Channels/WebSocket, exercices de code avec Monaco,
  gamification XP. C'est le seul bloc réellement alimenté.
- **C18 — tests et CI : 0.** Aucun test : les 6 `tests.py` sont les stubs
  `startapp` de 3 lignes ; les apps `agents`, `exercises`, `rag` n'en ont même
  pas. **`pytest` n'apparaît pas dans `uv.lock`** et il n'existe aucun groupe de
  dépendances de développement dans `pyproject.toml`. Pas de `conftest.py`.
  **Pas de `.github/`**, donc pas de CI. **Pas de Dockerfile ni de
  `docker-compose.yml`**, alors que `docs/cahier-des-charges.md` documente `docker compose up -d`.
- **Accessibilité** (transversale à C6, C9, C10, C14, C17, C19, C20) :
  **0 attribut `aria-*`, 0 `role=`** dans les templates. Hiérarchie de titres
  non séquentielle (deux `<h1>` dans `chat.html`, sauts h1→h3 ailleurs).
  `<html lang="fr">` figé alors que `LANGUAGE_CODE = 'en'`. Champs de
  formulaire écrits à la main sans `<label>`. Seul point positif : les `alt`
  d'images sont présents.

### Documentation et traçabilité

- **Aucun dossier `docs/`** avant ce document. Ni journal de décisions
  (`docs/decisions/`), ni notes quotidiennes (`docs/journal/`), ni matrice de
  traçabilité, ni schéma d'architecture.
- **0 docstring `Compétence visée`** dans tout le code, alors que `docs/cahier-des-charges.md`
  l'exige pour toute fonction servant de preuve, accompagnée d'une ligne
  « Choix » justifiant l'implémentation.
- **0 commit portant un tag `[Cx]`** sur 353 commits. Environ 14 % seulement
  suivent un format conventionnel ; beaucoup sont des messages auto-générés par
  l'éditeur web GitHub (« Updated views.py »).
- **Logs :** `docs/cahier-des-charges.md` impose `logging` plutôt que `print`. Résultat :
  **0 `import logging`** dans `apps/`, et **~86 appels à `print`** répartis sur
  10 fichiers.

---

## 4. Sécurité — constats

**Bonne nouvelle vérifiée :** aucun secret n'a jamais été commité. Ni `.env`,
ni `key_groq.txt`, ni `db.sqlite3` n'apparaissent dans l'historique Git, et
aucune occurrence de `gsk_` dans les 60 derniers commits. Le `.gitignore` a
fait son travail.

**Points à traiter :**

- `SECRET_KEY` en dur (`settings.py:26`, la valeur `django-insecure-` par
  défaut) et `DEBUG = True` en dur (`settings.py:29`). Aucune variable
  d'environnement n'est lue dans `settings.py` — la seule utilisation de
  `os.getenv` du projet est dans `apps/agents/tools/llm_loader.py`.
- Aucun durcissement : pas de `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- **Le bac à sable n'est pas RestrictedPython.** La dépendance est déclarée
  dans `pyproject.toml` mais **jamais importée**. `apps/exercises/security.py`
  implémente un `exec()` maison dont la liste blanche contient `__import__`,
  `getattr` et `setattr`, dont la validation se fait par recherche de
  sous-chaînes sur le source, et dont le `timeout` est stocké dans `__init__`
  puis **jamais appliqué** (ni signal, ni sous-processus, ni limite mémoire).
  C'est une question qui viendra à la soutenance.
- `key_groq.txt` (408 octets) traîne à la racine alors que `.env` porte
  désormais la clé. Gitignoré, donc sans risque immédiat, mais redondant.
- `CHANNEL_LAYERS` utilise `InMemoryChannelLayer` (`settings.py:222`) alors que
  `channels-redis` est déclaré en dépendance. Le multijoueur ne fonctionne
  qu'en mono-processus.

---

## 5. Synthèse et ordre de traitement

| Bloc | État | Risque |
|---|---|---|
| Bloc 1 (C1–C5) | **à construire intégralement** | **élevé** |
| Bloc 2 (service IA) | code présent, **aucune preuve ni API** | élevé |
| Bloc 3 (C17) | **acquis** | faible |
| Bloc 3 (C18, accessibilité) | absent | moyen |
| Documentation / traçabilité | **absente** | élevé |

Le blocage de fond est levé : sans environnement, sans corpus et sans base,
aucune preuve n'était productible. Ce n'est plus le cas. L'écart au référentiel,
lui, est intact.

**Ordre proposé, du plus bloquant au moins bloquant :**

1. **Retirer `**/migrations/` du `.gitignore`** et versionner les 15 migrations.
   Une ligne, débloque C4.
2. **Débloquer les modèles dans la console Groq**, puis remplacer le modèle mort
   dans les 3 fichiers. Sans cela, aucune démonstration IA n'est possible à
   l'oral. Candidat recommandé : `openai/gpt-oss-120b` (131k de contexte,
   `json_mode` et sorties structurées — utiles pour le parsing des quiz,
   aujourd'hui fait à la regex dans `apps/agents/utils.py`).
3. **`docs/`** : matrice de traçabilité des 21 compétences, `docs/decisions/`
   rétroactif sur les choix déjà faits (multi-agents, Groq/Ollama, Chroma, uv,
   bac à sable maison, SQLite), `docs/journal/`.
4. **Bloc 1 de bout en bout** : 5 sources → transformation → PostgreSQL avec
   MCD/MPD → requêtes SQL et Spark SQL → API données (C5).
5. **API du service IA (C9)** en DRF, distincte de l'API données, avec
   authentification et throttling.
6. **Tests pytest + CI GitHub Actions** (C18).
7. **Accessibilité, RGPD, durcissement des secrets.**

---

## 6. Commandes de vérification

Tous les constats de ce document sont reproductibles en lecture seule :

```bash
uv run python manage.py check                          # → no issues
uv run python manage.py makemigrations --check         # → No changes detected
git ls-files | grep -c migrations                      # → 0 (malgré 15 sur disque)
grep -rn "serializers\|ViewSet\|APIView" --include=*.py apps   # → 0
grep -rln "import logging" --include=*.py apps         # → 0
grep -c 'name = "pytest"' uv.lock                      # → 0
grep -rln "Compétence visée" --include=*.py apps       # → 0
git log --oneline | grep -c "\[C[0-9]"                 # → 0
ls .github                                             # → No such file or directory
```
