# Matrice de traçabilité — RNCP 37827

**Date du relevé :** 28 août 2026
**Mis à jour le :** 4 septembre 2026, chiffres relevés sur la base en marche
et sur le dépôt — six extracteurs, **394 tests**, **45 décisions**,
**18 dossiers d'incident**, **23 réserves**. Les écarts du premier relevé sont repris en fin de
document avec leur suite.
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
| C1 | Extraction de données depuis cinq types de sources | **vérifié** | **6 extracteurs** pour les cinq types exigés : API REST (Stack Overflow), scraping (doc Python), fichiers, base de données, big data — plus un **second scraping** (documentation de six bibliothèques, 91 pages, 1 005 documents). **Les cinq types portent des documents** : S4, longtemps exercée à vide, en rend 27 depuis le 3 septembre. S6 **n'ajoute aucun type** et ne débloque aucun critère : elle enrichit le corpus, et la décision 039 le dit dans ces termes plutôt que de la présenter comme une couverture supplémentaire. Socle commun : point de lancement, gestion d'erreurs différenciée, idempotence, bilan persisté | `data_pipeline/extract/s1_*.py` à `s6_*.py`, `base_extractor.py`, décision 039 |
| C2 | Requêtes dans deux langages | **vérifié** | 20 fichiers `.sql` en fichiers dédiés, jamais en chaînes inline. SQL PostgreSQL pour le schéma et la collecte S4 ; **Spark SQL** pour la conversion, la sélection et la volumétrie du dump big data. En-têtes documentant objectif, filtrage, jointures et optimisations | `data_pipeline/load/sql/`, `data_pipeline/extract/sql/` dont 3 `*.spark.sql` |
| C3 | Agrégation et nettoyage des données | **vérifié** | Trois modules distincts — normalisation des dates (ISO 8601), homogénéisation des formats, déduplication. 7 910 entrants, 40 doublons d'identifiant et 2 doublons de contenu retirés, 7 868 sortants, 0 date perdue, en 1,72 s. Clés de déduplication sur identifiant et empreinte SHA-256 du contenu, jamais sur l'URL ni le titre | `data_pipeline/transform/` (6 modules) |
| C4 | Base de données et modélisation | **vérifié** | Base `eduai_data` en PostgreSQL 16 conteneurisé, **13 tables et 4 vues**, **7 869 documents** en base — 7 868 vivants et un daté `retire_le`, une section disparue de `docs.python.org` entre deux campagnes : la base distingue ce qui n'a jamais existé de ce qui a cessé d'exister, et c'est ce qui explique l'unité d'écart avec les 7 868 sortants de C3. Les six sources comprises, 1 211 mots-clés, 20 545 rattachements, 14 992 collectes, 15 campagnes d'extraction, 0 rejet. **Les 27 documents de S4 ne portent aucun mot-clé** : les étiquettes viennent des sources qui en publient, et une production d'apprenant n'en a pas. MCD, MLD, dictionnaire de données, document de conformité RGPD. Isolation structurelle d'avec `eduai_app` (décision 006) | `data_pipeline/load/`, `docs/mcd_eduai_data.md`, `docs/mld_eduai_data.md`, `docs/dictionnaire_donnees_eduai_data.md`, `docs/rgpd_eduai_data.md`, décisions 006, 007, 009, **045** — l'effacement vide la source qui exploite les productions des apprenants, et le document dit laquelle des deux exigences cède. **Les supports de cours sont sous licence MIT** — « Python Cheatsheet » de wilfredinni, vérifié le 04/09/2026 — et non « propriétaire » comme le manifeste le déclarait ; l'obligation d'attribution est portée par la licence du dépôt. **L'attribution voyage jusque dans la fiche de l'apprenant** : url, licence et obligation d'attribution sont conservées par ajout — c'est la condition juridique qui autorise l'usage de ce corpus (décision 041) |
| C5 | API REST exposant le jeu de données | **vérifié** | Django REST Framework, 3 jeux de vues et une vue de statistiques, lecture seule garantie par un routeur de base qui lève sur écriture. **7 760 documents exposés sur 7 869** — les 81 aides-mémoire de DataCamp, le document sans licence déclarée et les **27 productions d'apprenants** sont retenus par `redistribution_autorisee`, faux pour ces trois licences : le corpus des apprenants alimente le jeu de données sans jamais être republié — le filtre de licence est dans le queryset de base, pas dans chaque vue. Authentification, permissions, throttling, pagination, OpenAPI | `apps/api_data/`, `docs/securite_api_donnees.md`, décisions 012, 013 |

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
| C10 | Intégration du modèle dans l'application | **présent** | 4 agents — Researcher, Pedagogue, Coach, Watcher — et un orchestrateur. Routage par agent, identifiants de modèle externalisés en variables d'environnement après la panne du modèle codé en dur. RAG sur ChromaDB. **Le rôle du modèle a été déplacé** : il ne produit plus le contenu d'un cours — qui entrerait en concurrence avec une documentation officielle toujours meilleure, désormais dans le corpus — mais **la version personnelle d'un contenu existant**. L'apprenant part d'un cours de référence et l'enrichit là où il bute (décisions 040, 041) | `apps/agents/`, `apps/courses/services.py`, `apps/agents/tools/model_config.py`, décisions 001, 040, 041 |
| C11 | Monitorer un modèle d'IA à partir des métriques courantes et spécifiques au projet, en intégrant les outils de collecte, d'alerte et de restitution | **vérifié** | **Aucun indicateur affiché n'est estimé** : le tableau de bord calculait un taux de réussite sur l'expérience gagnée (`60 + xp // 50`) et simulait le temps d'étude ; tout est mesuré ou annoncé comme non mesuré (incident 011). Le seuil de latence est réglé **par environnement** et dérivé de la dispersion mesurée, non du confort (décision 024). Les trois volets sont outillés — collecte, alerte, restitution — **et chaque métrique est expliquée** : ce qu'elle mesure, ce qu'elle ne mesure pas, comment la lire. 14 métriques, dont 5 qui observent l'appareil d'observation lui-même. Les seuils sont justifiés par les valeurs mesurées. Les déclencheurs de réentraînement de l'activité A5 sont déclarés sans objet **avec leur raison**, et ce qui en tient lieu est nommé | `docs/monitorage_metriques.md`, `apps/monitoring/`, décision 014 |
| C12 | Programmer les tests automatisés d'un modèle d'IA en définissant les règles de validation des jeux de données, des étapes de préparation, d'entraînement, d'évaluation et de validation | **présent** | Stratégie documentée : 76 cas listés par partie visée et par périmètre, avec la règle que chacun défend. Principe directeur — un test éprouve un effet, jamais une intention. Couverture exprimée par obligation plutôt qu'en pourcentage de lignes, avec la raison. Volets entraînement, évaluation et validation de modèle déclarés sans objet **avec leur raison**, et ce qui en tient lieu — la comparaison de modèles C7 — exposé avec sa limite | `docs/strategie_tests.md`, `tests/`, `.github/workflows/` |
| C13 | Conteneurisation et déploiement | **vérifié** | **Trois images** construites et **inspectées** en intégration continue — ni historique Git, ni vector store, point de montage du corpus présent et hors de `root`, taille relevée à chaque exécution. Poids ramené de 10,1 Go à **1,3 Go** (application web) et **1,26 Go** (service IA) par trois retraits mesurés. **Images publiées au registre par la chaîne**, étiquetées par empreinte de commit. `docker-compose.yml` à 4 services avec contrôles de santé. **Chaîne documentée de bout en bout** : installation, configuration, test, construction, publication, déploiement chez l'hébergeur, et **sept contrôles de vérification exécutables** sur l'URL publique | `docs/chaine_livraison.md`, `docker/verifier-deploiement.sh`, `Dockerfile`, `service_ia/Dockerfile`, `docker/ollama/Dockerfile`, `.dockerignore` |

---

## Bloc 3 — application intégrant un service d'IA

### Épreuve E4 — cadrage, application, intégration continue

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C14 | Analyse du besoin et spécifications fonctionnelles | **présent** | Contexte, trois parties prenantes, besoin exprimé et **origine de l'analyse assumée comme de première main** plutôt que déguisée en étude d'usage. Huit user stories avec critères d'acceptation, **l'accessibilité figurant dans ces critères** et non en section séparée. Périmètre livré et périmètre écarté, avec le motif de chaque exclusion | `docs/analyse_besoin.md`, décisions 004, 005, 017 |
| C15 | Cadre technique | **présent** | Architecture en cinq ensembles, **décrite textuellement avant d'être schématisée** — l'équivalent textuel est la description, non une légende appauvrie. Pile et versions, environnements conteneurisés, intégration continue, secrets, contrôle de version. Contraintes matérielles réelles suivies chacune de la décision qu'elle a produite | `docs/cadre_technique.md`, `docs/decisions/` |
| C16 | Démarche de gestion de projet | **présent** | Démarche **réellement suivie**, mesurée dans l'historique : 474 commits en deux phases séparées de treize mois, découpage par chantier plutôt que par sprint, 20 branches, 118 des 120 commits récents portant leur compétence, 45 décisions, 6 notes de session. Ce qui manque est énoncé — ni rétrospective formalisée, ni estimation, ni revue par un pair — avec le coût réel de chaque manque | `docs/demarche_projet.md` |
| C17 | Application intégrant des services d'IA | **vérifié** | Application Django 5.2 fonctionnelle, déployée et vérifiée sur URL publique. **Référentiel de compétences importable** — aucun libellé en dur, un test le garde — avec rattachement des exercices et des quiz par choix explicite. **Règle de progression énonçable en trois phrases**, dont un niveau déclaré non mesuré plutôt qu'atteint par accumulation. **Page d'accueil sur données mesurées, avec un état vide par bloc**. Interface bilingue français/anglais, langue suivant le compte. **Toutes les données factices retirées** : sept foyers, dont un taux de réussite calculé sur l'expérience gagnée (incident 011). **Quiz multijoueur réparé** : horodatage par le serveur, erreurs enregistrées, rattachement au référentiel, fin de partie prononcée par le serveur et non par chaque client (décisions 031, 032). **Feuille de style compilée** et CDN abandonné — 407 Kio de JavaScript en moins par page, équivalence vérifiée élément par élément sur six pages (décision 034). **Pages tenant dans l'écran** : l'ossature est figée, les cartes défilent, et 1 500 pixels de progression jusque-là coupés sont redevenus atteignables (décision 038). **Tuteur incarné** : personnage animé par planche de sprites, salutation assemblée à partir de données réelles et jamais engendrée, `prefers-reduced-motion` respecté deux fois plutôt qu'une (décisions 035 à 037). **Trois couches de cours rattachées à la compétence et non au cours** : référence à double statut — publié par un formateur, ou provisoire engendré en attendant, jamais confondus à l'écran —, fiche par apprenant, ajouts portant chacun la question qui les a produits. La fiche ne référence aucun cours : c'est ce qui fait survivre le travail de l'apprenant au remplacement du cours, et un test le défend | `apps/accueil/`, `apps/referentiel/`, décisions 026 à 028, `tests/test_accueil.py`, `tests/test_progression.py` |
| C18 | Tests automatisés et intégration continue | **vérifié** | **394 tests** `pytest` collectés et au vert, dont des contrôles de non-régression rattachés à des incidents précis. Chaîne GitHub Actions à **5 travaux** — qualité, tests sur PostgreSQL réel avec rejeu du schéma, construction et inspection des deux images applicatives en matrice, puis publication conditionnée à leur succès | `tests/`, `.github/workflows/integration-continue.yml` |
| C19 | Traçabilité et documentation technique | **vérifié** | **45 entrées** de journal de décisions, notes de session, garde-fou Git refusant les commits sur `main`, matrice de traçabilité. **Documentation de la chaîne couvrant toutes les étapes, toutes les tâches et tous les déclencheurs** — trois déclencheurs d'intégration continue, cinq déclencheurs locaux, et le déclencheur de livraison isolé en tableau : événement, branche, condition, effet. **L'étape de livraison est intégrée à la chaîne et s'exécute une fois le packaging validé** (`needs: [qualite, tests, image]`), ce que le critère demande explicitement. Les étapes qui restent manuelles — chargement du jeu de données, transfert et mise à jour du corpus — sont documentées comme telles, non passées sous silence | `.github/workflows/integration-continue.yml`, `docs/chaine_livraison.md`, `docs/decisions/`, `docs/journal/`, `.githooks/pre-commit` |

### Épreuve E5 — monitorage et résolution d'incidents

| # | Compétence | État | Preuve | Emplacement |
|---|---|---|---|---|
| C20 | Monitorage de l'application et du service IA | **vérifié** | Journal JSON Lines hors base, sondes branchées sur le mécanisme de rappels de LangChain, seuils d'alerte avec plancher d'appels et délai de silence, estimation de coût, exposition Prometheus et tableau de bord Grafana provisionné depuis un fichier | `apps/monitoring/`, `docker-compose.yml`, décision 014 |
| C21 | Résolution d'incidents techniques | **vérifié** | **18 dossiers d'incident** complets — déclenchement, périmètre, diagnostic, résolution, tests en succès — chacun avec son contrôle de non-régression. **Et un document qui en dégage trois familles** (`motifs_incidents.md`) : vérifié dans un contexte employé dans un autre ; l'instrument ne mesure pas ce qu'il prétend ; écrit, joignable, jamais appelé. Chaque famille porte les questions à poser pour éviter la prochaine occurrence : **sept à ce jour**, dont trois ajoutées début septembre — *ce contrôle mesure-t-il l'existence ou la substance ?*, *ce nombre compte-t-il la même chose que celui auquel je le compare ?*, *un refus a-t-il été vérifié aussi soigneusement qu'une autorisation ?* **23 réserves** ouvertes ou levées, datées | `docs/incidents/`, `docs/motifs_incidents.md`, `docs/reserves.md` |

---

## Récapitulatif

| État | Compétences | Nombre |
|---|---|---|
| **vérifié** | C1, C2, C3, C4, C5, C7, C9, C11, C13, C17, C18, C19, C20, C21 | 14 |
| **présent** | C6, C8, C10, C12, C14, C15, C16 | 7 |

*Une ligne « vérifié » figurait deux fois dans le relevé du 28 août, l'une
listant les compétences et l'autre les comptant. Corrigé.*

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
| `attempts_count` compte les soumissions, pas les tentatives avant réussite | `reserves.md` § 13 |
| `current_streak` est lu pour accorder un bonus, et n'est jamais écrit — il vaut zéro pour tout le monde | `reserves.md` § 19 |
| Le périmètre de S6 épingle PyTorch 2.13 dans un corpus sans notion de version | `reserves.md` § 20 |
| `prose` et `prose-invert` employées sans le greffon qui les produit : elles ne stylent rien | `reserves.md` § 18 |
| Seize traductions devinées par `makemessages`, inertes mais fausses | `reserves.md` § 17 |
| Une session d'apprentissage reste ouverte après chaque génération de quiz multijoueur | `reserves.md` § 16 |

**Les trois documents que ce tableau annonçait comme à produire — `analyse_besoin.md`,
`cadre_technique.md`, `demarche_projet.md` — sont écrits.** Le tableau qui les
listait est retiré plutôt que laissé à contredire les lignes C14, C15 et C16
ci-dessus : un document de traçabilité qui se contredit ne trace plus rien.

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
| ~~Le cahier des charges annonce **13 tables** sans mentionner les vues~~ — **corrigé le 04/09** : il annonce 13 tables et 4 vues | `docs/cahier-des-charges.md` | Écart levé |
| ~~Le cahier des charges annonçait **15 décisions** et **67 tests**~~ — **corrigé le 04/09** : 45 décisions, 394 tests, et son relevé porte désormais sa date | idem | Écart levé, la leçon reste : un tableau tenu à la main vieillit d'autant plus vite que le projet avance |
| ~~Une docstring justifie le repli local par le traitement de « données d'apprenants **potentiellement mineurs** »~~ — **corrigé** : la docstring dit désormais que le public est exclusivement adulte et que le repli tient à la souveraineté des données | `apps/agents/tools/model_config.py` | Écart levé |

Le troisième écart était le seul qui comptait pour le jury : il faisait dire à
un fichier de code le contraire de ce que deux décisions établissent, sur
précisément le point — l'âge du public — qui détermine le périmètre RGPD retenu.
**Il a été corrigé depuis**, et la ligne est conservée barrée : un écart relevé
puis levé se lit, un écart effacé ne se lit pas.

Le cahier des charges annonce par ailleurs la matrice de traçabilité comme
**absente**. Elle existe depuis le 28 août. C'est le même mécanisme que les
chiffres périmés au-dessus — et il vaut d'être noté ici, puisque c'est
précisément ce document qui est censé y remédier.

---

## Ce que la mise à jour du 2 septembre a changé

Six lignes ont bougé, et deux méritent d'être signalées pour ce qu'elles disent
du dispositif plutôt que du projet.

**C11 et C17 passent de « présent » à « vérifié ».** Non par ajout de preuve
mais par exécution : les indicateurs de C11 ont été confrontés à la base et
plusieurs se sont révélés inventés (incident 011) ; l'application de C17 a été
vérifiée sur son URL publique, page par page, avec un compte réel.

**Aucune ligne ne passe de « vérifié » à « présent ».** C'est ce qu'il faut
surveiller dans un document comme celui-ci : une preuve rejouée le 28 août ne
l'est plus le 2 septembre, et rien ne le signale. Le statut « vérifié » porte
donc une date implicite — celle du relevé — et non une garantie permanente.

**Les chiffres de ce document vieilliront comme ceux du cahier des charges.**
Ils sont datés pour cette raison. La parade n'est pas de les tenir à jour en
permanence, ce que personne ne fait, mais de dater le relevé et de refaire le
parcours avant chaque rendu.

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
