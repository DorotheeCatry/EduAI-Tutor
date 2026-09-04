# Chaîne d'installation, de configuration, de test et de livraison

**Date :** 28 août 2026, complété le 30 août 2026 (déploiement)
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
| `push` | **toutes les branches** (`"**"`) | Les trois travaux de validation, **et la livraison si la branche est `main`** |
| `pull_request` | **toutes les branches** (`"**"`) | Les trois travaux de validation seulement |
| `workflow_dispatch` | manuel, depuis l'interface GitHub | Les trois travaux de validation, **et la livraison si lancé sur `main`** |

**Trois déclencheurs, aucun autre.** Il n'y a ni déclencheur planifié
(`schedule`), ni déclencheur sur étiquette (`tags`), ni déclencheur sur
publication (`release`), et c'est délibéré :

- **Pas de `schedule`** : la chaîne n'éprouve rien qui varie avec le temps. Une
  exécution nocturne rejouerait à l'identique un résultat déjà connu.
- **Pas de `tags` ni de `release`** : la livraison suit `main`, pas un rituel
  d'étiquetage. Un projet individuel à échéance courte n'a pas de cycle de
  version à représenter ; ajouter des étiquettes ajouterait une cérémonie sans
  ajouter d'information.

#### Le déclencheur de la livraison, isolément

Le critère C19 demande que l'étape de livraison soit **intégrée à la chaîne et
exécutée une fois le packaging validé**. Voici son déclencheur, en entier :

| Question | Réponse |
|---|---|
| Quel travail ? | `publication`, dans le même fichier de chaîne |
| Sur quel événement ? | `push` ou `workflow_dispatch` — jamais `pull_request` |
| Sur quelle branche ? | `main` **uniquement** (`github.ref == 'refs/heads/main'`) |
| Sous quelle condition ? | `needs: [qualite, tests, image]` — les trois au vert |
| Effet 1 | Trois images publiées sur GitHub Container Registry |
| Effet 2 | Redéploiement demandé à l'hébergeur, si un crochet est configuré |
| Si un travail échoue | La publication **n'a pas lieu du tout** : `needs` ne se contourne pas |

**Pourquoi `main` seulement.** Une branche de chantier publie plusieurs fois par
jour un état non fusionné : l'hébergeur servirait un code qui n'est dans aucune
version de référence, et l'étiquette `:main` ne voudrait plus rien dire. La
validation, elle, reste sur toutes les branches — c'est le partage exact entre
« éprouver tôt » et « livrer ce qui est retenu ».

**Pourquoi jamais sur `pull_request`.** Une proposition de fusion venue d'un
dépôt tiers exécuterait alors du code capable d'écrire dans le registre. Le
projet est individuel et n'en reçoit pas, mais un droit qu'on ne s'accorde pas
ne peut pas être détourné.

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

Une fois l'indexation terminée, relever l'empreinte du corpus :

```bash
uv run python -m apps.rag.empreinte_corpus          # écrit apps/rag/chroma/EMPREINTE.json
```

Ce fichier — date, somme SHA-256 de `chroma.sqlite3`, modèle d'embarquement,
décompte de fragments par collection — voyage avec le corpus jusqu'à
l'hébergeur, et `/ai/sante` le restitue. C'est ce qui permet de constater que le
corpus déployé est bien celui du poste (§ 7.5 et décision 023). Relevé du
30/08/2026 : 21 189 fragments documentaires, 387 pédagogiques, 134 Mio de base
SQLite.

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

### 4.2 Les quatre travaux de la chaîne

Trois valident, **en parallèle** ; le quatrième livre et attend les autres.
Aucun ne porte `continue-on-error` : un contrôle qui ne peut pas faire échouer
la chaîne ne contrôle rien.

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

#### Travail 3 — « Construction et contrôle des images »

Ce travail est le **packaging** au sens du critère C19 : c'est sa validation
que la livraison attend. Il s'exécute deux fois, en matrice — une par image
applicative — parce que publier une image que rien n'a inspectée supprimerait
le contrôle au moment précis où il commence à servir.

| Étape | Commande | Rôle |
|---|---|---|
| 1 | `actions/checkout@v4` | — |
| 2 | `docker/setup-buildx-action@v3` | Constructeur |
| 3 | `docker/build-push-action@v6`, `push: false` | Construction **sans publication** |
| 4 | `docker buildx build --load` puis inspection | Contrôle du contenu |
| 5 | `docker image inspect --format '{{.Size}}'` | Relevé de la taille dans le récapitulatif |

Le cache est porté par le travail (`cache-from`/`cache-to: type=gha, mode=max`) :
la couche d'installation des dépendances prend **332 secondes mesurées** et n'a
pas à être rejouée tant que `uv.lock` ne change pas.

**Cinq contrôles sur le contenu de l'image**, exécutés dans le conteneur :

```
test ! -d /app/.git                            # l'historique Git n'y est pas
test ! -f /app/apps/rag/chroma/chroma.sqlite3  # le vector store n'y est pas
test -d /app/apps/rag/chroma                   # mais son point de montage existe
test "$(stat -c %U /app/apps/rag/chroma)" = "eduai"   # et appartient au compte sans privilège
test "$(stat -c %U /app)" = "eduai"            # /app n'appartient pas à root
```

Ils gardent un gain mesuré : de **10,1 Go** à l'origine, les images sont passées
à **5,22 Go** par `.dockerignore`, puis à **1,3 Go** le 30/08 par le retrait du
cache `uv`, de PySpark et du corpus. Sans contrôle, la taille dériverait sans
que rien ne le signale.

**Une limite à connaître, plutôt qu'à croire** : le contrôle du vector store
**ne peut pas échouer ici**. `apps/rag/chroma` étant dans `.gitignore`, il
n'est dans aucun clone, donc jamais dans une image construite par la chaîne. Ce
contrôle garde son sens pour une construction lancée depuis un poste, où le
corpus existe. Un contrôle qui ne peut pas échouer ne contrôle rien : celui-ci
en fait partie tant qu'il s'exécute en intégration continue, et il vaut mieux
l'écrire que le compter comme une garantie.

#### Travail 4 — « Publication des images et déclenchement du déploiement »

C'est l'étape de livraison. Elle est décrite en entier à la § 6, et son
déclencheur à la § 1.1.

### 4.3 Ce qui se saute, et pourquoi cela se voit

Les tests marqués `corpus` se sautent en intégration : reconstituer 7 868
documents demanderait les dumps et plusieurs heures. **Le saut apparaît dans le
récapitulatif de la chaîne**, et il est motivé ici. Un test sauté en silence
serait un test absent.

---

## 5. Construction des images — étapes des `Dockerfile`

**Trois images, et non plus une.** L'application web et le service IA sont
séparés parce que le référentiel évalue séparément l'API du jeu de données (C5,
en DRF) et l'API du service IA (C9, en FastAPI) : deux images rendent la
séparation lisible, et la panne de l'une ne fait pas tomber l'autre. La
troisième sert les embarquements.

| Image | Fichier | Rôle | Taille |
|---|---|---|---|
| Application web | `Dockerfile` | Django, DRF, interface, agents | 1,3 Go |
| Service IA | `service_ia/Dockerfile` | FastAPI, six points de terminaison | 1,26 Go |
| Serveur d'embarquement | `docker/ollama/Dockerfile` | Ollama + `mxbai-embed-large`, réseau privé | ~1,5 Go |

Les deux premières partagent leur structure ; les tailles ci-dessus datent du
30/08/2026, après trois retraits successifs :

| Retrait | Gain | Motif |
|---|---|---|
| `.dockerignore` (28/08) | 10,1 Go → 5,22 Go | Historique Git, données du pipeline, fichiers produits à l'exécution |
| Cache `uv` (`UV_NO_CACHE=1`, 30/08) | −1 816 Mio | Le cache reste dans la couche qui l'a créé, pour un contenu qui ne sert qu'à la construction |
| PySpark hors du socle (30/08) | −344 Mio | Importé par le seul extracteur big data, exécuté hors ligne (groupe `pipeline` de `pyproject.toml`) |
| Corpus vectoriel (30/08) | −219 Mio | Monté depuis un volume persistant (décision 023) |

**Le serveur d'embarquement mérite son propre paragraphe.** Le RAG embarque
chaque requête avant de chercher dans le corpus. Sur le poste, Ollama tourne sur
la machine ; chez l'hébergeur, rien n'écoute sur la boucle locale et **toute
recherche documentaire échouerait**. Le modèle est téléchargé à la construction
et non au premier démarrage, faute de quoi la première recherche de chaque
déploiement échouerait le temps que 670 Mio arrivent. Le modèle n'est pas un
réglage : le corpus a été indexé avec `mxbai-embed-large`, et l'interroger avec
un autre modèle ne donne pas de moins bons résultats — il en donne de dénués de
sens, les deux espaces vectoriels n'ayant aucun rapport.

### 5.1 Étapes du `Dockerfile` du service IA

Base `python:3.13-slim`.

| Étape | Contenu | Motif |
|---|---|---|
| 1 | Copie d'`uv` depuis son image officielle | Pas d'installation par `pip` |
| 2 | Variables d'environnement (`PYTHONUNBUFFERED`, …) | Journaux non tamponnés |
| 3 | Création de l'utilisateur `eduai`, UID 1000 | **Rien ne tourne en `root`** |
| 4 | `WORKDIR /app`, `chown` **du seul répertoire** | Un `chown -R` après installation dupliquerait l'arborescence dans une couche — c'est ce qui avait porté l'image à 10,1 Go |
| 5 | `USER eduai` | Bascule avant toute installation |
| 6 | `COPY pyproject.toml uv.lock` puis `uv sync --frozen --no-install-project --no-default-groups` | **Avant** la copie du code : la couche est réutilisée tant que le verrou ne change pas. `--no-default-groups` écarte PySpark et les outils de test, sans usage à l'exécution |
| 7 | `mkdir -p /app/apps/rag/chroma` | Point de montage du volume de corpus, créé vide et appartenant à `eduai`. Sans lui, le volume appartiendrait à `root` et SQLite ne pourrait pas y écrire son journal WAL (décision 018) |
| 8 | `COPY . .` puis `uv sync --frozen --no-default-groups` | Le code, filtré par `.dockerignore` |
| 9 | `EXPOSE 8100` | — |
| 10 | `HEALTHCHECK` — 30 s d'intervalle, 5 s de délai, 40 s de démarrage, 3 tentatives | C'est lui que `depends_on: condition: service_healthy` attend |
| 11 | `CMD ["./docker/entree-service-ia.sh"]` | Un script, non une ligne de commande. Il lit `${PORT:-8100}`, appelle l'exécutable du venv — **pas** `uv run`, qui resynchroniserait l'environnement au démarrage — et passe les en-têtes de proxy |

L'ordre des étapes 6 et 8 est le point de conception de ce fichier : inverser
les deux ferait réinstaller toutes les dépendances à chaque modification du
code — 332 secondes à chaque construction.

#### Le port d'écoute : une contrainte qui ne se voit pas en local

**En développement, le port est libre.** On choisit le sien, `docker-compose`
publie 8100, et tout concorde. **Chez l'hébergeur, il est imposé** : Railway
attribue un port par la variable `PORT` et n'interroge que celui-là.

Les deux images lisent donc `PORT` dans leur script de démarrage, avec une
valeur de repli — 8000 pour l'application web, 8100 pour le service IA — qui
sert au lancement local et au fichier de composition.

Trois points à connaître, chacun payé une fois :

- **La forme exec d'un `CMD` n'étend pas les variables d'environnement.**
  Écrire `--port ${PORT}` dans `CMD ["...", "--port", "${PORT}"]` transmet la
  chaîne littérale. C'est pourquoi le port se lit dans un script, et non dans
  la ligne de commande.
- **La sonde de vivacité doit lire le même port.** Une sonde interrogeant 8100
  en dur déclare le conteneur malade dès qu'un autre port est imposé — soit
  exactement quand le service va bien mais écoute ailleurs.
- **Un conteneur qui écoute sur le mauvais port ne journalise rien
  d'anormal.** Il sert, correctement, à une adresse que personne n'interroge.
  La plateforme répond « Application failed to respond » et le composant en
  cause n'a rien à signaler de son point de vue. Diagnostic complet :
  `docs/incidents/2026-08-30-service-injoignable-port-en-dur.md`.

### 5.2 Ce que le `Dockerfile` de l'application web ajoute

Mêmes étapes, avec deux différences :

| Étape | Contenu | Motif |
|---|---|---|
| `collectstatic` à la **construction** | Les fichiers statiques sont collectés une fois, dans l'image | Au démarrage, la collecte rallongerait chaque redémarrage et écrirait dans un système de fichiers éphémère. Ses erreurs arrêtent la construction, au lieu d'apparaître en production sous la forme d'une page sans feuille de style |
| `CMD ["./docker/entree-web.sh"]` | Migrations, puis `uvicorn` sur `$PORT` | Le port est **imposé par l'hébergeur** via `$PORT`, avec une valeur de repli pour le lancement local. Un seul travailleur : la couche de canaux et le compteur Prometheus sont en mémoire de processus, plusieurs travailleurs les fragmenteraient sans qu'aucune erreur n'apparaisse |

Les trois variables `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` et
`EDUAI_DATA_PASSWORD` sont définies **pour la seule durée** de l'instruction
`collectstatic`, avec des valeurs sans usage : les réglages refusent de se
charger sans elles, et la collecte n'ouvre aucune connexion. Aucune ne subsiste
dans l'image — ce ne sont pas des valeurs de repli.

---

## 6. Livraison

L'étape de livraison est le travail `publication` de la chaîne. Elle s'exécute
**après** les trois travaux de validation, et seulement s'ils passent — c'est
ce que le critère C19 demande de démontrer.

### 6.1 Ce que fait la livraison, dans l'ordre

| # | Tâche | Détail |
|---|---|---|
| 1 | Ouvrir une session au registre | `ghcr.io`, avec le jeton de la chaîne. **Aucun secret à créer ni à renouveler** — un secret qu'on n'a pas à gérer est un secret qui ne fuit pas |
| 2 | Établir les noms d'images | Le registre exige des minuscules, le propriétaire du dépôt porte des majuscules. Sans conversion, la publication échoue sur un message qui n'en dit pas la cause |
| 3 | Publier l'application web | `ghcr.io/<dépôt>/web:main` et `:<empreinte du commit>` |
| 4 | Publier le service IA | `ghcr.io/<dépôt>/service-ia:main` et `:<empreinte du commit>` |
| 5 | Publier le serveur d'embarquement | `ghcr.io/<dépôt>/embarquement:main` et `:<empreinte du commit>` |
| 6 | Demander le redéploiement | POST sur le crochet `RAILWAY_CROCHET_DEPLOIEMENT`, s'il est configuré |
| 7 | Écrire le récapitulatif | Déclencheur, commit livré, images, état du déploiement — lisible sans dérouler les journaux |

**Deux étiquettes par image, deux usages.** `:main` est ce que l'hébergeur
déploie ; l'empreinte de commit est ce qui permet de dire quelle version tourne
et d'y revenir. Une étiquette mobile seule rendrait tout retour arrière
impossible.

### 6.2 Les droits accordés à la chaîne

```yaml
permissions:
  contents: read
  packages: write
```

Rien d'autre — et notamment pas le droit d'écrire dans le dépôt. Le jeton de la
chaîne peut publier une image ; il ne peut pas modifier une ligne de code.

### 6.3 Le déclenchement du déploiement

**Choix : un crochet, et non les identifiants du compte d'hébergement.**
Motivation : un crochet ne peut faire qu'une chose, redéployer ce service. Des
identifiants pourraient tout faire, y compris supprimer le projet.

**Choix : son absence ne fait pas échouer la chaîne.** Motivation : les images
sont alors publiées et vérifiées — la livraison a bien eu lieu. Ce qui manque
est le déclenchement automatique, et le récapitulatif l'écrit en clair
(`Déploiement : manuel`) plutôt que de laisser croire à un déploiement qui n'a
pas été demandé.

Le `curl` porte `--fail`. Sans lui, `curl` rend 0 sur une réponse 4xx ou 5xx, et
la chaîne annoncerait un déploiement demandé alors que l'hébergeur l'a refusé —
le motif exact des incidents déjà documentés par ce projet.

**Variante possible**, si l'hébergeur n'expose pas de crochet entrant :
brancher son intégration GitHub, qui redéploie sur poussée dans `main`. Elle
reconstruit alors l'image chez l'hébergeur, en doublon de celle que la chaîne
vient de publier ; les images du registre restent la référence pour dire ce qui
tourne.

### 6.4 Livraison locale, sans registre

Toujours valable, et utile pour éprouver une image avant de la pousser :

| Étape | Commande |
|---|---|
| Construire | `docker compose build service_ia` |
| Démarrer ou redémarrer | `docker compose up -d service_ia` |
| Forcer la recréation après un changement de configuration | `docker compose up -d --force-recreate service_ia` |
| Vérifier la santé | `docker compose ps` — colonne `Status` |
| Consulter les journaux | `docker compose logs -f service_ia` |

**Le piège à connaître** : `docker compose restart` **ne relit pas** le fichier
de composition. Un changement de port, de variable ou de réseau exige
`--force-recreate`. C'est ce qui avait laissé PostgreSQL exposé à tout le réseau
alors que le fichier était corrigé.

---

## 7. Déploiement sur Railway

**Hébergeur retenu : Railway** (décision 020), plan payant, environ 5 $/mois. Ce
qui est déployé, et ce qui ne l'est pas :

| Composant | Déployé | Raison |
|---|---|---|
| Application web Django (C17, C5) | oui | C'est l'objet de la démonstration |
| Service IA FastAPI (C9) | oui | Seconde API, évaluée séparément |
| Serveur d'embarquement Ollama | oui | Sans lui, aucune recherche RAG n'aboutit |
| PostgreSQL | oui | Les deux bases, `eduai_app` et `eduai_data` |
| Redis | non | `InMemoryChannelLayer` en usage, et le seul consommateur WebSocket n'a aucun client (réserve 1) |
| Prometheus, Grafana | non | Le jury doit voir l'application vivre, pas la pile d'observabilité. Le monitorage JSON Lines, lui, continue de fonctionner sur le serveur : c'est lui la preuve de C20 |

### 7.1 Provisionner les services

Dans l'ordre, chaque étape dépendant de la précédente :

1. **Créer le projet**, puis y ajouter un service **PostgreSQL**. Relever l'URL
   de connexion interne qu'il expose.
2. **Ajouter le serveur d'embarquement**, depuis l'image
   `ghcr.io/<dépôt>/embarquement:main`. **Ne lui donner aucun domaine public** :
   il n'a ni authentification ni limitation de débit, et n'en a pas besoin tant
   qu'il reste sur le réseau privé du projet. Relever son adresse interne, de la
   forme `http://<nom-du-service>:11434`.
3. **Ajouter le service IA**, depuis `ghcr.io/<dépôt>/service-ia:main`, avec un
   domaine public.
4. **Ajouter l'application web**, depuis `ghcr.io/<dépôt>/web:main`, avec un
   domaine public.

**Deux services exposés sur trois, et c'est délibéré.** Le service IA porte un
domaine parce que le référentiel l'évalue comme une API à part entière (C9) :
son contrat OpenAPI à `/ai/docs` est une pièce que le jury doit pouvoir ouvrir.
Il est protégé par clé de service, quotas et plafond de concurrence. Le serveur
d'embarquement, lui, n'a **aucune** de ces protections et n'en a pas besoin tant
qu'il reste sur le réseau privé : lui donner un domaine offrirait à tout venant
un service d'inférence gratuit.

Le registre étant celui d'un dépôt public, les images sont lisibles sans
identifiants. Si le dépôt passait en privé, il faudrait fournir à l'hébergeur un
jeton de lecture de paquets.

### 7.2 Les variables d'environnement

Toutes les valeurs viennent de l'environnement, aucune n'est dans une image.
Les valeurs par défaut sont **asymétriques** : un secret absent interrompt le
démarrage, il ne bascule pas sur une valeur permissive.

**Application web :**

| Variable | Valeur | Effet si absente |
|---|---|---|
| `DJANGO_SECRET_KEY` | secret, généré une fois | Démarrage refusé |
| `DJANGO_DEBUG` | `False` | Vaut `False` par défaut — la valeur sûre |
| `DJANGO_ALLOWED_HOSTS` | `<sous-domaine>.up.railway.app` | Toute requête refusée en 400 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<sous-domaine>.up.railway.app` | Tout formulaire refusé en 403 |
| `DJANGO_DERRIERE_PROXY` | `True` | **Boucle de redirection infinie** — voir ci-dessous |
| `DJANGO_DB_NAME` | `eduai_app` | — |
| `POSTGRES_HOST`, `POSTGRES_PORT` | ceux du service PostgreSQL | Démarrage refusé |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | **`eduai_application`** et son mot de passe — **jamais le superutilisateur** | Démarrage refusé |
| `EDUAI_DATA_USER`, `EDUAI_DATA_PASSWORD` | `eduai_lecture` et son mot de passe | L'API du jeu de données ne répond plus |
| `GROQ_API_KEY` | clé du fournisseur | Bascule sur le repli local, indisponible ici |
| `OLLAMA_BASE_URL` | adresse interne du serveur d'embarquement | Aucune recherche RAG n'aboutit |
| `EDUAI_QUOTA_GENERATIONS_PAR_JOUR` | `5` | Valeur par défaut prudente |
| `EDUAI_PLAFOND_GENERATIONS_PAR_JOUR` | `200` | Valeur par défaut prudente |
| `MONITORAGE_REPERTOIRE` | chemin sur volume persistant | Les traces disparaîtraient à chaque redéploiement |
| `EDUAI_MEDIA_REPERTOIRE` | `/app/media`, sur volume persistant | Les photos de profil disparaîtraient à chaque redéploiement |
| `PORT` | **fournie par l'hébergeur**, à ne pas définir soi-même | Repli sur 8000 (web) ou 8100 (service IA) — le service écoute alors un port que la plateforme n'interroge pas, et répond « Application failed to respond » (incident 008) |

**`DJANGO_DERRIERE_PROXY=True` n'est pas un réglage de confort.** L'hébergeur
place un proxy inverse devant l'application et lui transmet les requêtes en
clair. Sans cette variable, Django voit du HTTP, applique `SECURE_SSL_REDIRECT`,
renvoie vers HTTPS, et la requête revient par le même chemin : la boucle est
infinie et le service paraît en panne. C'est le cas prévu par la décision 008,
et c'est ici qu'il se présente pour la première fois.

**Service IA :** les mêmes variables de base et de fournisseur, plus
`SERVICE_IA_CLES` — une clé par consommateur, aucune valeur de repli dans le
code, puisqu'une clé par défaut est une clé publique.

### 7.3 Créer et peupler les deux bases

Une seule instance PostgreSQL, **deux bases distinctes** (décision 006) :
`eduai_app` pour l'application, `eduai_data` pour le jeu de données. PostgreSQL
n'autorisant pas de requête inter-bases sans extension, l'isolation est
structurelle et non conventionnelle : le pipeline peut recharger son jeu de
données sans qu'aucune erreur de ciblage n'atteigne les comptes des apprenants.

**`eduai_app`** se crée par les migrations, appliquées au démarrage par
`docker/entree-web.sh`. Rien à faire à la main.

**`eduai_data`** se charge depuis l'export produit sur le poste :

```bash
# Sur le poste — produit l'archive, la vérifie, relève sa volumétrie
./data_pipeline/load/exporter_jeu_donnees.sh

# Vers le serveur — création de la base, puis chargement
createdb  -h <hôte> -p <port> -U <rôle> eduai_data
gunzip -c data_pipeline/data/exports/eduai_data-<horodatage>.sql.gz \
  | psql -h <hôte> -p <port> -U <rôle> -d eduai_data
```

Le fichier `sauvegarde_eduai_data.sql` (18 Mo, décompressé) est la même chose
sous forme non comprimée ; il se charge par `psql -f`.

**Pourquoi un export et non un rejeu du pipeline sur le serveur** : le pipeline
part des sources brutes, dont un dump Stack Exchange de plusieurs gigaoctets,
ni versionnées ni transférables raisonnablement. Le résultat, lui, tient en
quelques dizaines de mégaoctets. **Pourquoi le schéma et les données dans le
même fichier** : les rejouer séparément fait deux opérations là où une suffit,
et ouvre la possibilité qu'elles divergent.

**Ce que l'export ne porte pas : les rôles.** `pg_dump` exporte une base, pas
les comptes du serveur. Le rôle de lecture seule dont dépend l'API du jeu de
données (C5) est à créer sur le serveur cible :

**Deux rôles, et aucun des deux n'est superutilisateur.** Le rôle applicatif
possède le schéma de `eduai_app`, ce que les migrations Django exigent ; le rôle
de lecture ne peut rien faire d'autre que lire `eduai_data`. Les faire porter
par le superutilisateur du serveur — ce qui était le cas jusqu'au 31/08 —
annulerait les trois niveaux de garantie décrits ici : une injection aboutie
s'exercerait sur les deux bases, les rôles et l'instance entière.

```sql
-- Rôle applicatif, propriétaire du schéma de eduai_app
CREATE ROLE eduai_application LOGIN PASSWORD '<secret>';
GRANT CONNECT ON DATABASE eduai_app TO eduai_application;
-- CREATE, et pas seulement USAGE : Django crée des tables à chaque migration
GRANT USAGE, CREATE ON SCHEMA public TO eduai_application;
```

Les objets déjà migrés doivent lui être transférés, faute de quoi la prochaine
migration échouera sur un `ALTER TABLE` — les privilèges ne suffisent pas, il
faut la propriété. **Objet par objet, jamais par `REASSIGN OWNED`** : cette
commande s'applique à tout ce que l'ancien rôle possède, y compris des objets
partagés de l'instance, et `postgres` est le rôle d'amorçage du serveur. Les
séquences rattachées à une colonne d'identité suivent leur table et ne se
transfèrent pas séparément — PostgreSQL le refuse.

```sql
-- Rôle de lecture seule, dont dépend l'API du jeu de données (C5)
CREATE ROLE eduai_lecture LOGIN PASSWORD '<secret>';
GRANT CONNECT ON DATABASE eduai_data TO eduai_lecture;
GRANT USAGE ON SCHEMA public TO eduai_lecture;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO eduai_lecture;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO eduai_lecture;

-- Fermer chaque base au pseudo-rôle PUBLIC : PostgreSQL accorde par défaut la
-- connexion à toute base, donc chaque rôle peut ouvrir une session sur celle
-- qui ne le concerne pas. L'isolation des deux bases (décision 006) n'est
-- complète qu'avec ces deux lignes.
REVOKE CONNECT ON DATABASE eduai_app  FROM PUBLIC;
REVOKE CONNECT ON DATABASE eduai_data FROM PUBLIC;
GRANT  CONNECT ON DATABASE eduai_data TO eduai_lecture;
```

**Ouvrir le tunnel** — la base de l'hébergeur n'a pas d'adresse publique, et
il n'est pas souhaitable de lui en donner une :

```bash
railway connect --tunnel-only -P 15432 Postgres
# puis, dans un autre terminal, psql -h 127.0.0.1 -p 15432 -U postgres ...
```

Le tunnel affiche le mot de passe du superutilisateur en clair dans le
terminal. En tenir compte : refermer le tunnel après usage, et ne pas laisser
la trace dans un fichier de journal.

**Vérifier après chargement, et non supposer.** L'export écrit à côté de
l'archive un fichier `.volumetrie` relevé **avant** l'export ; les mêmes
décomptes se relisent sur le serveur :

```sql
SELECT 'documents=' || count(*) FROM document
UNION ALL SELECT 'mots_cles=' || count(*) FROM mot_cle
UNION ALL SELECT 'sources='   || count(*) FROM source;
```

C'est le contrôle qui manquait le 27/08, quand un chargement s'est annoncé
réussi sur une base restée vide (incident 001).

**Relevé du 31/08/2026, chargement réel** : 6 836 documents, 1 211 mots-clés,
5 sources sur le serveur — identiques au relevé d'avant export. 17 tables
créées.

**Vérifier le rôle dans les deux sens.** Un rôle de lecture seule dont on n'a
éprouvé que la lecture n'est pas éprouvé :

| Ce qui a été tenté avec `eduai_lecture` | Attendu | Constaté |
|---|---|---|
| `SELECT count(*) FROM document` | 6 836 | **6 836** |
| `DELETE FROM document` | refus | **permission denied for table document** |
| `CREATE TABLE …` | refus | **permission denied for schema public** |
| Connexion à `eduai_app` | refus | **permission denied for database** |

Le dernier point a demandé une correction : PostgreSQL accorde par défaut la
connexion à toute base au pseudo-rôle `PUBLIC`. `eduai_lecture` pouvait donc
ouvrir une session sur la base applicative — sans y lire quoi que ce soit,
faute de `SELECT`, mais la porte était ouverte. Refermée par :

```sql
REVOKE CONNECT ON DATABASE eduai_app FROM PUBLIC;
```

Sans effet sur les deux services, qui se connectent en superutilisateur — ce
qui est en soi une réserve, la huitième.

### 7.4 Transférer le corpus vectoriel

### La purge par ancienneté

Chaque source déclare une durée de conservation — 365 jours pour les sources
publiques, **90 jours pour les productions d'apprenants**, sans terme pour le
corpus pédagogique. La purge supprime les documents qui la dépassent, et les
cascades du schéma emportent leurs spécialisations, leurs collectes et leurs
rattachements.

```bash
uv run python -m data_pipeline.load.purge --a-blanc   # compte, n'écrit pas
uv run python -m data_pipeline.load.purge             # supprime
```

**Toujours à blanc d'abord.** La commande dénombre par source avant de
supprimer, et **n'engage la transaction que si la base a supprimé exactement
ce qui avait été annoncé** : un écart annule tout. C'est la leçon de
l'incident 001 — un chargement s'était annoncé réussi sur une base restée
vide, parce qu'il comptait ce qu'il croyait avoir écrit.

**L'ordonnancement relève de l'hébergeur, pas du dépôt.** Le dépôt fournit la
commande ; il ne décide pas quand elle passe. Chez Railway, une tâche planifiée
sur le service de l'application suffit :

```
0 3 * * *   cd /app && python -m data_pipeline.load.purge
```

Choix : ne pas embarquer d'ordonnanceur. Motivation : un `cron` dans l'image
s'exécuterait dans chaque conteneur, y compris ceux qu'on lance pour une
démonstration ou un test, et supprimerait des données depuis un environnement
qui n'était pas censé écrire. La planification appartient à l'endroit qui sait
combien d'exemplaires tournent.

**État au 4 septembre 2026 : aucun document n'est échu.** Le corpus a dix
jours, la plus courte conservation est de 90. La commande le dit et ne fait
rien — c'est le comportement attendu, et il est vérifié par les tests.

### Le volume des médias

Les photos de profil déposées par les apprenants sont les **seuls** fichiers que
l'application écrit sur disque. `media/` est exclu de l'image : au démarrage, le
répertoire est vide, et le système de fichiers d'un conteneur est éphémère.
**Sans volume, une photo envoyée disparaît au redéploiement suivant** — sans
erreur, sans trace, l'apprenant retrouvant simplement son avatar par défaut.

```bash
railway volume add -m /app/media        # sur le service de l'application web
railway volume list                     # vérifier le point de montage
```

Le chemin par défaut est `/app/media`. Pour en monter un autre, renseigner
`EDUAI_MEDIA_REPERTOIRE` : le réglage lit cette variable, il n'est pas figé
dans le code.

**Le point de montage existe déjà dans l'image**, créé vide et appartenant au
compte sans privilège, pour la même raison que celui du corpus : un volume
monté sur un chemin absent de l'image appartiendrait à `root`, et le conteneur,
qui ne tourne pas en `root`, ne pourrait rien y écrire.

Le démarrage le vérifie en écrivant réellement un fichier témoin, et non en
lisant des bits de permission — qui diraient « accessible » là où l'écriture
échoue. En cas d'échec, le service démarre quand même : ne pas pouvoir déposer
une photo n'empêche ni de se connecter ni de suivre un cours. Le journal porte
alors trois lignes d'avertissement explicites. Sans ce contrôle, la panne
n'apparaîtrait qu'au premier apprenant qui essaie, sous forme d'erreur 500.

Les avatars Koda, eux, ne demandent aucun volume : ce sont des fichiers
statiques livrés dans l'image.

### Le volume du corpus vectoriel

Le corpus **n'est pas dans les images** (décision 023) : il est dans
`.gitignore`, donc absent de tout clone, et la chaîne ne peut pas embarquer ce
qu'elle ne voit pas.

Procédure éprouvée le 31/08/2026, dans cet ordre.

**1. Créer le volume**, monté sur `/app/apps/rag/chroma` :

```bash
railway volume add -m /app/apps/rag/chroma        # sur le service lié
railway volume list                                # vérifier le point de montage
```

Un volume Railway appartient à **un** service. Le service IA a le sien ; si
l'application web doit interroger le corpus elle aussi, il lui en faut un
second, et le corpus est téléversé deux fois. Le chemin est écrit en dur dans
quatre modules : ce n'est pas un réglage.

**2. Relever l'empreinte** sur le poste, avant tout envoi :

```bash
uv run python -m apps.rag.empreinte_corpus
```

**3. Téléverser**, l'empreinte **en dernier** — c'est elle qui atteste que le
transfert est complet, et un `EMPREINTE.json` posé sur un corpus partiel
mentirait.

**Lire la sortie de chaque montée, et ne pas se fier à l'ordre seul.** Cette
règle protège d'une interruption à la fin ; elle ne protège pas d'un échec au
début suivi d'une reprise. Le 31/08, la première montée a échoué sur un
`Timeout` et les suivantes ont réussi, empreinte comprise : le corpus était
incomplet et attesté complet (réserve 9). **Comparer les tailles, volume contre
poste, avant de conclure** :

```bash
railway volume files --volume <volume> list /<collection> --json   # tailles distantes
```


```bash
railway volume files --volume <volume> upload apps/rag/chroma/<collection> /<collection>
railway volume files --volume <volume> upload apps/rag/chroma/chroma.sqlite3 /chroma.sqlite3
railway volume files --volume <volume> upload apps/rag/chroma/EMPREINTE.json /EMPREINTE.json
```

**4. Donner les fichiers au compte sans privilège.** `railway volume files
upload` écrit en **root**, or le conteneur tourne en `eduai` (uid 1000) :

```bash
railway ssh -s <service> -- "chown -R 1000:1000 /app/apps/rag/chroma"
```

**Sans cette étape, la recherche échoue en 503** avec `attempt to write a
readonly database`. SQLite écrit son journal WAL et ses verrous même pour une
lecture (décision 018) : un corpus que le processus ne peut pas écrire est un
corpus qu'il ne peut pas lire. C'est la deuxième fois que ce projet rencontre
ce mur, sous une forme différente — la première, le 29/08, venait d'un montage
déclaré en lecture seule.

**5. Redéployer** le service, puis **vérifier** que `/ai/sante` renvoie
l'empreinte attendue (§ 7.5) et qu'une recherche aboutit.

**Contrôle de bout en bout, éprouvé** : le fichier a été retéléchargé depuis le
volume et sa somme SHA-256 comparée à celle du poste — identiques. Le compteur
d'occupation affiché par `railway volume list` retarde de plusieurs minutes ; il
annonçait 32 Mo pour 219 Mio réellement transférés. **Ne pas conclure sur ce
compteur** : la taille exacte se lit dans `railway volume files list / --json`.

### 7.5 Mettre à jour le corpus — étape manuelle, et assumée

Cette étape n'est pas automatisable, et la documenter fait partie du critère :
**toutes** les étapes de la chaîne, y compris celles qui restent manuelles.

| # | Action | Où |
|---|---|---|
| 1 | Réindexer : `uv run python -m apps.rag.indexation_corpus` | Poste, hors ligne |
| 2 | Relever l'empreinte : `uv run python -m apps.rag.empreinte_corpus` | Poste |
| 3 | Téléverser le corpus **et** son empreinte sur le volume | Poste → hébergeur |
| 4 | Redémarrer les deux services qui montent le volume | Hébergeur |
| 5 | Comparer l'empreinte servie par `/ai/sante` à celle du poste | Depuis n'importe où |

**Pourquoi la réindexation reste hors ligne.** L'embarquement traite une
vingtaine de fragments par minute : 21 189 fragments demandent plus de dix-sept
heures. Aucun démarrage de conteneur ne peut porter cela — l'hébergeur
déclarerait le service défaillant et le redémarrerait bien avant la fin,
indéfiniment. Ce n'est pas une option lente, c'est une option qui n'aboutit
jamais.

**Ce que l'étape 5 protège.** Depuis que le corpus voyage séparément du code,
les deux peuvent diverger : un corpus réindexé mais non téléversé laisse
tourner l'application sur l'ancien, sans qu'aucune erreur ne se produise.
L'empreinte ne l'empêche pas — elle le rend constatable en une requête :

```bash
curl -s https://<service-ia>.up.railway.app/ai/sante | python3 -m json.tool | grep -A 8 empreinte
```

Une date ou un décompte qui ne sont pas ceux du poste signalent que le
téléversement n'a pas eu lieu, ou qu'il est incomplet.

### 7.6 Vérifier le déploiement

Ne pas considérer le déploiement fait parce qu'il ne renvoie pas d'erreur. Le
script `docker/verifier-deploiement.sh` passe les sept contrôles de la § 8 sur
une URL publique et rend un compte-rendu :

```bash
./docker/verifier-deploiement.sh https://<web>.up.railway.app https://<service-ia>.up.railway.app
```

---

## 8. Vérifier le déploiement — les sept contrôles

**Ne pas considérer le déploiement fait parce qu'il ne renvoie pas d'erreur.**
Ce projet a documenté sept incidents dont le motif commun est qu'une action et
son effet ne coïncident pas sans qu'on aille le constater : un extracteur
annonçant un succès à zéro enregistrement, un chargeur annonçant 6 836
documents sur une base vide, une sonde se déclarant branchée sans recevoir
aucun rappel.

Chaque contrôle porte donc sur un **effet**, jamais sur une déclaration.

| # | Contrôle | Ce qui est constaté | Comment |
|---|---|---|---|
| 1 | HTTPS effectif | Certificat valide, **et** trafic en clair redirigé — un site qui répond en HTTPS mais sert aussi en clair laisse passer le cookie de session avant toute chance de le protéger | Deux requêtes, `https://` puis `http://` |
| 2 | Cookies `Secure` | L'attribut `Secure` sur le cookie CSRF et sur le cookie de session. Il ne se voit pas dans une page : il se lit dans l'en-tête `Set-Cookie` | En-têtes de `/auth/login/`, puis fichier de cookies après connexion |
| 3 | Pages authentifiées | L'anonyme est **renvoyé** vers la connexion, et la personne connectée obtient 200. La première moitié compte autant que la seconde | `/courses/generator/` sans session, puis avec |
| 4 | Corpus et empreinte | Le corpus est monté, et son empreinte est **celle du poste** — date, SHA-256, décompte par collection | `/ai/sante`, comparé à `apps/rag/chroma/EMPREINTE.json` |
| 5 | Recherche RAG | Des fragments reviennent, **et chacun porte une attribution**. Une réponse sans source n'est pas attribuable, et c'est l'attribution qui distingue une recherche documentaire d'une génération plausible | `POST /ai/recherche` |
| 6 | Génération de cours | Un cours est réellement produit, avec sa durée et sa taille | `POST /ai/cours` — **appel facturé**, explicite |
| 7 | Quota et monitorage | Le décompte de générations s'affiche sur la page, et le journal JSON Lines **s'écrit sur le serveur** | Page de génération connectée, puis `monitorage.lignes_ecrites_sur_disque` |

### 8.1 Exécution

```bash
SERVICE_IA_CLE=<clé> \
EDUAI_UTILISATEUR=<adresse> EDUAI_MOT_DE_PASSE=<mot de passe> \
./docker/verifier-deploiement.sh https://<web>.up.railway.app https://<service-ia>.up.railway.app
```

Le script rend trois compteurs : **réussis**, **en échec**, **non vérifiés**. Il
sort en code 1 dès qu'un contrôle échoue.

**Les « non vérifiés » ne sont pas des réussites**, et le script le dit à chaque
exécution en rappelant les variables qui les débloqueraient. C'est délibéré :
un contrôle sauté en silence est un contrôle absent.

**Le contrôle 6 ne s'exécute pas par défaut** — il appelle le fournisseur, donc
il coûte. Il se déclenche par `VERIFIER_GENERATION=1`. Motivation : une
vérification qu'on hésite à relancer n'est pas relancée ; mieux vaut un contrôle
explicitement optionnel qu'un contrôle complet qu'on n'ose plus lancer.

### 8.2 Ce que ces contrôles ne couvrent pas

| Non couvert | Pourquoi |
|---|---|
| Le quota individuel atteignant réellement 0 | Épuiser le plafond consommerait cinq générations facturées à chaque vérification. Le déclenchement au seuil est éprouvé par les tests automatisés (`tests/test_quotas.py`) ; sur le serveur, on constate que le décompte existe et s'affiche |
| Le rendu visuel des pages | Aucun test de bout en bout d'interface, arbitrage documenté dans `strategie_tests.md` |
| La charge | Aucun tir de montée en charge ; le plafond de concurrence borne le risque, il ne le mesure pas |

---

## 9. Ce que la chaîne ne fait pas

Énoncé pour qu'on ne le suppose pas.

| Absent | Raison |
|---|---|
| Exécution planifiée | La chaîne n'éprouve rien qui varie avec le temps |
| Téléversement automatique du corpus | Le corpus est produit hors ligne, en dix-sept heures d'embarquement : aucune chaîne ne peut le porter. L'étape reste manuelle et documentée (§ 7.5) |
| Chargement automatique de `eduai_data` | Un rechargement déclenché par une poussée écraserait le jeu de données servi. Il reste une opération décidée, jamais un effet de bord |
| Retour arrière automatique | Chaque image porte l'empreinte de son commit : le retour se fait en redéployant l'étiquette voulue, à la main |
| Contrôle de couverture chiffré | Choix documenté dans `strategie_tests.md` : un taux mesure les lignes exécutées, pas les comportements éprouvés |
| Tests de bout en bout de l'interface | Coût élevé au regard de l'échéance |
| Analyse de sécurité des dépendances | **Manque réel**, non couvert par un choix ; ni `pip-audit` ni équivalent n'est branché |

Le dernier est le seul de la liste qui ne soit pas un arbitrage assumé mais une
lacune : il serait peu coûteux à combler et ne l'a pas été.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `.github/workflows/integration-continue.yml` | La chaîne, livraison comprise |
| `Dockerfile`, `service_ia/Dockerfile`, `docker/ollama/Dockerfile`, `.dockerignore` | La construction des trois images |
| `docker/verifier-deploiement.sh` | Les sept contrôles sur l'URL publique |
| `data_pipeline/load/exporter_jeu_donnees.sh` | L'export du jeu de données vers l'hébergeur |
| `apps/rag/empreinte_corpus.py` | L'empreinte qui rend le corpus vérifiable |
| `decisions/020`, `decisions/021`, `decisions/023` | L'hébergeur, le périmètre déployé, le transport du corpus |
| `docker-compose.yml` | Les quatre services |
| `strategie_tests.md` | Ce que les tests éprouvent et pourquoi |
| `cadre_technique.md` | La pile et les environnements |
| `incidents/` | Les pannes dont plusieurs contrôles ci-dessus découlent |
