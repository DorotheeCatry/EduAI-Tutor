# Stratégie de tests automatisés

**Date :** 28 août 2026
**Compétence visée :** C12 (épreuve E3) — programmer les tests automatisés d'un
modèle d'IA en définissant les règles de validation des jeux de données, des
étapes de préparation des données, d'entraînement, d'évaluation et de validation
du modèle, pour permettre son intégration en continu
**Compétences concernées :** C18 (E4), C21 (E5)

---

## 1. La stratégie en une page

### Le principe directeur

**Un test de ce projet éprouve un effet, jamais une intention.**

Ce n'est pas une formule : c'est la conséquence directe de ce que le projet a
vécu. Quatre incidents documentés partagent le même motif — un composant qui
rapporte un succès ne correspondant à rien. Un chargeur annonçant 6 836
documents sur une base vide ; une sonde s'annonçant branchée sans rien tracer
pendant vingt-deux heures ; une extraction déclarant « succès, 0 enregistrement »
sur une panne d'API ; un service annoncé `active` qui ne servait rien.

Chaque fois, un test naïf aurait passé. La stratégie en découle : **on ne
vérifie pas qu'une fonction a été appelée, on vérifie ce qu'elle a laissé sur le
disque, en base, ou dans la réponse.**

### Ce qui n'est pas testé, délibérément

| Non testé | Raison |
|---|---|
| La qualité des réponses du modèle | Elle ne s'automatise pas honnêtement — voir § 5 |
| L'interface web page par page | Les 13 pages sont vérifiées manuellement ; les couvrir en Selenium coûterait plus que la confiance gagnée d'ici l'échéance |
| Les appels réels aux fournisseurs | Un test qui appelle Groq échoue quand Groq est indisponible, ce qui n'apprend rien sur le code |
| L'entraînement, l'évaluation et la validation d'un modèle | **Sans objet** — voir § 5 |

### Le seuil de couverture retenu

**Aucun pourcentage de couverture de lignes n'est fixé, et c'est délibéré.**

Un taux de couverture mesure les lignes exécutées, pas les comportements
éprouvés. On l'atteint en écrivant des tests qui traversent le code sans rien
affirmer — et le projet a précisément souffert de vérifications qui passaient
sans vérifier. La couverture retenue est donc exprimée **par obligation**, en
§ 3 : chaque règle métier nommée doit avoir au moins un test qui échoue si elle
est violée. Cette couverture-là se constate ligne par ligne dans le tableau.

Un exemple vécu : un test des séparateurs Unicode a perdu ses caractères
`U+2028` et `U+2029` lors d'un enregistrement. **Il a continué de passer** — sur
une entrée devenue sans séparateur, l'assertion était trivialement vraie. Un
taux de couverture n'aurait rien signalé.

---

## 2. Les outils, et pourquoi ceux-là

| Outil | Rôle | Cohérence avec le contexte |
|---|---|---|
| `pytest` | Exécution, paramétrage, fixtures | Standard de l'écosystème Python ; le paramétrage évite de dupliquer un test pour trois vecteurs d'attaque |
| `pytest-django` | Accès à l'ORM et au client de test | Le projet est un projet Django ; tester l'API données sans son ORM demanderait de réécrire ses requêtes |
| `TestClient` de FastAPI | Points de terminaison du service IA | Le service IA n'est pas un projet Django : il a son propre client de test |
| `ruff` | Analyse statique | Jeu de règles volontairement restreint. Un contrôle qui signale des milliers de lignes n'est pas lu, donc ne contrôle rien |
| GitHub Actions | Intégration continue | Trois travaux parallèles, aucun en `continue-on-error` |
| PostgreSQL 16 en service de CI | Base réelle pour les tests d'intégrité | **Même version majeure que le conteneur du projet.** Éprouver sur SQLite ferait passer des tests que la production refuserait |

**Le point de cohérence le plus important** est le dernier. Les tests
d'intégrité portent sur des contraintes que seul PostgreSQL applique — clés
étrangères, contraintes de vérification, unicité composite. La chaîne
d'intégration **rejoue les scripts de schéma depuis zéro** avant de les
exécuter : un schéma qui ne se crée plus depuis rien n'est pas reproductible, et
le jury doit pouvoir monter le projet à partir du seul dépôt.

---

## 3. Les cas à tester, par partie visée

**63 fonctions de test, 76 cas collectés** — l'écart vient du paramétrage, qui
décline certains tests sur plusieurs vecteurs.

### 3.1 Validation des jeux de données — 9 cas

Partie visée : le jeu de données chargé dans `eduai_data`.
Périmètre : contraintes structurelles et règles métier, éprouvées sur la base
réelle.

| Cas | Règle qu'il défend |
|---|---|
| Les cinq types de sources sont déclarés | C1 exige cinq types distincts : le test échoue si l'un disparaît |
| Chaque source est rattachée à un type connu | Aucune source orpheline |
| La partition des documents est totale | Tout document appartient à exactement une source — ni perte ni double comptage |
| Aucun document ne porte une licence inconnue | Une licence absente de la nomenclature rendrait le filtre de diffusion inopérant |
| `attribution_requise` ne diverge pas de sa licence | Deux champs disent la même chose : ils ne doivent pas se contredire |
| Une licence exigeant l'attribution impose une URL | Sans URL source, l'attribution est impossible à honorer |
| Les comptes par source correspondent aux spécialisations | Le total et le détail concordent |
| Un statut de succès exige des enregistrements | **Non-régression** : le motif « succès, 0 enregistrement » |
| Un retrait n'est jamais antérieur à la dernière observation | Cohérence temporelle du marquage |

### 3.2 Étapes de préparation des données — 11 cas

Partie visée : `data_pipeline/transform/`.
Périmètre : déduplication, normalisation, homogénéisation.

| Cas | Règle qu'il défend |
|---|---|
| Deux documents de même identifiant sont fusionnés | Clé de déduplication primaire |
| Deux contenus identiques sous des identifiants différents sont fusionnés | Empreinte SHA-256 du contenu |
| Une URL partagée ne fait pas un doublon | **Contre-test.** Deux réponses distinctes d'une même page partagent l'URL |
| Un titre partagé ne fait pas un doublon | **Contre-test.** Deux questions peuvent porter le même titre |
| La fusion conserve la traçabilité du doublon | Un doublon retiré laisse une trace de son existence |
| La déduplication est déterministe | Deux exécutions rendent le même résultat |
| L'indentation du code est préservée | Le corpus est technique : une normalisation qui écrase l'indentation détruit le sens |
| Les lignes vides en série sont réduites | Homogénéisation |
| Les mots-clés acceptent les deux formats de dump | Les délimiteurs diffèrent entre exports Stack Exchange |
| Les mots-clés sont normalisés et dédoublonnés | |
| Une licence inconnue ne se rabat pas sur une licence voisine | **Un repli silencieux ferait diffuser un document sous une licence qui ne l'autorise pas** |

Les deux **contre-tests** sont le cœur de cette section : ils vérifient qu'on ne
fusionne **pas** ce qui doit rester distinct. Un jeu de tests qui ne contiendrait
que des cas positifs serait satisfait par une déduplication trop agressive.

### 3.3 Socle d'extraction — 7 cas

Partie visée : `data_pipeline/extract/base_extractor.py`.
Périmètre : distinction succès / échec / vide, protection de la sortie.

Le cas décisif : **une extraction stérile n'écrase pas la sortie précédente.**
Si une source tombe en panne et rend zéro enregistrement, le corpus déjà
collecté doit survivre. Sont testés aussi le cas symétrique — un vide
**légitime**, déclaré par la source, peut vider la sortie — et le statut « zéro
est valide » pour les sources qui le déclarent, comme l'extraction depuis une
base applicative vide.

### 3.4 Accès aux données et sécurité de l'API — 7 cas

Partie visée : `apps/api_data/`.
Périmètre : filtre de diffusion et lecture seule.

Le filtre de licence est éprouvé sur **trois vecteurs distincts** : le
gestionnaire par défaut, l'accès direct par identifiant, et la recherche. Un
filtre correct sur la liste mais absent de l'accès direct laisserait sortir tout
document dont on connaît l'identifiant. Les documents retirés sont testés
séparément, ainsi que le décompte par source — qui ne doit compter que
l'exposable.

Deux cas portent sur le routeur de base de données : il refuse toute écriture,
et n'autorise aucune migration sur le jeu de données.

### 3.5 Service IA — 20 cas

Partie visée : `service_ia/`.
Périmètre : authentification, validation d'entrée, limitation de débit, contrat
des points de terminaison.

Le paramétrage décline « sans clé, tout est refusé » sur l'ensemble des points
de terminaison : une route ajoutée sans protection fait échouer la suite.

### 3.6 Monitorage — 13 cas

Partie visée : `apps/monitoring/`.
Périmètre : journal, seuils d'alerte, visibilité de la sonde.

Deux cas sont des **contrôles de non-régression** rattachés à un incident précis
— la sonde doit être visible depuis un fil d'exécution neuf et depuis une tâche
asynchrone. Le défaut d'origine avait échappé à trois vérifications manuelles,
toutes menées depuis des scripts où le contexte est celui de l'import : **on
avait vérifié que la sonde fonctionne, jamais qu'elle fonctionne là où le
service tourne.**

Un autre cas mérite mention : `verifier()` doit constater ce qui est sur le
disque, non ce que le journal croit avoir écrit. Le test écrit une ligne
directement dans le fichier, sans passer par le journal, et exige qu'elle soit
comptée.

### 3.7 Outillage de mesure — 9 cas

Partie visée : `benchmark/`.
Périmètre : les règles de méthode qui rendent une mesure valide.

Ils n'éprouvent pas les modèles — ceux-ci changent, et une suite qui en dépend
échouerait pour de mauvaises raisons. Ils éprouvent qu'un refus de quota est
reconnu par son **code** et non par le texte du message ; qu'un appel en erreur
n'entre pas dans la latence médiane, faute de quoi le modèle qui échoue le plus
vite afficherait la meilleure latence ; et qu'un appel sans trace de sonde est
compté à part.

---

## 4. Exécution et intégration continue

### La chaîne

Trois travaux en parallèle, sur chaque poussée et chaque branche :

| Travail | Contenu |
|---|---|
| **Qualité** | `ruff check .` |
| **Tests** | PostgreSQL 16 en service, rejeu des scripts de schéma, contrôle que 13 tables au moins existent, puis `pytest -v` |
| **Image** | Construction de l'image du service IA, puis **inspection de son contenu** : ni historique Git, ni vector store, et `/app` n'appartient pas à `root` |

Le contrôle du travail « Image » garde un gain mesuré : le `.dockerignore` a
ramené l'image de 10,1 Go à 5,22 Go. Sans ce contrôle, la taille dériverait sans
que rien ne le signale.

**Aucun travail ne porte `continue-on-error`.** Un contrôle qui ne peut pas
faire échouer la chaîne ne contrôle rien.

### Les tests qui se sautent, et pourquoi ils ne passent pas inaperçus

Les cas exigeant le corpus complet chargé se **sautent** en intégration
continue : reconstituer 6 836 documents demanderait les dumps et plusieurs
heures. Ce saut est explicite — il apparaît dans le récapitulatif de la chaîne,
et il est motivé ici. Un test sauté en silence serait un test absent.

### Rejouer localement les conditions de la chaîne

La chaîne ne définit pas `DJANGO_DEBUG`. Le défaut de ce réglage est `False`
(décision 008), donc les protections de transport — redirection HTTPS, HSTS,
cookies `Secure` — y sont **actives**, comme chez l'hébergeur, alors qu'elles
sont inactives sur un poste de développement où `.env` porte `DJANGO_DEBUG=True`.

Quatre tests passant par le client HTTP de Django ont échoué pour cette seule
raison à leur première exécution en intégration continue, sur un `301` vers
`https://testserver/` (incident 007). Ils sont désormais écrits avec
`secure=True` — ils simulent une requête HTTPS, comme en production, plutôt que
de désactiver la redirection.

Avant d'annoncer qu'une suite passe, la rejouer donc dans les conditions de la
chaîne :

```bash
DJANGO_DEBUG=False uv run pytest
```

C'est la même commande, avec le contexte de l'environnement cible. Un test
vérifié uniquement là où il est commode de le lancer n'a été vérifié qu'à
moitié.

### État à la date de ce document

```
111 passed, 1 warning in 56.05s
```

Suite complète au vert sur PostgreSQL réel, **en local et avec
`DJANGO_DEBUG=False`**, c'est-à-dire dans les deux contextes où elle s'exécute.
Le quatrième critère — « les tests s'exécutent sans problème technique » — est
satisfait.

Relevé du 30/08/2026. Les 35 cas ajoutés depuis la première rédaction de ce
document couvrent l'effacement de compte (C4), les deux plafonds de génération
et le placement du décompte à l'écran (C13, C17).

---

## 5. Entraînement, évaluation et validation du modèle — sans objet

Le libellé de la compétence couvre cinq étapes. Trois d'entre elles n'ont pas
d'objet dans ce projet, et ce document le déclare explicitement plutôt que de
laisser trois sections vides — **une section vide se lit comme un oubli, une
section qui dit pourquoi se lit comme une analyse.**

### La raison

**EduAI Tutor n'entraîne aucun modèle.** Il en intègre : deux modèles servis par
un fournisseur tiers, deux exécutés en local mais téléchargés. Le projet ne
détient aucun jeu d'entraînement, aucun cycle d'apprentissage, aucun poids.

Il n'y a donc :

- **aucune étape d'entraînement** à tester — aucune boucle d'apprentissage
  n'existe dans le dépôt ;
- **aucune évaluation de modèle** au sens statistique — pas de jeu de test
  étiqueté, pas de métrique d'exactitude, de rappel ou de F1, faute d'une vérité
  de terrain ;
- **aucune validation de modèle** avant mise en service — le modèle est celui
  que le fournisseur sert, et sa version peut changer sans que le projet en soit
  informé.

Ce cadre est cohérent avec le bloc de compétences visé — « intégrer des modèles
et des services d'intelligence artificielle » — et avec la contrainte matérielle
réelle : la machine dispose d'un GPU de 4 Go.

### Ce qui en tient lieu, et ses limites

Là où un projet d'entraînement valide un modèle avant de le mettre en service,
celui-ci **compare des modèles servis par des tiers** avant de choisir lequel
router vers quel agent. C'est l'objet du protocole C7 : six critères fixés et
commités avant toute mesure, 90 appels, dispersion mesurée sur trois
répétitions.

Mais il faut dire la limite, parce qu'elle est réelle : **le volet qualité de
cette comparaison n'est pas automatisé, et ne le sera pas.**

Un modèle qui juge d'autres modèles a des biais documentés — préférence pour les
réponses longues, pour son propre style, pour sa famille d'origine. Aucun ne
serait défendable. La qualité est donc notée **à la main**, en aveugle, sur une
grille en cinq axes écrite avant d'avoir vu une réponse, la correspondance entre
étiquettes et modèles vivant dans un fichier séparé.

Cela signifie qu'**une partie de la validation de ce projet n'est pas
automatisable**, donc pas rejouable en intégration continue. C'est une limite
assumée : mieux vaut une notation humaine honnête et non rejouable qu'un score
automatique reproductible et biaisé. Un chiffre reproductible n'est pas un
chiffre juste.

---

## 6. Ce qui manque

| Manque | Effet | Traitable ? |
|---|---|---|
| Aucun test de charge | Le comportement sous concurrence n'est pas éprouvé | Oui, mais sans usage réel à reproduire, le scénario serait inventé |
| Aucun test de bout en bout de l'interface | Les 13 pages sont vérifiées à la main | Coût élevé d'ici l'échéance |
| La chaîne saute les tests exigeant le corpus | Ces cas ne tournent qu'en local | Un jeu de données réduit versionné les rendrait rejouables |
| Aucun test du chaînon PostgreSQL → ChromaDB | Le module d'indexation n'a pas de test | **À combler** : sa règle centrale — le filtre de diffusion réutilisé, non réécrit — mérite un contrôle de non-régression |

Le dernier est le plus important, et il est identifié plutôt que découvert : le
module `apps/rag/indexation_corpus.py` porte la règle selon laquelle un document
non diffusable ne doit pas devenir interrogeable par une autre porte que l'API.
Cette règle appelle un test.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `tests/` | Les 63 fonctions de test |
| `.github/workflows/integration-continue.yml` | La chaîne à trois travaux |
| `incidents/` | Les quatre dossiers dont les non-régressions découlent |
| `benchmark_modeles.md` | Le protocole de comparaison, et la grille de notation manuelle |
| `traceabilite.md` | Index des preuves par compétence |
