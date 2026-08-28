# Veille technique — au-delà du RAG classique : que retenir pour EduAI Tutor

**Date de la session :** 29/08/2026
**Compétence visée :** C6 (épreuve E2) — veille technique
**Thématique :** approches de récupération augmentée postérieures au RAG vectoriel
simple, et pertinence pour le corpus du projet

---

## 1. Pourquoi cette thématique

Le RAG d'EduAI Tutor est un RAG vectoriel plat : découpage, vectorisation dans
ChromaDB, recherche par similarité, transmission des fragments à l'agent. C'est
l'architecture la plus répandue, et la première implémentée.

Trois observations faites pendant la construction du corpus ont motivé cette
session :

1. Un fichier de 149 083 caractères a produit un seul document, ses soixante et
   onze titres étant au format Setext, non reconnu par le découpeur.
2. Dix-neuf sections d'une même page de documentation partagent une URL : une
   déduplication par URL en aurait supprimé dix-huit.
3. Le corpus est hétérogène — questions Stack Overflow, documentation
   officielle, cours en français, dump Data Science — donc les fragments n'ont
   ni la même longueur, ni la même langue, ni la même structure.

La question posée est donc concrète : **une architecture plus avancée
corrigerait-elle ces défauts, ou relèvent-ils du prétraitement ?**

---

## 2. Qualification des sources

| Source | Nature | Date | Fiabilité |
|---|---|---|---|
| Chen et al., *Is GraphRAG Needed?*, GEM 2026 (ACL) | Article scientifique évalué par les pairs | juin 2026 | **Haute.** Comparaison expérimentale de RAG simple, GraphRAG, modulaire et agentique |
| Panorama RAG, Labo LLM | Synthèse d'état de l'art | avril 2026 | **Moyenne à haute.** Position argumentée, recoupée avec l'article ci-dessus |
| Turing Post, panorama des variantes | Veille technique | août 2026 | **Moyenne.** Utile pour l'inventaire, à recouper — recense des travaux très récents, sans recul |
| Billets d'ingénierie divers | Retours d'expérience | 2026 | **Faible à moyenne.** Utiles pour le vocabulaire, pas pour trancher |

**Précaution retenue.** Beaucoup de publications sur ce sujet décrivent des
architectures sans les comparer à une base de référence. Un article qui présente
une technique sans la mesurer contre un RAG simple n'établit pas qu'elle est
supérieure — seulement qu'elle existe.

---

## 3. Le paysage en 2026

Le constat qui structure la littérature récente : **le RAG n'est plus une
technique mais une famille**, et le choix se fait sur le profil du corpus et
des questions, non sur une hiérarchie universelle.

### Trois grandes familles

| Famille | Principe | Quand elle convient |
|---|---|---|
| **Vectoriel dense** | Textes transformés en vecteurs, recherche par proximité sémantique | Corpus homogène, questions formulées en langage naturel |
| **Sparse / hybride** | Recherche par mots-clés combinée à la recherche sémantique | Vocabulaire technique précis, noms propres, identifiants exacts |
| **Émergentes** | GraphRAG, Self-RAG, Adaptive, Agentic | Corpus relationnel, questions à sauts multiples, exigence de vérification |

### Les approches avancées, en une ligne chacune

- **GraphRAG** construit un graphe de connaissances à l'ingestion et le parcourt
  à la requête. Il capture des relations entre entités que la similarité
  vectorielle plate ne voit pas.
- **Agentic RAG** transforme la récupération en boucle : le système décide s'il
  faut chercher, quoi chercher, et quand s'arrêter, au lieu d'une récupération
  unique.
- **Self-RAG** ajoute une étape de critique : le système évalue ses propres
  résultats de récupération et réduit les faux positifs.
- **LongRAG** exploite les grandes fenêtres de contexte avec un découpage
  minimal, pour éviter la fragmentation.

### Le débat du long contexte

Les fenêtres sont passées d'environ 128 000 jetons début 2024 à plus d'un
million en 2026, ce qui remet en cause une hypothèse fondatrice du RAG : à quoi
bon récupérer si l'on peut tout donner à lire ?

La réponse qui se dégage est nuancée : le long contexte **n'a pas remplacé le
RAG**, il a absorbé les petits corpus stables et laissé au RAG les corpus
volumineux, ceux qui évoluent, et ceux qui doivent citer leurs sources.

### Le résultat le plus utile

L'article de Chen et al. identifie un **écart entre récupération et
génération** : élargir la récupération n'améliore pas proportionnellement la
qualité de la réponse produite. Les métriques centrées sur la récupération
surestiment donc le bénéfice des architectures avancées.

C'est le constat qui pèse le plus sur une décision d'architecture : une
amélioration mesurée sur la récupération peut ne rien changer pour
l'utilisateur.

---

## 3 bis. Les approches qui ne s'appellent pas RAG

Toute la section précédente reste à l'intérieur d'une même famille : on récupère,
puis on génère. D'autres paradigmes répondent au même besoin — ancrer un modèle
dans une connaissance externe — sans passer par une récupération à la requête.

### CAG — génération augmentée par le cache

C'est l'alternative la plus sérieuse, formalisée par l'article *Don't Do RAG:
When Cache-Augmented Generation is All You Need for Knowledge Tasks*, présenté à
l'ACM Web Conference 2025.

**Le principe.** Au lieu de récupérer quelques fragments à chaque requête, on
précharge l'intégralité de la base de connaissance dans le contexte du modèle,
**une seule fois**, et on met en cache les états internes correspondants. À
l'inférence, le modèle n'a plus qu'à traiter la question et à s'appuyer sur le
cache déjà calculé.

Formule qui résume l'écart : le RAG récupère quelques fragments à chaque
requête, le CAG charge tout le corpus une fois et le réutilise.

**Les gains annoncés.** Suppression de la latence de récupération, disparition
des erreurs de sélection de documents, architecture nettement plus simple —
plus de vectorisation, plus de base vectorielle, plus de découpage. Les mesures
publiées font état de générations jusqu'à quarante fois plus rapides.

**Les limites, qui sont structurelles.** Le corpus entier doit tenir dans la
fenêtre de contexte, et la performance des modèles se dégrade sur les très longs
contextes. Les seuils qui circulent en 2026 : confortable sous 500 000 jetons,
utilisable mais dégradé sur les détails de 500 000 à 1,5 million, et au-delà le
RAG redevient le bon choix car le rappel en contexte long se dégrade plus vite
que la précision d'un récupérateur bien réglé.

**Le critère de fraîcheur, plus décisif que la taille.** Le cache hérite de la
fraîcheur de son écriture. Un corpus qui change quotidiennement invalide le
cache quotidiennement, et le coût d'écriture cesse de s'amortir. Le point de
bascule cité : **si le cache doit être réécrit plus d'une fois toutes les dix
mille lectures, le RAG revient moins cher.**

**Le motif dominant en production** n'est ni l'un ni l'autre mais un
**empilement** : CAG pour le noyau documentaire stable, RAG pour la longue
traîne.

### Récupération sans vecteurs, guidée par le raisonnement

Paradigme apparu fin 2025 et diffusé en 2026, dont l'implémentation de référence
est **PageIndex** (VectifyAI, open source).

**Le principe.** On supprime à la fois la base vectorielle et le découpage. Le
document est organisé en **arbre hiérarchique** suivant sa structure naturelle —
pages, sections, sous-sections — et le modèle **navigue** dans cet arbre par
raisonnement, comme un humain parcourt une table des matières. Le chemin est :
question → arbre du document → raisonnement du modèle → nœuds retenus →
génération.

L'inspiration revendiquée est la recherche arborescente d'AlphaGo.

**Ce que ça corrige, et qui nous concerne directement.** Les auteurs partent
d'un constat précis : sur des documents longs et spécialisés, **le vocabulaire
de domaine est sémantiquement homogène**, ce qui rend difficile la récupération
du passage exact. C'est très exactement le problème identifié plus haut avec
`itertools.groupby` ou `KeyError`.

Trois autres limites du RAG vectoriel qu'il adresse :

- **Les renvois internes.** « voir l'annexe G », « cf. tableau 5.3 » sont
  systématiquement manqués, faute de similarité sémantique avec la cible.
- **L'absence de raisonnement en plusieurs étapes.** Une recherche par
  similarité est un coup unique, sans exploration progressive.
- **Le découpage artificiel.** Rien n'est coupé : la structure de l'auteur est
  conservée.

**Les résultats annoncés.** 98,7 % d'exactitude sur FinanceBench, un jeu
d'évaluation de questions-réponses sur documents financiers, présenté comme
nettement supérieur au RAG vectoriel.

**Les limites.** Chaque récupération mobilise des appels au modèle pour naviguer
dans l'arbre — le coût se déplace de l'ingestion vers la requête, à l'inverse du
RAG vectoriel. L'approche est conçue pour des documents longs et structurés, pas
pour un corpus de fragments courts et indépendants.

**Une remarque de méthode.** Les chiffres les plus favorables proviennent de
l'éditeur de l'outil, sur un jeu d'évaluation qu'il a choisi. Ils indiquent une
piste sérieuse, pas une supériorité établie — la même précaution que celle
énoncée au §2 sur les publications sans base de référence.



| Approche | Principe | Quand elle a du sens |
|---|---|---|
| **Affinage (fine-tuning)** | On modifie les poids du modèle pour incorporer la connaissance | Style, format, vocabulaire de domaine. Mauvais pour les faits : coûteux à mettre à jour, et le modèle ne peut pas citer sa source |
| **Ingénierie de contexte** | On soigne ce qu'on met dans le prompt sans mécanisme de récupération | Corpus très petit et stable. C'est le CAG sans le cache |
| **Cache sémantique** | On met en cache les couples question / réponse déjà vus | Questions très répétitives. Se combine avec n'importe quelle architecture |
| **Appel d'outils / texte-vers-SQL** | Le modèle interroge une base structurée par requête, sans vectorisation | Données tabulaires, chiffres, agrégats — là où la similarité sémantique n'a aucun sens |

**Le point commun de ces approches** : aucune ne fournit d'attribution par
passage. Le modèle produit une réponse, mais on ne sait pas de quel document
elle vient. C'est un critère qui pèse lourd dans le cas présent.

---

## 4. Confrontation au corpus d'EduAI Tutor

| Approche | Pertinence ici | Décision |
|---|---|---|
| **Long contexte seul** | Corpus de 6 836 documents, en croissance. Et l'attribution CC BY-SA impose de citer la source de chaque contenu affiché — un contexte long ne trace pas l'origine d'un passage. | **Écartée.** L'obligation de licence rend la récupération nécessaire, indépendamment de la taille. |
| **GraphRAG** | Le corpus n'est pas naturellement relationnel : ce sont des explications indépendantes, pas des entités liées. Le coût d'ingestion serait payé sans contrepartie. | **Écartée.** Aucune question du tuteur n'exige de raisonnement à sauts multiples entre entités. |
| **Self-RAG** | Réduirait les fragments hors sujet. Intérêt réel, coût d'un appel supplémentaire par requête. | **Notée.** À évaluer si le taux de réponses hors sujet le justifie — donnée que le monitorage permettra de mesurer. |
| **Agentic RAG** | L'architecture multi-agents existe déjà, mais la récupération reste unique et non décidée. Le passage à une boucle multiplierait les appels facturés. | **Écartée pour cette version.** Le rapport coût/bénéfice n'est pas établi sur un corpus de cette taille. |
| **Recherche hybride (dense + mots-clés)** | **Le candidat le plus pertinent.** Le corpus contient du code et du vocabulaire exact : noms de fonctions, modules, messages d'erreur. Une recherche purement sémantique retrouve mal `itertools.groupby` ou `KeyError` — ce sont des chaînes littérales, pas des concepts. | **Retenue comme évolution prioritaire.** |
| **CAG sur l'ensemble du corpus** | 6 836 documents, dont un de 149 083 caractères : le volume dépasse largement la zone confortable. Et les sources sous CC BY-SA exigent une attribution par passage, que le cache ne fournit pas. | **Écartée.** Taille et obligation de licence, deux motifs indépendants. |
| **CAG sur le seul corpus propriétaire (S3)** | **Piste sérieuse.** Les 380 documents du corpus local sont stables — ils changent quand j'écris un cours, pas quotidiennement — et l'attribution n'y est pas contrainte puisque j'en détiens les droits. C'est exactement le profil décrit pour le CAG : noyau documentaire stable, faible fréquence de réécriture. | **Notée comme évolution.** Motif d'empilement : CAG pour le cours, RAG pour la longue traîne Stack Overflow. |
| **Affinage du modèle** | Incorporerait le style pédagogique, pas les faits. Un modèle affiné ne cite pas ses sources et se met à jour au prix d'un réentraînement. | **Écartée.** Le besoin porte sur des faits traçables, pas sur un style. |
| **Récupération sans vecteurs (PageIndex)** | **Le constat de départ est le mien** : sur un corpus technique, le vocabulaire de domaine est sémantiquement homogène et la similarité retrouve mal le passage exact. Et la navigation par structure aurait traité correctement les dix-neuf sections d'`itertools`, là où le découpage plat les a mises à plat. Mais l'approche vise des documents longs et structurés — elle convient à la documentation Python et au corpus local, pas aux 6 000 fragments courts et indépendants venant de Stack Overflow. | **Notée comme piste sérieuse, sur une partie du corpus seulement.** À réévaluer si la recherche hybride ne suffit pas. |
| **Appel d'outils / texte-vers-SQL** | Sans objet sur un corpus documentaire, mais pertinent pour la source S4 : les productions d'apprenants sont des données structurées, et une agrégation s'y fait mieux en SQL qu'en similarité sémantique. | **Notée.** Complémentaire du RAG, pas concurrente. |

### Le point qui compte

Les trois défauts observés au §1 — titres Setext, sections partageant une URL,
hétérogénéité — **ne relèvent d'aucune de ces architectures.** Ce sont des
défauts de découpage et de prétraitement.

Aucune approche avancée ne les corrigerait. Un GraphRAG construit sur un
document de 149 083 caractères non découpé produirait un graphe tout aussi
inutilisable.

C'est la conclusion la plus utile de cette session : **améliorer le
prétraitement avant de changer d'architecture.**

---

## 5. Impact concret sur le projet

| Constat | Conséquence pour EduAI Tutor |
|---|---|
| Les défauts observés sont des défauts de découpage | Traiter les titres Setext dans le découpeur de S3. **Action identifiée.** |
| La recherche sémantique retrouve mal les termes exacts | Évaluer une recherche hybride. Le corpus contient du code, où la correspondance littérale compte. |
| Écart récupération / génération | Ne pas mesurer la qualité du RAG sur la seule pertinence des fragments. Le monitorage trace déjà le nombre de fragments rendus — il faudra le corréler à la qualité perçue. |
| GraphRAG et Agentic coûtent cher | Écartés avec justification, non par méconnaissance. C'est une décision, pas une lacune. |
| L'obligation d'attribution impose la récupération | Le long contexte ne peut pas remplacer le RAG ici, quelle que soit l'évolution des fenêtres. Argument juridique autant que technique. |

**Action retenue** : corriger le découpage Setext, puis évaluer la recherche
hybride. Consigner l'écartement de GraphRAG et d'Agentic RAG dans une décision
d'architecture, avec leur motif.

---

## 6. À suivre

- Évolution du coût des fenêtres longues : si le prix au jeton continue de
  baisser, l'arbitrage récupération / contexte long se déplacera.
- Travaux sur l'évaluation des systèmes RAG, le point faible actuel du domaine.
- Maturité des implémentations de recherche hybride dans ChromaDB.

---

## 7. Ce que cette session m'a appris sur la méthode

Le réflexe naturel devant une liste d'architectures plus avancées est de vouloir
en adopter une. La lecture attentive conduit à l'inverse : mes trois problèmes
observés relèvent du prétraitement, et aucune architecture ne les résoudrait.

Deux règles que j'en tire :

1. **Diagnostiquer avant de choisir une solution.** J'ai commencé cette veille
   en cherchant « mieux que le RAG », alors que la question était « pourquoi mon
   RAG ne marche pas bien ». Ce ne sont pas les mêmes réponses.
2. **Se méfier des publications sans base de référence.** Une architecture
   présentée sans comparaison à un RAG simple n'établit pas sa supériorité.
   L'article de Chen et al. est utile précisément parce qu'il compare.
