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
| C8 | Preuve de concept | **présent** | Hypothèse formulée telle qu'elle l'était avant la mise en œuvre, périmètre construit et périmètre écarté, résultats repris des mesures existantes, limites constatées, décision. Deux limites énoncées franchement : le journal de production ne contient que 4 appels et 2 recherches, aucun d'usage réel ; et aucune mesure ne compare l'architecture multi-agents à un appel unique — manque chiffré à une heure de machine, proposé comme suite | `docs/poc_multi_agents.md` |

### Épreuve E3 — service IA, application prototype, monitorage du modèle

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C9 | API REST exposant le service IA | **vérifié** | FastAPI dans un processus séparé de l'API données, 6 points de terminaison (5 POST, 1 GET), authentification par clé en comparaison à temps constant, throttling, validation Pydantic, OpenAPI, conteneur dédié | `service_ia/`, `docs/securite_api_service_ia.md`, décision 015 |
| C10 | Intégration du modèle dans l'application | **présent** | 4 agents — Researcher, Pedagogue, Coach, Watcher — et un orchestrateur. Routage par agent, identifiants de modèle externalisés en variables d'environnement après la panne du modèle codé en dur. RAG sur ChromaDB | `apps/agents/`, `apps/agents/tools/model_config.py`, décision 001 |
| C11 | Monitorer un modèle d'IA à partir des métriques courantes et spécifiques au projet, en intégrant les outils de collecte, d'alerte et de restitution | **présent** | Les trois volets sont outillés — collecte, alerte, restitution — **et chaque métrique est expliquée** : ce qu'elle mesure, ce qu'elle ne mesure pas, comment la lire. 14 métriques, dont 5 qui observent l'appareil d'observation lui-même. Les seuils sont justifiés par les valeurs mesurées. Les déclencheurs de réentraînement de l'activité A5 sont déclarés sans objet **avec leur raison**, et ce qui en tient lieu est nommé | `docs/monitorage_metriques.md`, `apps/monitoring/`, décision 014 |
| C12 | Programmer les tests automatisés d'un modèle d'IA en définissant les règles de validation des jeux de données, des étapes de préparation, d'entraînement, d'évaluation et de validation | **présent** | Stratégie documentée : 76 cas listés par partie visée et par périmètre, avec la règle que chacun défend. Principe directeur — un test éprouve un effet, jamais une intention. Couverture exprimée par obligation plutôt qu'en pourcentage de lignes, avec la raison. Volets entraînement, évaluation et validation de modèle déclarés sans objet **avec leur raison**, et ce qui en tient lieu — la comparaison de modèles C7 — exposé avec sa limite | `docs/strategie_tests.md`, `tests/`, `.github/workflows/` |
| C13 | Conteneurisation et déploiement | **vérifié** | Image construite et **inspectée** en intégration continue — ni historique Git, ni vector store, `/app` hors de `root` ; `.dockerignore` ramenant l'image de 10,1 à 5,22 Go. `docker-compose.yml` à 4 services avec contrôles de santé et dépendances conditionnelles. **Chaîne documentée de bout en bout** : installation, configuration, test, construction, et les dix étapes du `Dockerfile` avec leur motif | `docs/chaine_livraison.md`, `service_ia/Dockerfile`, `.dockerignore`, `docker-compose.yml` |

---

## Bloc 3 — application intégrant un service d'IA

### Épreuve E4 — cadrage, application, intégration continue

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C14 | Analyse du besoin et spécifications fonctionnelles | **présent** | Contexte, trois parties prenantes, besoin exprimé et **origine de l'analyse assumée comme de première main** plutôt que déguisée en étude d'usage. Huit user stories avec critères d'acceptation, **l'accessibilité figurant dans ces critères** et non en section séparée. Périmètre livré et périmètre écarté, avec le motif de chaque exclusion | `docs/analyse_besoin.md`, décisions 004, 005, 017 |
| C15 | Cadre technique | **présent** | Architecture en cinq ensembles, **décrite textuellement avant d'être schématisée** — l'équivalent textuel est la description, non une légende appauvrie. Pile et versions, environnements conteneurisés, intégration continue, secrets, contrôle de version. Contraintes matérielles réelles suivies chacune de la décision qu'elle a produite | `docs/cadre_technique.md`, `docs/decisions/` |
| C16 | Démarche de gestion de projet | **présent** | Démarche **réellement suivie**, mesurée dans l'historique : 474 commits en deux phases séparées de treize mois, découpage par chantier plutôt que par sprint, 20 branches, 118 des 120 commits récents portant leur compétence, 17 décisions, 4 notes de session. Ce qui manque est énoncé — ni rétrospective formalisée, ni estimation, ni revue par un pair — avec le coût réel de chaque manque | `docs/demarche_projet.md` |
| C17 | Application intégrant des services d'IA | **présent** | Application Django 5.2 fonctionnelle, 13 pages authentifiées répondant en 200, 16 migrations, bascule de SQLite vers `eduai_app` faite. Générateur de cours, quiz, exercices, flashcards, progression | `apps/`, `eduai_project/`, `templates/` |
| C18 | Tests automatisés et intégration continue | **vérifié** | 76 tests `pytest` collectés et au vert, dont des contrôles de non-régression rattachés à des incidents précis. Chaîne GitHub Actions à 3 travaux parallèles — qualité, tests sur PostgreSQL réel avec rejeu du schéma, construction et inspection de l'image | `tests/`, `.github/workflows/integration-continue.yml` |
| C19 | Traçabilité et documentation technique | **vérifié** | 17 entrées de journal de décisions, 4 notes de session, garde-fou Git refusant les commits sur `main`, matrice de traçabilité. **Documentation de la chaîne couvrant toutes les étapes, toutes les tâches et tous les déclencheurs** — trois déclencheurs d'intégration continue et cinq déclencheurs locaux, énumérés avec ce qu'ils lancent et pourquoi les déclencheurs absents le sont | `docs/chaine_livraison.md`, `docs/decisions/`, `docs/journal/`, `.githooks/pre-commit`, `docs/traceabilite.md` |

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
| **vérifié** | 12 compétences | 12 |
| **présent** | C6, C8, C10, C11, C12, C14, C15, C16, C17 | 9 |

**Les 21 compétences disposent d'une preuve localisable.** Aucune ligne n'est en
« partiel » ni en « absent ».

Cela ne veut pas dire que tout est excellent : « présent » signifie que la preuve
existe et est localisable, non qu'elle a été rejouée aujourd'hui. Les réserves
propres à chaque preuve sont dans son document — et plusieurs sont sérieuses,
notamment l'absence de traces d'usage réel, l'accessibilité définie mais non
auditée, et les deux écarts RGPD ouverts.

### Ce qui reste — non plus des preuves, mais des réserves

Les six documents manquants sont écrits. Ce qui subsiste n'est plus une absence
de preuve mais une série de réserves à traiter, listées ici pour qu'elles ne se
perdent pas :

| Réserve | Où elle est consignée |
|---|---|
| ~~Route d'effacement de compte non implémentée~~ — **levée le 28/08** : route `users:supprimer_compte`, effacement vérifié par relecture de la base et du disque, 9 tests | `rgpd_eduai_data.md` § 8 |
| ~~Champ `ip_address` à supprimer~~ — **levée le 28/08** : champ supprimé, colonne absente de la base | idem |
| Cascade sur `GameRoom.host` : effacer un compte emporte les réponses d'autres participants | `rgpd_eduai_data.md`, « écart restant » |
| Accessibilité définie dans les critères mais non auditée — 7 gabarits sur 28 portent des attributs, 4 déclarent la langue | `analyse_besoin.md` § 6 |
| Aucune trace d'usage réel : 4 appels au modèle, tous de vérification | `poc_multi_agents.md` § 3.6 |
| Tarifs du fournisseur non confrontés à la source | `benchmark_modeles.md` § 6 |
| Notation en aveugle de la qualité non faite | `benchmark/notation-aveugle.md` |
| Corpus documentaire non indexé dans le vector store | `poc_multi_agents.md` § 2.2 |
| Comparaison multi-agents / agent unique non menée — chiffrée à une heure | `poc_multi_agents.md` § 5 bis |
| Aucune analyse de sécurité des dépendances dans la chaîne | `chaine_livraison.md` § 7 — seule lacune de la liste qui ne soit pas un arbitrage assumé |

| Compétence | Document à produire | Ce qui manque exactement |
|---|---|---|
| C14 | `docs/analyse_besoin.md` | User stories et critères d'acceptation, **accessibilité comprise dans ces critères** |
| C15 | `docs/cadre_technique.md` | La consolidation : architecture, environnements, outillage, contraintes matérielles |
| C16 | `docs/demarche_projet.md` | La démarche réellement suivie, et ce qui manque par rapport à une démarche agile complète |

Deux précisions que les libellés imposent et qu'il serait facile de manquer.

**C11 est un critère d'explication.** « Les métriques sont expliquées sans erreur
d'interprétation » ne se démontre pas en montrant un tableau de bord : il se
démontre en disant ce que chaque métrique mesure, ce qu'elle ne mesure pas, et
ce qu'on en conclut. L'activité A5 mentionne aussi « les éventuels déclencheurs
pour le réentraînement » — à traiter, y compris pour dire qu'ils sont sans objet
ici et pourquoi.

**C12 comporte des volets sans objet dans ce projet.** Le libellé couvre
l'entraînement, l'évaluation et la validation d'un modèle. **EduAI Tutor
n'entraîne aucun modèle** : il intègre des modèles servis par un tiers ou en
local. Ces volets doivent être déclarés sans objet **explicitement**, avec la
raison — une section vide se lit comme un oubli, une section qui dit « sans
objet, car le projet n'entraîne pas de modèle » se lit comme une analyse.

### Ce que la première version de ce document ne pouvait pas dire

Au premier relevé, C11 et C12 étaient portées « absentes ». Le référentiel
versionné dans `reference/` ne contient que le schéma des épreuves : il place
C11, C12 et C13 dans un groupe intitulé « Monitoring modèle IA / CI-CD » sans
donner le libellé de chacune, et il était impossible de dire ce qui comptait
comme preuve.

Les libellés relevés dans le référentiel complet — pages 12 et 14 — ont fait
passer les deux lignes d'« absent » à « partiel » **sans qu'une ligne de code
ait été écrite**. La preuve était là ; c'est le critère qui manquait pour la
reconnaître.

Cela vaut d'être noté, parce que l'erreur inverse est plus courante : conclure
qu'une compétence est couverte parce qu'on a construit quelque chose qui lui
ressemble. Ici, la vérification a joué dans les deux sens — elle a révélé des
trous au premier passage, et refermé deux fausses alertes au second.

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
