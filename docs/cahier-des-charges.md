# Cahier des charges — EduAI Tutor

## Contexte et contrainte de temps

EduAI Tutor est une plateforme éducative web à architecture multi-agents
(Researcher, Pedagogue, Coach, Watcher) avec RAG.

**Cadre d'usage :** organisme de formation professionnelle au développement.
Le public est constitué d'apprenants **adultes exclusivement** — le service est
réservé aux majeurs (décisions 004 et 005). Ce cadre n'est pas décoratif : il
détermine le périmètre RGPD retenu et l'absence de tout dispositif de
protection des mineurs.

Ce dépôt sert de support d'évaluation pour la certification RNCP 37827
« Développeur en intelligence artificielle » (Simplon, titre 2023).

**Échéances fermes :**
- Rendu des 5 livrables écrits : **4 septembre, 17h**
- Soutenance orale : **14 septembre**

**L'application existe déjà et fonctionne en grande partie.** Le travail
restant consiste à compléter ce qui manque et à mettre l'existant en conformité
avec le référentiel — **pas à reconstruire**.

**Aucun bloc de compétences n'est sacrifiable** : un bloc non acquis n'est pas
rattrapable avant l'année suivante. La priorité est donc la **couverture des 21
compétences**, pas la profondeur sur quelques-unes. Une compétence couverte
modestement vaut mieux qu'une compétence brillante à côté d'une compétence
absente.

---

## État d'avancement

Relevé du 27/08/2026, en fin de journée. **À lire avant de commencer : ne pas
refaire ce qui existe.**

| Chantier | État |
|---|---|
| Extracteurs (C1) | **5 sur 5** — S1 API Stack Overflow, S2 scraping doc Python, S3 fichiers, S4 base de données `eduai_app`, S5 big data Spark sur dump Stack Exchange |
| Base de données (C4) | **En place** — deux bases PostgreSQL, 13 tables, index, contraintes, données de référence chargées, MCD, MLD, dictionnaire, document RGPD |
| Application web (C17) | **Fonctionnelle**, bascule de SQLite vers `eduai_app` faite |
| Journal de décisions (C19) | **10 entrées** dans `docs/decisions/` |
| Requêtes (C2) | **Deux langages couverts** — SQL PostgreSQL (schéma dans `data_pipeline/load/sql/`, collecte S4 dans `data_pipeline/extract/sql/`), Spark SQL pour S5 |
| API données DRF (C5) | **Absente** — `rest_framework` est installé, aucun point de terminaison n'existe |
| API service IA FastAPI (C9) | **Absente** — la dépendance n'est pas encore ajoutée |
| Tests et CI (C18) | **Absents** — les `tests.py` sont des gabarits vides, aucun workflow GitHub Actions |
| Matrice de traçabilité | **Absente** |

Ce tableau vieillit. En cas de doute, vérifier l'état réel plutôt que le croire.

---

## Règles de priorité (dans cet ordre)

1. **Ne pas casser ce qui marche.** L'application fonctionne : toute
   modification doit être incrémentale et vérifiable.
2. **Combler les trous de couverture** avant d'améliorer l'existant.
3. **Rendre les preuves lisibles** pour un jury qui ouvrira le dépôt.
4. Le reste — élégance, optimisation, refactoring — n'est pas au programme
   d'ici le 4 septembre.

### Interdits jusqu'au 4 septembre

- **Aucune restructuration de l'arborescence existante.** Si l'organisation
  actuelle diffère de la cible décrite plus bas, on s'adapte à l'existant. On
  ne déplace pas des dizaines de fichiers à 10 jours du rendu.
- Aucun changement de dépendance majeure, de framework ou de version.
- Aucun refactoring « pour la propreté ».
- Aucune nouvelle fonctionnalité non exigée par le référentiel.

Avant toute modification qui touche plus de trois fichiers : **proposer un plan
et attendre validation.**

---

## Règle d'or

> Avant de refactorer ou de condenser du code existant, vérifier qu'on ne
> supprime pas une preuve d'évaluation.

Ce qui ressemble à de la verbosité inutile est souvent un critère explicite du
référentiel. Ne jamais :

- fusionner les étapes d'un pipeline en une seule fonction « propre » ;
- remplacer un `try/except` explicite par une gestion implicite ;
- supprimer des logs jugés redondants ;
- factoriser les extracteurs en une abstraction générique qui masque le fait
  qu'il y a bien 5 types de sources distincts ;
- retirer une docstring parce que « le code est auto-documenté ».

En cas de doute entre deux implémentations : choisir la plus explicite.

---

## Architecture

Organisation cible, **à ajuster à l'existant plutôt que l'inverse** :

- Pipeline de données (Bloc 1, épreuve E1, C1 à C5) : extraction, transformation,
  chargement, avec un point de lancement unique.
- API REST exposant le **jeu de données** (C5) : **DRF**, dans le projet Django.
- API REST exposant le **service IA** (C9) : **FastAPI**, service séparé.
- Application web Django (Bloc 3, C17).
- Documentation : journal de décisions et matrice de traçabilité.

**Deux séparations à préserver :**

1. L'API données (C5, Bloc 1) et l'API du service IA (C9, Bloc 2) doivent
   rester distinguables. Deux frameworks, deux périmètres : DRF sert le jeu de
   données depuis le projet Django, FastAPI sert le service IA dans un
   processus séparé. La séparation devient lisible sans explication — un jury
   doit voir deux API, pas deux dossiers.
2. ChromaDB n'est pas la base de données évaluée en C4. La BDD de C4 est
   PostgreSQL, avec modèles conceptuel et physique. Le vector store est un
   artefact aval.

**Base de données :** une seule instance PostgreSQL, en conteneur, port hôte
**5433**, deux bases distinctes.

- `eduai_app` — application Django (C17). Schéma géré par les migrations.
- `eduai_data` — jeu de données du pipeline (C4). Schéma géré par les scripts
  de `data_pipeline/load/sql/`.

PostgreSQL n'autorise pas de requête inter-bases sans extension : l'isolation
est structurelle, pas conventionnelle. Le pipeline peut donc purger et
recharger son jeu de données sans qu'aucune erreur de ciblage n'atteigne les
comptes des apprenants (décision 006).

## Stack

- Data/ML : Python, LangChain, ChromaDB, Groq/Ollama, PostgreSQL, PySpark
- App : Django 5.2+, DRF (API données), FastAPI (API service IA),
  Channels/Redis, Tailwind, Monaco Editor
- DevOps : Linux, uv, Docker, Git/GitHub Actions

Gestionnaire de paquets : **uv**.

---

## Les 5 sources de données (C1)

Le référentiel exige un mix d'au moins **cinq types** de sources : service web
(API REST), scraping, fichier de données, base de données, système big data.

Chaque type vit dans son propre fichier, nommé explicitement, pour que le jury
identifie la couverture d'un coup d'œil. Ne pas réduire ce nombre, ne pas
fusionner deux types dans un même fichier.

Le type « big data » est le plus souvent manquant : PySpark sur du Parquet
partitionné répond au critère.

---

## Structure d'un script d'extraction

Critère C1 textuel : *« Le script comprend un point de lancement,
l'initialisation des dépendances et des connexions externes, les règles
logiques de traitement, la gestion des erreurs et des exceptions, la fin du
traitement et la sauvegarde des résultats. »*

Squelette à respecter, sections commentées comprises :

```python
"""
Extraction depuis <TYPE DE SOURCE> — <nom de la source>.

Compétence visée : C1 (épreuve E1)
Contraintes de la source : <licence, robots.txt, rate limit, ToS>
Sortie : <chemin>
"""

# --- 1. Initialisation des dépendances et connexions externes ---
# --- 2. Règles logiques de traitement ---
# --- 3. Gestion des erreurs et exceptions ---
# --- 4. Sauvegarde des résultats ---
# --- 5. Point de lancement ---
if __name__ == "__main__":
    main()
```

Contraintes complémentaires :

- Logging structuré (`logging`, pas `print`) : début, fin, volumétrie, erreurs.
- Gestion d'erreurs explicite et différenciée — jamais `except Exception: pass`.
- Idempotence : relancer le script ne duplique pas les données.
- Scraping : `User-Agent` identifiable, respect du `robots.txt`, rate limiting
  explicite et commenté.

## Docstrings

Toute fonction ou module servant de preuve porte la compétence en en-tête,
suivie d'une ligne « Choix » qui justifie l'implémentation :

```python
def normalize_dates(df):
    """
    Homogénéise les formats de date (ISO 8601) sur l'ensemble des sources.

    Compétence visée : C3 (épreuve E1)
    Choix : ISO 8601 retenu car <justification>.
    """
```

La ligne « Choix » n'est pas décorative : le jury pose des questions ouvertes.

## Requêtes (C2)

Requêtes dans des fichiers dédiés (`*.sql`, `*.spark.sql`), pas en chaînes
inline, avec en commentaire d'en-tête : objectif de collecte, choix de
sélection / filtrage / jointure, optimisations appliquées.

Deux langages exigés : SQL sur PostgreSQL **et** Spark SQL sur le système big
data. Ne pas remplacer Spark SQL par de l'API DataFrame seule.

---

## Git — règles de travail

### Avant toute session

Vérifier la branche courante avec `git branch --show-current` et l'annoncer.
Ne jamais supposer qu'on est sur la bonne branche.

### Branches

- **Jamais de commit direct sur `main`**, sauf correctif urgent explicitement
  demandé.
- Une branche par chantier, nommée `<type>/<bloc>-<sujet>` :
  - `feat/bloc1-pipeline-donnees`
  - `feat/bloc2-api-service-ia`
  - `test/bloc3-pytest-ci`
  - `fix/...` pour les correctifs
  - `docs/...` pour la documentation seule
- Créer la branche **avant** la première modification, jamais après.
- Fusion dans `main` seulement quand le chantier est testé et fonctionnel.
- Pas de Git Flow, pas de branches de release, pas de pull requests : projet
  individuel avec échéance courte, la simplicité prime.

### Commits

Format imposé, en français :

```
<type>(<portée>): <description à l'infinitif ou au présent> [<compétence>]
```

- Types : `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`
- Portée : le module concerné (`extract`, `api`, `rag`, `agents`, `db`…)
- Compétence entre crochets : `[C1]`, `[C4]`, `[C18]`… **obligatoire** dès que
  le commit produit une preuve d'évaluation. Plusieurs compétences possibles :
  `[C1][C3]`.
- Description en minuscule, sans point final, sous 72 caractères.

Exemples valides :

```
feat(extract): ajoute l'extracteur API education.gouv [C1]
fix(db): versionne les migrations exclues à tort du dépôt [C4]
test(api): couvre les points de terminaison du service IA [C18]
docs(decisions): consigne le choix du routage par agent [C10]
```

### Granularité

- **Un commit = une unité de preuve.** Un extracteur, une migration, une série
  de tests, une décision documentée.
- Ne pas mélanger dans un même commit du code fonctionnel et du formatage.
- Ne pas accumuler une journée de travail dans un commit unique : l'historique
  doit montrer la progression.
- Commiter dès qu'une étape fonctionne, sans attendre la perfection.

### Interdits

- Pas de `git push --force` sur `main`.
- Pas de réécriture d'historique (`rebase -i`, `commit --amend` sur du
  poussé) : les dates de commit sont une trace de la démarche réelle.
- Jamais de secret, de clé API, de `.env`, de base de données ni de données
  brutes dans un commit. Vérifier `git status` avant chaque `git add`.
- Pas de `git add .` aveugle : ajouter les fichiers explicitement.

### Après chaque commit significatif

Si le commit acte une décision d'architecture, créer ou compléter l'entrée
correspondante dans `docs/decisions/` **avant** de passer à la suite.

## Journal de décisions

Toute décision d'architecture non triviale donne lieu à une entrée courte dans
`docs/decisions/` : contexte, options, option retenue, raison.

Cinq lignes suffisent. Ce journal alimente les rapports et constitue la seule
préparation à l'oral entre le 4 et le 14 septembre. **Quand une décision est
prise pendant une session de code, l'écrire avant de passer à la suite.**

## Notes quotidiennes

En fin de session, produire une note dans `docs/journal/AAAA-MM-JJ.md` : ce qui
a été fait, les difficultés rencontrées, les choix effectués, les compétences
touchées. Ces notes sont la matière première des 5 rapports — elles évitent de
reconstituer une semaine de travail de mémoire.

---

## Sécurité, RGPD, accessibilité

- API : authentification, permissions, throttling. OWASP API Top 10 implémenté
  et documenté (C5, C9).
- Données personnelles : minimisation, durée de conservation, pseudonymisation,
  effacement (C4). Le public visé est **exclusivement adulte** — plateforme de
  formation professionnelle au développement (décisions 004 et 005). Ce
  cadre écarte le consentement parental de l'article 8 du RGPD et l'information
  en termes compréhensibles par un enfant de l'article 12.1, et rien d'autre :
  c'est un rétrécissement de périmètre, pas un allègement du RGPD.
- Secrets en variables d'environnement uniquement.
- Accessibilité : critère transversal présent dans les grilles de C6, C9, C10,
  C14, C17, C19, C20. Interfaces visant WCAG 2.1 AA / RGAA ; documentation avec
  titres hiérarchisés, alternatives textuelles, tableaux à en-têtes.

## Tests

`pytest`. Couverture minimale : composants métier, gestion des accès, points de
terminaison des deux API. Les tests tournent en CI GitHub Actions à chaque push
(C18). Docstring mentionnant la compétence quand le test sert de preuve.

## Commandes

```bash
uv sync
uv run pytest
docker compose up -d
```

---

## Ce que je ne veux pas

- Du code généré sans que je comprenne pourquoi. Expliquer chaque choix : je
  dois pouvoir le défendre à l'oral le 14 septembre.
- Des abstractions prématurées qui rendent le pipeline illisible.
- Des dépendances ajoutées sans justification.
- Des raccourcis qui « marchent » mais effacent une étape que le référentiel
  demande de démontrer.
- Des chantiers ouverts qui ne seront pas terminés avant le 4 septembre.
