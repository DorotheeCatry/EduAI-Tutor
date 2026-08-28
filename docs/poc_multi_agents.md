# Preuve de concept — architecture multi-agents avec RAG

**Date :** 28 août 2026
**Compétence visée :** C8 (épreuve E2) — preuve de concept
**Compétences concernées :** C6 et C7 (E2), C10 (E3), C20 (E5)

---

## Avertissement de méthode

Ce document rapporte une expérimentation. Il n'a pas pour objet de convaincre
qu'elle a réussi, mais de dire **ce qui a été éprouvé, ce qui ne l'a pas été, et
ce qu'on peut en conclure sans forcer**.

Tous les chiffres qui suivent proviennent de mesures déjà consignées ailleurs
dans le dépôt — benchmark C7, journal de monitorage, bilans du pipeline. Aucun
n'a été produit pour ce document, et aucun n'est estimé. Là où une donnée
manque, elle est écrite comme manquante.

Ce projet tient quatre dossiers d'incident dont le motif commun est un rapport
qui ne correspond pas à son effet. Un POC qui surinterpréterait ses résultats
serait le cinquième.

---

## 1. L'hypothèse de départ

Elle est reproduite ici **telle qu'elle était formulée avant la mise en œuvre**,
non telle que les résultats permettraient de la reformuler aujourd'hui.

> Un tuteur pédagogique rend quatre services de nature différente : chercher de
> l'information, l'expliquer, corriger une production, et repérer une méprise.
> Un appel unique à un modèle généraliste doit les traiter tous avec le même
> prompt, la même température et le même modèle. L'hypothèse est qu'en séparant
> ces quatre rôles en agents distincts, chacun avec son prompt, son modèle et
> son accès au corpus, on obtient à la fois **une meilleure qualité par tâche**
> et **un meilleur rapport coût-latence**, parce qu'on cesse de payer un modèle
> de raisonnement pour classer une erreur en un mot.

Cette hypothèse comporte deux volets, et il faut dire d'emblée qu'ils n'ont pas
été éprouvés au même degré :

| Volet | Éprouvé ? |
|---|---|
| Meilleur rapport coût-latence par spécialisation | **Oui**, mesuré — § 3.1 |
| Meilleure qualité par tâche | **Non**, la mesure attend une notation à la main — § 5 |

Une hypothèse à moitié éprouvée reste à moitié éprouvée. C'est la conclusion la
plus importante de ce document, et elle est énoncée avant les résultats plutôt
qu'après.

---

## 2. Le périmètre expérimenté

### 2.1 Ce qui a été construit

| Élément | État |
|---|---|
| **Quatre agents** — Researcher, Pedagogue, Coach, Watcher | Construits, avec un orchestrateur |
| **Routage par modèle** | Construit : identifiants externalisés en variables d'environnement, un modèle par agent |
| **RAG sur ChromaDB** | Construit, alimenté par le corpus de cours |
| **Repli local** | Construit, servi par Ollama |
| **Corpus documentaire** | 6 836 documents en PostgreSQL, issus de cinq types de sources |
| **Monitorage** | Construit : collecte, alerte, restitution |

### 2.2 Ce qui a été laissé de côté, et pourquoi

| Écarté | Raison |
|---|---|
| **L'interaction adaptative sur les cours** — un cours qui se reconfigure selon les réponses de l'apprenant | Arbitrage de délai. C'était la fonction la plus ambitieuse et la plus incertaine ; la livrer à moitié aurait coûté la couverture d'autres compétences |
| **L'extension du corpus RAG aux onze modules** | Arbitrage de délai. **11 modules sont présents** dans `data/contents/courses/`, **3 index sont construits** — Python, science des données, ressources |
| **L'indexation du corpus documentaire dans le vector store** | Écrite (`apps/rag/indexation_corpus.py`), **pas encore exécutée**. Les 6 836 documents de PostgreSQL ne sont pas interrogeables par les agents à la date de ce document |
| **L'entraînement d'un modèle** | Hors périmètre par construction : le projet **intègre** des modèles, il n'en entraîne aucun |
| **Un juge automatique de qualité** | Écarté délibérément, voir § 5 |

Le troisième point mérite d'être souligné, parce qu'il découpe le système en
deux moitiés qui ne se parlent pas encore : **le pipeline de données alimente
PostgreSQL, le RAG interroge ChromaDB, et rien ne portait les documents de l'un
à l'autre.** Le chaînon est écrit ; il n'a pas tourné.

---

## 3. Les résultats mesurés

### 3.1 Le volet coût-latence — éprouvé

Campagne du 28 août, 90 appels : trois modèles × dix prompts représentatifs des
quatre agents × trois répétitions. 90 succès, aucune erreur. Protocole complet
dans `benchmark_modeles.md`, écrit et commité avant toute mesure.

| Modèle | Latence médiane | Jetons de sortie (moy.) | Coût / 1000 requêtes |
|---|---|---|---|
| `openai/gpt-oss-20b` | **0,75 s** | 416 | 0,140 $ ⚠ |
| `openai/gpt-oss-120b` | 0,98 s | **356** | 0,236 $ ⚠ |
| `qwen/qwen3.6-27b` | 1,89 s | 768 | 0,480 $ ⚠ |

⚠ Les tarifs n'ont pas été confrontés à la grille du fournisseur. Ces montants
valent par leurs **rapports**, non par leurs valeurs absolues.

**Ce que cela établit.** La spécialisation par agent est justifiée sur les
critères mesurables : l'écart de latence médiane entre le modèle rapide et le
modèle de qualité est de 0,23 seconde, et l'écart de coût d'un facteur 1,7. Pour
l'agent Watcher, dont la tâche est de rendre un mot, payer le second n'a pas de
contrepartie. Pour l'agent Pedagogue, qui rédige un cours, 0,23 seconde ne se
perçoit pas.

**Ce que cela n'établit pas.** Que l'architecture multi-agents soit meilleure
qu'un appel unique. Le benchmark compare des **modèles entre eux sur des tâches
d'agent**, il ne compare pas une architecture à une autre. Aucune mesure
comparant « quatre agents spécialisés » à « un agent généraliste » n'a été
faite. L'hypothèse de départ portait pourtant là-dessus.

### 3.2 Un résultat non anticipé

`gpt-oss-120b` consomme **moins** de jetons de sortie que `gpt-oss-20b` : 356
contre 416. Le modèle le plus gros est le plus concis. Son coût pour mille
requêtes reste supérieur — son tarif au jeton l'est — mais l'écart est bien
moindre que le rapport des tailles ne le laissait attendre.

C'est le type de fait qu'une décision prise sans mesure ne peut pas connaître,
et c'est l'argument principal en faveur de l'exercice.

### 3.3 Un modèle écarté sur ses propres chiffres

`qwen/qwen3.6-27b` ouvre un bloc de raisonnement visible sur 30 appels sur 30 et
ne le referme que 5 fois dans le budget commun de 800 jetons : 25 réponses sur
30 sont du raisonnement tronqué, sans réponse.

Restait à savoir si l'on mesurait le modèle ou la contrainte. Une mesure
complémentaire à 4 000 jetons, tenue hors des tableaux principaux parce que ses
paramètres diffèrent, tranche : le modèle répond alors correctement aux dix
prompts, mais consomme **2 052 jetons de sortie** contre moins de 420 aux deux
autres, pour un contenu rendu de longueur comparable. Le surcoût est une
propriété du modèle.

Sans cette vérification, l'exclusion aurait reposé sur un plafond qu'on lui
avait soi-même imposé — un raisonnement circulaire.

### 3.4 Le corpus documentaire

| Grandeur | Valeur |
|---|---|
| Types de sources distincts | 5 — API REST, scraping, fichiers, base de données, big data |
| Documents entrés en transformation | 6 876 |
| Doublons retirés | 40 |
| Documents chargés en base | **6 836** |
| Documents diffusables | **6 753** — 82 licences non redistribuables, 1 retiré |
| Mots-clés, rattachements | 1 211, 20 544 |
| Rejets au chargement | 0 |

### 3.5 Le vector store

| Collection | Fragments |
|---|---|
| `eduai_knowledge_base` — corpus de cours | **387** |
| `eduai_corpus_documentaire` — corpus du pipeline | **0** — indexation écrite, non exécutée |

Projection pour la seconde : environ 23 000 fragments, estimée sur un essai à
blanc de 20 documents ayant produit 69 fragments. **C'est une projection, pas
une mesure.**

### 3.6 Ce que le monitorage a réellement observé — et c'est peu

C'est le point que ce document ne peut pas embellir.

| Type d'événement | Occurrences |
|---|---|
| Démarrages du monitorage | 45 |
| Appels au modèle (`appel_llm`) | **4** |
| Recherches RAG | **2** |

Et sur ces six événements, **aucun ne provient d'un usage réel** : deux appels
portent sur des modèles délibérément inexistants (`modele-qui-nexiste-pas`,
`modele-absent`), posés pour éprouver la sonde ; les deux recherches RAG ont
échoué en `ValueError` ; les deux appels aboutis étaient des vérifications
manuelles.

**Le monitorage fonctionne — c'est établi par ailleurs, les 90 appels du
benchmark ayant tous produit une trace vérifiée sur le disque. Mais il observe
une application que personne n'a encore utilisée.**

Il en découle qu'aucune affirmation sur le comportement du système **en usage**
n'est soutenable dans ce document : ni sur la charge, ni sur la pertinence des
réponses en situation, ni sur la répartition réelle des appels entre agents. La
mesure existe, l'objet à mesurer n'a pas encore eu lieu.

---

## 4. Ce que l'expérimentation a coûté en incidents

Un POC se juge aussi à ce qu'il a fait apparaître. **Quatre dossiers
d'incident** sont tenus dans `docs/incidents/`. Le tableau ci-dessous en reprend
les quatre, plus une panne antérieure à la mise en place du registre, consignée
dans la décision 001 plutôt que dans un dossier — la distinction est faite ici
pour qu'on ne compte pas cinq dossiers là où il y en a quatre :

| Incident | Ce qu'il a révélé |
|---|---|
| Modèle retiré du catalogue du fournisseur *(décision 001, hors registre)* | Un identifiant de modèle codé en dur dans trois fichiers rend le système otage du catalogue d'un tiers |
| Sonde branchée sans effet | Une sonde posée par variable de contexte au démarrage est invisible des fils qui traitent les requêtes — 22 heures de traces perdues en annonçant « sonde branchée » |
| Conversion Spark non scalable | Un traitement correct à petite échelle peut être rédhibitoire à grande : 13 analyses XML par ligne, 14 h 19 pour 48 tâches sur 775 |
| Chargement rapporté sans effet | Une transaction implicite transformait la validation en point de reprise : 6 836 documents annoncés sur une base vide |
| Service Ollama en boucle | Trois jours d'indisponibilité du RAG sans qu'aucune alerte ne se déclenche, et deux défauts distincts se masquant l'un l'autre |

Le motif est constant et il est le principal enseignement de ce POC : **dans un
système qui enchaîne un pipeline, un vector store, un fournisseur tiers et un
service local, l'échec le plus fréquent n'est pas l'erreur bruyante mais le
succès silencieux.** Chaque incident a donné lieu à un contrôle qui constate un
effet plutôt qu'une intention — relire le fichier au lieu du compteur, compter
les fragments rendus au lieu du `k` demandé, interroger `ollama list` au lieu de
`systemctl is-active`.

---

## 5. Les limites constatées

| Limite | Nature | Conséquence |
|---|---|---|
| **Aucune mesure de qualité** | Délibérée | Un modèle juge d'autres modèles avec des biais documentés — préférence pour les réponses longues, pour son propre style, pour sa famille. La notation est donc à la main, sur une grille écrite avant d'avoir vu une réponse. **Elle n'est pas encore faite.** Le volet « qualité » de l'hypothèse reste ouvert |
| **Tarifs non vérifiés à la source** | Externe | Les coûts sont des ordres de grandeur. La vérification demande la console du fournisseur, hors d'atteinte d'un script |
| **Compteurs Prometheus mono-processus** | Technique | Chaque processus — serveur Django, service FastAPI, scripts — tient ses propres compteurs. Les agréger suppose un collecteur multiprocessus qui n'est pas en place. Les chiffres exposés décrivent un processus, pas le système |
| **Corpus RAG partiel** | Arbitrage | 3 index construits sur 11 modules présents ; corpus documentaire non indexé |
| **Aucune trace d'usage réel** | Factuelle | Voir § 3.6. Rien ne peut être conclu sur le comportement en situation |
| **Souveraineté non mesurée** | Conséquence d'un incident | Les trois modèles mesurés envoient tous leurs prompts chez un tiers, alors que ceux de l'agent Coach contiennent du code d'apprenant. Le seul modèle qui aurait répondu autrement était en panne pendant la campagne. Le service est réparé depuis ; la mesure reste à faire |
| **Pas de comparaison à l'alternative** | Méthodologique | Aucune mesure ne compare l'architecture multi-agents à un appel unique. C'est la limite la plus sérieuse au regard de l'hypothèse posée au § 1 — mais elle est **finançable**, voir § 5 bis |

### 5 bis. La limite principale est finançable

L'absence de comparaison entre l'architecture multi-agents et un appel unique
est un manque réel. Elle n'est pas pour autant définitive, et il serait
malhonnête de la présenter comme telle : **elle coûte environ une heure de
machine libre.**

Le protocole existe déjà. Les dix prompts du benchmark C7 sont figés et
versionnés ; l'exécuteur sait passer un jeu de prompts sur un modèle donné en
relevant latence, jetons et coût ; l'analyseur sait en tirer médiane, dispersion
et coût pour mille requêtes. Ce qui manque est un seul terme de comparaison :

| Bras | Ce qu'on mesure |
|---|---|
| **Chaîne complète** | Les dix prompts routés vers leur agent, chacun sur son modèle, avec accès au corpus |
| **Agent unique** | Les dix mêmes prompts, un seul modèle généraliste, un seul prompt système, sans routage |

Trois répétitions par bras, mêmes paramètres, appels séquentiels : 60 appels, la
moitié de la campagne déjà réalisée. Les critères mesurés — latence cumulée par
requête, jetons totaux, coût pour mille requêtes — se lisent directement. Le
critère de qualité passe par la même grille de notation en aveugle, appliquée
aux vingt réponses.

**Ce qu'il faut écrire avant de mesurer**, et non après : ce qui compterait
comme un avantage. Une chaîne à quatre agents fait plus d'appels qu'un agent
unique ; elle sera donc plus coûteuse en volume brut. L'hypothèse porte sur le
rapport entre ce surcoût et le gain de qualité et de latence par tâche — c'est
ce rapport qu'il faut fixer comme critère avant la campagne, exactement comme
les six critères de C7 ont été fixés avant leur mesure.

Cette mesure est donc **proposée comme suite**, non consignée comme limite
définitive. Elle est la seule qui puisse répondre à l'hypothèse du § 1, et elle
tient dans une soirée.

---

## 6. La décision

### Ce qui est décidé

**L'architecture multi-agents est conservée**, et le routage acté en décision
001 est confirmé — non pas parce que le POC a démontré sa supériorité, mais
parce que les mesures disponibles la soutiennent sur les critères qu'elles
couvrent, et qu'aucune ne la contredit.

| Agent | Modèle | Critère décisif |
|---|---|---|
| Researcher | `openai/gpt-oss-120b` | Jetons de sortie les plus bas sur la tâche la plus exigeante |
| Pedagogue | `openai/gpt-oss-120b` | Qualité prioritaire ; 0,23 s d'écart imperceptible en génération de cours |
| Coach | `openai/gpt-oss-20b` | Latence de 0,75 s — le retour sur code est interactif |
| Watcher | `openai/gpt-oss-20b` | Latence la plus basse et coût le plus bas ; classer un mot n'appelle pas le modèle le plus fort |

**`qwen/qwen3.6-27b` est écarté** sur les mesures du § 3.3.

### Ce que cette décision engage

1. **Exécuter l'indexation du corpus documentaire.** Tant qu'elle n'a pas
   tourné, les 6 836 documents du pipeline restent hors de portée des agents, et
   la moitié « données » du projet ne sert pas la moitié « IA ».
2. **Faire la notation en aveugle.** C'est la seule chose qui puisse déplacer la
   décision, et d'une seule manière : si le modèle rapide se révélait nettement
   plus faible sur les prompts de l'agent Coach, l'écart de coût de 0,10 $ pour
   mille requêtes ne justifierait pas de le conserver là.
3. **Mesurer le repli local**, maintenant que le service est réparé. C'est la
   seule réponse au critère de souveraineté.
4. **Obtenir des traces d'usage réel** avant toute conclusion sur le
   comportement du système en situation.
5. **Mener la comparaison du § 5 bis** — dix prompts sur un agent unique contre
   la chaîne complète, une heure de machine libre — pour répondre enfin à
   l'hypothèse posée au § 1.

### Ce que cette décision ne prétend pas

Elle ne prétend pas que quatre agents valent mieux qu'un. Cette question, qui
est celle de l'hypothèse de départ, demanderait la mesure comparative décrite au
§ 5 bis. **Elle est identifiée et chiffrée, non traitée** — ce qui est préférable
à une conclusion qui aurait l'air d'y répondre, et honnête quant au fait qu'il
s'agit d'un report, non d'une impossibilité.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `benchmark_modeles.md` | Protocole, mesures et décision de la comparaison de modèles |
| `benchmark/mesures.jsonl` | Les 90 mesures brutes, recalculables |
| `decisions/001-externalisation-des-modeles-llm.md` | Routage initial des agents |
| `decisions/016-modeles-mesures-avant-decision.md` | Méthode de la comparaison |
| `incidents/` | Les quatre dossiers d'incident |
| `traceabilite.md` | Index des preuves par compétence |
