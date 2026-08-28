# Chaîne d'installation, de configuration, de test et de livraison

**Date :** 28 août 2026
**Compétence visée :** C13 (épreuve E3) — conteneurisation et déploiement
**Compétence visée :** C19 (épreuve E4) — documentation technique de la chaîne
**Compétences concernées :** C18 (E4) — tests en intégration continue

---

## Ce que ce document couvre

Le critère demande **toutes les étapes, toutes les tâches et tous les
déclencheurs disponibles**. Ce document les énumère sans exception : ce qui
déclenche quoi, dans quel ordre, avec quelles variables, et ce qui échoue si une
étape manque.

Il est écrit pour qu'une personne qui n'a jamais vu ce dépôt puisse monter le
projet, le configurer, l'éprouver et construire son image **à partir du seul
dépôt**, sans pièce jointe extérieure.

---

## 1. Les déclencheurs — la liste complète

### 1.1 Déclencheurs de la chaîne d'intégration continue

Fichier : `.github/workflows/integration-continue.yml`.

| Déclencheur | Portée | Ce qu'il lance |
|---|---|---|
| `push` | **toutes les branches** (`"**"`) | Les trois travaux |
| `pull_request` | **toutes les branches** (`"**"`) | Les trois travaux |
| `workflow_dispatch` | manuel, depuis l'interface GitHub | Les trois travaux |

**Trois déclencheurs, aucun autre.** Il n'y a ni déclencheur planifié (`schedule`),
ni déclencheur sur étiquette (`tags`), ni déclencheur sur publication
(`release`), et c'est délibéré :

- **Pas de `schedule`** : la chaîne n'éprouve rien qui varie avec le temps. Une
  exécution nocturne rejouerait à l'identique un résultat déjà connu.
- **Pas de `tags` ni de `release`** : rien n'est publié. Le travail « image »
  construit sans pousser vers un registre — publier supposerait un registre et
  des identifiants, hors du périmètre du projet.

**Le choix de `"**"` plutôt que d'une liste de branches** est le point important
de cette section. Une chaîne qui ne s'exécute que sur `main` ne protège pas
`main` : elle constate l'échec après la fusion. Ici, toute branche de chantier
est éprouvée avant d'être fusionnée.

### 1.2 Déclencheurs locaux

| Déclencheur | Mécanisme | Effet |
|---|---|---|
| Tout `git commit` | Crochet `.git/hooks/pre-commit` | **Refuse le commit si la branche est `main` ou `master`** ; échappatoire explicite par `AUTORISER_COMMIT_MAIN=1` |
| `docker compose up` | `depends_on` + `condition: service_healthy` | `service_ia` n'est lancé qu'une fois PostgreSQL déclaré sain ; Grafana attend Prometheus |
| Démarrage d'un conteneur | `restart: unless-stopped` | Les quatre services redémarrent après un arrêt de l'hôte, sauf arrêt explicite |
| Démarrage de PostgreSQL **sur un volume vierge** | Scripts montés dans `docker-entrypoint-initdb.d` | Création du schéma de `eduai_data`. **Ne se rejoue pas** si le volume contient déjà des données |
| Import de `service_ia` ou d'un agent | `apps.monitoring.sondes.installer()` | Branche la sonde de monitorage, sauf si `MONITORAGE_ACTIF` vaut `false` |

Le quatrième mérite un avertissement : **les scripts d'initialisation de
PostgreSQL ne s'exécutent qu'au premier démarrage**, sur un volume vide. Modifier
un script de schéma et relancer `docker compose up` ne change rien. Pour rejouer
le schéma, il faut soit détruire le volume (`docker compose down -v`, qui efface
les données), soit appliquer les scripts à la main (§ 2.4).

---

## 2. Installation

### 2.1 Prérequis

| Élément | Version | Vérification |
|---|---|---|
| Python | ≥ 3.12, < 3.14 | `python3 --version` |
| uv | récent | `uv --version` |
| Docker et Docker Compose | v2 | `docker compose version` |
| Java | 17 | `java -version` — requis par PySpark uniquement |
| Ollama | facultatif | `ollama list` — requis pour le RAG et le repli local |

La borne haute sur Python n'est pas une précaution : `RestrictedPython` et
`django-tailwind` ne suivent pas encore la 3.14.

### 2.2 Dépendances Python

```bash
uv sync
```

Pour reproduire exactement l'environnement de l'intégration continue :

```bash
uv sync --frozen --all-extras --dev
```

**`--frozen` refuse de mettre à jour `uv.lock`.** C'est ce qui garantit que ce
qui est éprouvé en intégration est ce qui tourne en local : sans verrou, un test
qui passe aujourd'hui et échoue demain ne dirait rien sur le code.

### 2.3 Services conteneurisés

```bash
docker compose up -d
```

Quatre services démarrent :

| Service | Image | Écoute | Volume |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `127.0.0.1:5433` | `postgres_data` |
| `service_ia` | `eduai/service-ia:1.0.0` | boucle locale, port 8100 | — |
| `prometheus` | `prom/prometheus:v2.55.1` | boucle locale, port 9090 | `prometheus_data` |
| `grafana` | `grafana/grafana:11.3.1` | boucle locale, port 3000 | `grafana_data` |

**Aucun service n'est publié sur `0.0.0.0`.** Ce point a coûté un incident : le
port de PostgreSQL avait été exposé à tout le réseau. Corriger le fichier n'a pas
suffi — `docker compose restart` ne recrée pas un conteneur :

```bash
docker compose up -d --force-recreate postgres
```

Les trois services de monitorage et le service IA tournent en `network_mode:
host`, faute de quoi ils ne pourraient pas joindre une application Django qui
n'écoute que sur la boucle locale de l'hôte.

### 2.4 Schéma de la base du jeu de données

Sur un volume vierge, les scripts sont joués automatiquement. Pour les rejouer à
la main, **dans cet ordre** :

```bash
for script in data_pipeline/load/sql/0[0-4]*.sql; do
  psql -h 127.0.0.1 -p 5433 -U eduai -d eduai_data -v ON_ERROR_STOP=1 -f "$script"
done
bash data_pipeline/load/sql/06_role_lecture.sh
```

| Script | Contenu |
|---|---|
| `00_bases.sql` | Création des deux bases |
| `01_schema.sql` | Tables du jeu de données |
| `02_index.sql` | Index — voir décision 007 |
| `03_contraintes.sql` | Contraintes d'intégrité |
| `04_donnees_reference.sql` | Nomenclatures : types de sources, licences |
| `06_role_lecture.sh` | Rôle en lecture seule pour l'API données |

**L'ordre n'est pas indicatif.** `ON_ERROR_STOP=1` interrompt à la première
erreur, plutôt que de poursuivre sur un schéma partiel.

### 2.5 Schéma de la base applicative

```bash
uv run python manage.py migrate
```

**16 migrations.** Contrôle qu'aucune dérive n'existe entre modèles et
migrations :

```bash
uv run python manage.py makemigrations --check --dry-run
```

### 2.6 Corpus et vector store

```bash
uv run python -m data_pipeline.orchestrator          # extraction → transformation → chargement
uv run python -m apps.rag.indexation_corpus          # eduai_data → ChromaDB
```

L'indexation est **reprenable** : les fragments déjà présents sont sautés, ce qui
importe car l'embarquement local traite environ vingt fragments par minute — un
traitement de plusieurs heures sera interrompu.

---

## 3. Configuration

Aucun secret n'est versionné. Tout passe par des variables d'environnement, lues
depuis un `.env` local non versionné.

### 3.1 Base de données

| Variable | Défaut | Rôle |
|---|---|---|
| `POSTGRES_HOST` | `127.0.0.1` | Hôte |
| `POSTGRES_PORT` | `5433` | Port publié |
| `POSTGRES_DB` | `eduai_data` | Base du jeu de données |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | — | Compte propriétaire |
| `DJANGO_DB_NAME` | `eduai_app` | Base applicative |
| `EDUAI_DATA_USER`, `EDUAI_DATA_PASSWORD` | — | Compte **en lecture seule** de l'API données |

### 3.2 Django

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | Obligatoire |
| `DJANGO_DEBUG` | `False` en dehors du développement |
| `DJANGO_ALLOWED_HOSTS` | Boucle locale par défaut |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origines de confiance |
| `DJANGO_DERRIERE_PROXY` | Active la lecture des en-têtes de proxy |

### 3.3 Modèles

| Variable | Rôle |
|---|---|
| `GROQ_API_KEY` | Clé du fournisseur ; son absence bascule sur le local |
| `GROQ_MODEL`, `DEFAULT_LLM_MODEL` | Modèles par défaut |
| `USE_LOCAL_LLM` | Force le repli local |
| `OLLAMA_BASE_URL` | Défaut `http://127.0.0.1:11434` |
| `OLLAMA_EMBED_MODEL` | Modèle d'embarquement |
| `OLLAMA_TIMEOUT` | Défaut 300 s — un embarquement local dépasse la minute sur machine chargée |
| `STACKEXCHANGE_KEY` | Facultative ; relève le quota de l'extracteur S1 |

### 3.4 Service IA

| Variable | Rôle |
|---|---|
| `SERVICE_IA_CLES` | Clés d'accès acceptées, séparées par des virgules |
| `SERVICE_IA_CONCURRENCE_MAX` | Bornes des appels simultanés |
| `SERVICE_IA_QUOTA_GENERATION`, `_RECHERCHE`, `_SANTE` | Limitation de débit par famille de points de terminaison |

### 3.5 Monitorage

| Variable | Défaut | Rôle |
|---|---|---|
| `MONITORAGE_ACTIF` | `true` | Mettre à `false` **désactive la sonde** |
| `MONITORAGE_REPERTOIRE` | `data_pipeline/data/monitorage` | Répertoire du journal |
| `MONITORAGE_APPELS_MINIMUM` | 5 | Plancher avant tout calcul de taux |
| `MONITORAGE_SEUIL_ERREUR` | 0,20 | Seuil d'alerte sur le taux d'erreur |
| `MONITORAGE_SEUIL_LATENCE` | 10 s | Seuil d'alerte sur la latence |
| `MONITORAGE_SILENCE_MINUTES` | 10 | Délai anti-répétition des alertes |
| `MONITORAGE_FENETRE_MINUTES` | — | Fenêtre glissante des taux |

---

## 4. Test

### 4.1 En local

```bash
uv run pytest              # suite complète
uv run pytest -m "not integration"   # sans PostgreSQL
uv run ruff check .        # analyse statique
```

**87 tests.** Trois marqueurs déclarés, et `--strict-markers` refuse tout
marqueur inconnu — un marqueur mal orthographié ferait silencieusement sauter un
test.

| Marqueur | Signification |
|---|---|
| `integration` | Exige PostgreSQL et le schéma de `eduai_data` |
| `corpus` | Exige le corpus chargé, non reconstituable en intégration continue |
| `lent` | Dépasse quelques secondes |

### 4.2 Les trois travaux de la chaîne

Les trois s'exécutent **en parallèle**, et aucun ne porte `continue-on-error` :
un contrôle qui ne peut pas faire échouer la chaîne ne contrôle rien.

#### Travail 1 — « Qualité du code »

| Étape | Commande |
|---|---|
| 1 | `actions/checkout@v4` |
| 2 | Installation d'uv avec cache (`astral-sh/setup-uv@v5`) |
| 3 | `uv sync --frozen --all-extras --dev` |
| 4 | `uv run ruff check .` |

#### Travail 2 — « Tests »

Service annexe : `postgres:16-alpine`, publié sur `5433`, avec un contrôle de
santé `pg_isready` toutes les 5 s, 10 tentatives. **Même version majeure que le
conteneur du projet** : éprouver sur une autre ferait passer des tests que la
production refuserait.

| Étape | Commande | Ce qui échoue si elle rate |
|---|---|---|
| 1 | `actions/checkout@v4` | — |
| 2 | Installation d'uv avec cache | — |
| 3 | `uv sync --frozen --all-extras --dev` | Dépendance non verrouillée |
| 4 | `apt-get install postgresql-client` | `psql` absent |
| 5 | Rejeu des scripts `0[0-4]*.sql` avec `ON_ERROR_STOP=1` | **Un schéma qui ne se crée plus depuis zéro n'est pas reproductible** |
| 6 | Contrôle : au moins 13 tables dans `information_schema` | Échec bruyant plutôt qu'une suite qui se sauterait en silence |
| 7 | `uv run pytest -v` | Régression |
| 8 | Récapitulatif (`if: always()`) | — |

Variables d'environnement de ce travail : `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `DJANGO_DB_NAME`,
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `EDUAI_DATA_USER`, `EDUAI_DATA_PASSWORD`,
`SERVICE_IA_CLES`, `MONITORAGE_ACTIF=false`.

**Aucune n'est un secret réel** : la base est créée puis détruite avec le
travail. `MONITORAGE_ACTIF=false` évite d'écrire des traces de test dans le
journal.

#### Travail 3 — « Construction de l'image du service IA »

| Étape | Commande | Rôle |
|---|---|---|
| 1 | `actions/checkout@v4` | — |
| 2 | `docker/setup-buildx-action@v3` | Constructeur |
| 3 | `docker/build-push-action@v6`, `push: false` | Construction **sans publication** |
| 4 | `docker buildx build --load` puis inspection | Contrôle du contenu |

Le cache est porté par le travail (`cache-from`/`cache-to: type=gha, mode=max`) :
la couche d'installation des dépendances prend **332 secondes mesurées** et n'a
pas à être rejouée tant que `uv.lock` ne change pas.

**Trois contrôles sur le contenu de l'image**, exécutés dans le conteneur :

```
test ! -d /app/.git                          # l'historique Git n'y est pas
test ! -f /app/apps/rag/chroma/chroma.sqlite3  # le vector store n'y est pas
test "$(stat -c %U /app)" = "eduai"          # /app n'appartient pas à root
```

Ils gardent un gain mesuré : le `.dockerignore` a ramené l'image de **10,1 Go à
5,22 Go**. Sans contrôle, la taille dériverait sans que rien ne le signale.

### 4.3 Ce qui se saute, et pourquoi cela se voit

Les tests marqués `corpus` se sautent en intégration : reconstituer 6 836
documents demanderait les dumps et plusieurs heures. **Le saut apparaît dans le
récapitulatif de la chaîne**, et il est motivé ici. Un test sauté en silence
serait un test absent.

---

## 5. Construction de l'image — étapes du `Dockerfile`

Fichier : `service_ia/Dockerfile`. Base `python:3.13-slim`.

| Étape | Contenu | Motif |
|---|---|---|
| 1 | Copie d'`uv` depuis son image officielle | Pas d'installation par `pip` |
| 2 | Variables d'environnement (`PYTHONUNBUFFERED`, …) | Journaux non tamponnés |
| 3 | Création de l'utilisateur `eduai`, UID 1000 | **Rien ne tourne en `root`** |
| 4 | `WORKDIR /app`, `chown` **du seul répertoire** | Un `chown -R` après installation dupliquerait l'arborescence dans une couche — c'est ce qui avait porté l'image à 10,1 Go |
| 5 | `USER eduai` | Bascule avant toute installation |
| 6 | `COPY pyproject.toml uv.lock` puis `uv sync --frozen --no-install-project` | **Avant** la copie du code : la couche est réutilisée tant que le verrou ne change pas |
| 7 | `COPY . .` puis `uv sync --frozen` | Le code, filtré par `.dockerignore` |
| 8 | `EXPOSE 8100` | — |
| 9 | `HEALTHCHECK` — 30 s d'intervalle, 5 s de délai, 40 s de démarrage, 3 tentatives | C'est lui que `depends_on: condition: service_healthy` attend |
| 10 | `CMD uvicorn service_ia.main:application` | — |

L'ordre des étapes 6 et 7 est le point de conception de ce fichier : inverser
les deux ferait réinstaller toutes les dépendances à chaque modification du
code — 332 secondes à chaque construction.

---

## 6. Livraison

**Il n'y a pas de déploiement automatisé, et ce n'est pas un oubli.**

Le projet tourne sur un poste unique. Publier vers un registre supposerait un
registre, des identifiants et une cible de déploiement, dont aucun n'existe. La
chaîne s'arrête donc à la construction et à la vérification de l'image.

Ce qui tient lieu de livraison :

| Étape | Commande |
|---|---|
| Construire l'image | `docker compose build service_ia` |
| Démarrer ou redémarrer | `docker compose up -d service_ia` |
| Forcer la recréation après un changement de configuration | `docker compose up -d --force-recreate service_ia` |
| Vérifier la santé | `docker compose ps` — colonne `Status` |
| Consulter les journaux | `docker compose logs -f service_ia` |

**Le piège à connaître** : `docker compose restart` **ne relit pas** le fichier
de composition. Un changement de port, de variable ou de réseau exige
`--force-recreate`. C'est ce qui avait laissé PostgreSQL exposé à tout le réseau
alors que le fichier était corrigé.

---

## 7. Ce que la chaîne ne fait pas

Énoncé pour qu'on ne le suppose pas.

| Absent | Raison |
|---|---|
| Publication de l'image vers un registre | Aucun registre, aucun identifiant |
| Déploiement automatisé | Aucune cible ; poste unique |
| Exécution planifiée | La chaîne n'éprouve rien qui varie avec le temps |
| Contrôle de couverture chiffré | Choix documenté dans `strategie_tests.md` : un taux mesure les lignes exécutées, pas les comportements éprouvés |
| Tests de bout en bout de l'interface | Coût élevé au regard de l'échéance |
| Analyse de sécurité des dépendances | **Manque réel**, non couvert par un choix ; ni `pip-audit` ni équivalent n'est branché |

Le dernier est le seul de la liste qui ne soit pas un arbitrage assumé mais une
lacune : il serait peu coûteux à combler et ne l'a pas été.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `.github/workflows/integration-continue.yml` | La chaîne |
| `service_ia/Dockerfile`, `.dockerignore` | La construction de l'image |
| `docker-compose.yml` | Les quatre services |
| `strategie_tests.md` | Ce que les tests éprouvent et pourquoi |
| `cadre_technique.md` | La pile et les environnements |
| `incidents/` | Les pannes dont plusieurs contrôles ci-dessus découlent |
