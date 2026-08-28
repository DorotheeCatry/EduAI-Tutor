# Matrice de traçabilité — RNCP 37827

**Date du relevé :** 28 août 2026
**Compétence visée :** C19 (épreuve E4) — traçabilité
**Objet :** indexer, pour chacune des 21 compétences, la preuve et son emplacement

---

## Comment lire ce document

Les cinq rapports écrits font deux à cinq pages chacun. Ils ne peuvent donc pas
démontrer, seulement indexer. **Ce document est l'index**, et il est le cœur du
rendu plutôt qu'une annexe.

Chaque ligne porte une **colonne « état »** dont les valeurs sont volontairement
peu nombreuses :

| Valeur | Signification |
|---|---|
| **vérifié** | La preuve existe et a été exécutée ou lue pendant ce relevé. |
| **présent** | La preuve existe dans le dépôt, mais n'a pas été rejouée aujourd'hui. |
| **partiel** | Une partie de la preuve existe, une autre manque. La ligne dit laquelle. |
| **absent** | Aucune preuve. La ligne dit ce qu'il faut produire. |

Une case vide identifiée est traitable ; une case vide masquée ne l'est pas.
Aucune ligne de ce tableau n'est laissée sans état.

### Réserve sur les intitulés

Le référentiel versionné dans `reference/` est le **schéma** des compétences et
des épreuves, non le texte intégral de leurs libellés. Les intitulés de la
colonne « compétence » ci-dessous sont donc des **résumés de travail**, fidèles
au schéma et au regroupement par épreuve, mais ils ne reproduisent pas le
libellé officiel mot pour mot. Là où le libellé exact décide de ce qui compte
comme preuve — c'est le cas de C11 et C12 — la ligne le signale.

---

## Bloc 1 — collecte, stockage et mise à disposition des données (épreuve E1)

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C1 | Extraction de données depuis cinq types de sources | **vérifié** | 5 extracteurs distincts, un par type : API REST (Stack Overflow), scraping (doc Python), fichiers, base de données, big data. Socle commun avec point de lancement, gestion d'erreurs différenciée, idempotence, bilan persisté | `data_pipeline/extract/s1_*.py` à `s5_*.py`, `base_extractor.py` |
| C2 | Requêtes dans deux langages | **vérifié** | 20 fichiers `.sql` en fichiers dédiés, jamais en chaînes inline. SQL PostgreSQL pour le schéma et la collecte S4 ; **Spark SQL** pour la conversion, la sélection et la volumétrie du dump big data. En-têtes documentant objectif, filtrage, jointures et optimisations | `data_pipeline/load/sql/`, `data_pipeline/extract/sql/` dont 3 `*.spark.sql` |
| C3 | Agrégation et nettoyage des données | **vérifié** | Trois modules distincts — normalisation des dates (ISO 8601), homogénéisation des formats, déduplication. 6 876 entrants, 40 doublons retirés, 6 836 sortants. Clés de déduplication sur identifiant et empreinte SHA-256 du contenu, jamais sur l'URL ni le titre | `data_pipeline/transform/` (6 modules) |
| C4 | Base de données et modélisation | **vérifié** | Base `eduai_data` en PostgreSQL 16 conteneurisé, **17 tables**, 6 836 documents chargés, 1 211 mots-clés, 20 544 rattachements, 0 rejet. MCD, MLD, dictionnaire de données, document de conformité RGPD. Isolation structurelle d'avec `eduai_app` (décision 006) | `data_pipeline/load/`, `docs/mcd_eduai_data.md`, `docs/mld_eduai_data.md`, `docs/dictionnaire_donnees_eduai_data.md`, `docs/rgpd_eduai_data.md`, décisions 006, 007, 009 |
| C5 | API REST exposant le jeu de données | **vérifié** | Django REST Framework, 3 jeux de vues et une vue de statistiques, lecture seule garantie par un routeur de base qui lève sur écriture. 6 753 documents exposés sur 6 836 — le filtre de licence est dans le queryset de base, pas dans chaque vue. Authentification, permissions, throttling, pagination, OpenAPI | `apps/api_data/`, `docs/securite_api_donnees.md`, décisions 012, 013 |

---

## Bloc 2 — intégration de modèles et de services d'IA

### Épreuve E2 — veille et preuve de concept

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C6 | Veille technique et réglementaire | **présent** | 2 notes de veille, chacune avec qualification des sources, confrontation au projet et impact concret : l'AI Act appliqué à un tuteur pédagogique, et les approches de récupération postérieures au RAG vectoriel plat | `docs/veille/` |
| C7 | Comparaison de services d'IA | **vérifié** | Protocole à 6 critères écrit et commité **avant** toute mesure (commit `8cb868f`), puis campagne de 90 appels — 3 modèles × 10 prompts × 3 répétitions, 90 succès. Mesures brutes recalculables, grille de notation en aveugle, décision argumentée | `docs/benchmark_modeles.md`, `docs/benchmark/`, `benchmark/`, décision 016 |
| C8 | Preuve de concept | **absent** | — | **À produire : `docs/poc_multi_agents.md`.** La matière existe (architecture mesurée, benchmark, traces de monitorage) ; le document qui la présente comme un POC — hypothèse, expérimentation, résultat, décision — n'existe pas |

### Épreuve E3 — service IA, application prototype, monitorage du modèle

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C9 | API REST exposant le service IA | **vérifié** | FastAPI dans un processus séparé de l'API données, 6 points de terminaison (5 POST, 1 GET), authentification par clé en comparaison à temps constant, throttling, validation Pydantic, OpenAPI, conteneur dédié | `service_ia/`, `docs/securite_api_service_ia.md`, décision 015 |
| C10 | Intégration du modèle dans l'application | **présent** | 4 agents — Researcher, Pedagogue, Coach, Watcher — et un orchestrateur. Routage par agent, identifiants de modèle externalisés en variables d'environnement après la panne du modèle codé en dur. RAG sur ChromaDB | `apps/agents/`, `apps/agents/tools/model_config.py`, décision 001 |
| C11 | *Groupe « monitorage du modèle IA / CI-CD » du schéma* | **absent** | Aucune preuve marquée `C11` dans le dépôt | **Libellé exact à récupérer dans le référentiel complet.** `apps/monitoring/` trace déjà les appels au modèle — agent, latence, jetons, coût, issue — et pourrait couvrir la part « monitorage ». Le revendiquer sans connaître le libellé serait une surinterprétation |
| C12 | *Groupe « monitorage du modèle IA / CI-CD » du schéma* | **absent** | Aucune preuve marquée `C12` dans le dépôt | **Libellé exact à récupérer.** Même remarque que C11 |
| C13 | Conteneurisation | **vérifié** | Image du service IA construite et vérifiée en intégration continue — contrôle que ni l'historique Git ni le vector store n'y entrent, et que `/app` n'appartient pas à root. `docker-compose.yml` à 4 services, tous en fonctionnement au moment du relevé | `service_ia/Dockerfile`, `.dockerignore`, `docker-compose.yml`, travail `image` de la chaîne |

---

## Bloc 3 — application intégrant un service d'IA

### Épreuve E4 — cadrage, application, intégration continue

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C14 | Analyse du besoin et spécifications fonctionnelles | **partiel** | La matière existe dans les décisions 004 et 005 — cadre d'usage, public adulte exclusif, parties prenantes, options écartées. Manquent les user stories et leurs critères d'acceptation, **accessibilité comprise dans ces critères** | Matière : décisions 004, 005. **À produire : `docs/analyse_besoin.md`** |
| C15 | Cadre technique | **partiel** | La matière existe, dispersée dans 16 entrées de décisions et le cahier des charges. Manque le document qui consolide : schéma d'architecture, environnements, outillage, et l'effet des contraintes matérielles réelles sur les choix | Matière : `docs/decisions/`, `docs/cahier-des-charges.md`. **À produire : `docs/cadre_technique.md`** |
| C16 | Démarche agile | **absent** | Aucune preuve marquée `C16` | **À produire : `docs/demarche_projet.md`.** La démarche réelle est traçable — chantiers, une branche par chantier, marquage des compétences dans les commits, journal de décisions, notes de session — mais elle n'est écrite nulle part comme démarche. Ne pas fabriquer un historique de sprints qui n'a pas eu lieu |
| C17 | Application intégrant des services d'IA | **présent** | Application Django 5.2 fonctionnelle, 13 pages authentifiées répondant en 200, 16 migrations, bascule de SQLite vers `eduai_app` faite. Générateur de cours, quiz, exercices, flashcards, progression | `apps/`, `eduai_project/`, `templates/` |
| C18 | Tests automatisés et intégration continue | **vérifié** | 76 tests `pytest` collectés et au vert, dont des contrôles de non-régression rattachés à des incidents précis. Chaîne GitHub Actions à 3 travaux parallèles — qualité, tests sur PostgreSQL réel avec rejeu du schéma, construction et inspection de l'image | `tests/`, `.github/workflows/integration-continue.yml` |
| C19 | Traçabilité et documentation technique | **vérifié** | 16 entrées de journal de décisions, 4 notes de session, garde-fou Git refusant les commits directs sur `main`, ce document | `docs/decisions/`, `docs/journal/`, `.githooks/pre-commit`, `docs/traceabilite.md` |

### Épreuve E5 — monitorage et résolution d'incidents

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C20 | Monitorage de l'application et du service IA | **vérifié** | Journal JSON Lines hors base, sondes branchées sur le mécanisme de rappels de LangChain, seuils d'alerte avec plancher d'appels et délai de silence, estimation de coût, exposition Prometheus et tableau de bord Grafana provisionné depuis un fichier | `apps/monitoring/`, `docker-compose.yml`, décision 014 |
| C21 | Résolution d'incidents techniques | **vérifié** | 3 dossiers d'incident complets — déclenchement, périmètre, diagnostic, résolution, tests en succès — plus les contrôles de non-régression correspondants dans la suite de tests | `docs/incidents/`, `tests/test_monitorage.py`, `tests/test_benchmark.py` |

---

## Récapitulatif

| État | Compétences | Nombre |
|---|---|---|
| **vérifié** | C1, C2, C3, C4, C5, C7, C9, C13, C18, C19, C20, C21 | 12 |
| **présent** | C6, C10, C17 | 3 |
| **partiel** | C14, C15 | 2 |
| **absent** | C8, C11, C12, C16 | 4 |

**17 compétences sur 21 disposent d'une preuve localisable.** Quatre n'en ont
pas, et elles se répartissent en deux natures très différentes.

### Ce qui est un travail de rédaction

**C8, C14, C15, C16.** La matière existe pour les quatre ; il manque le document
qui la présente. Ce sont des chantiers de documentation, pas de code, et ils
sont planifiables :

- C8 — `docs/poc_multi_agents.md`
- C14 — `docs/analyse_besoin.md`
- C15 — `docs/cadre_technique.md`
- C16 — `docs/demarche_projet.md`

### Ce qui demande une information que je n'ai pas

**C11 et C12.** Le référentiel versionné dans `reference/` ne contient que le
schéma des épreuves : il place C11, C12 et C13 dans un même groupe intitulé
« Monitoring modèle IA / CI-CD », sans donner le libellé de chacune. C13 est
couverte, identifiée comme la conteneurisation. Pour C11 et C12, je ne peux pas
dire ce qui compte comme preuve sans le libellé.

C'est une case vide **de nature différente** des quatre précédentes : elle ne se
comble pas en écrivant, elle se comble en lisant le référentiel complet. Tant
qu'elle n'est pas levée, il est possible que `apps/monitoring/` couvre déjà la
part « monitorage du modèle » — le module trace agent, modèle, latence, jetons,
coût et issue de chaque appel — et que seule la part « CI-CD du service IA »
manque. Mais l'affirmer serait exactement la surinterprétation que ce projet
s'interdit.

**Action : récupérer les libellés de C11 et C12, puis reprendre ces deux
lignes.** C'est la seule tâche de cette liste qui ne dépend pas de moi.

---

## Écarts constatés pendant ce relevé

Trois incohérences relevées en confrontant les documents au dépôt réel. Elles
sont consignées ici plutôt que corrigées en silence.

| Constat | Où | Nature |
|---|---|---|
| Le cahier des charges annonce **13 tables** dans `eduai_data` ; la base en compte **17** | `docs/cahier-des-charges.md`, section « État d'avancement » | Chiffre périmé |
| Le cahier des charges annonce **15 décisions** et **67 tests** ; il y en a **16** et **76** | idem | Chiffres périmés |
| Une docstring justifie le repli local par le traitement de « données d'apprenants **potentiellement mineurs** » | `apps/agents/tools/model_config.py` | **Contredit les décisions 004 et 005**, qui établissent un public exclusivement adulte. Le repli local reste justifié, mais par la souveraineté des données, pas par la protection des mineurs |

Le troisième écart est le seul qui compte pour le jury : il fait dire à un
fichier de code le contraire de ce que deux décisions établissent, sur
précisément le point — l'âge du public — qui détermine le périmètre RGPD retenu.

---

## Ce que ce relevé a corrigé

L'état d'avancement du cahier des charges annonçait le bloc 2 couvert pour
« C9 à C13 ». Le relevé montre que **C11 et C12 n'ont aucune preuve marquée**.
L'écart ne vient pas d'une négligence mais du mécanisme même d'un tableau
d'avancement : il est tenu à la main, il vieillit, et il ne signale pas ce qu'il
ignore.

C'est l'argument d'existence de ce document. Une matrice se construit en
parcourant les 21 lignes une par une, y compris celles dont on est convaincu
d'avance ; c'est ce parcours, et non la conviction, qui fait apparaître les
trous.
