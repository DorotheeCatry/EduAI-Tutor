# Monitorage du modèle d'IA — les métriques et leur interprétation

**Date :** 28 août 2026
**Compétence visée :** C11 (épreuve E3) — monitorer un modèle d'IA à partir des
métriques courantes et spécifiques au projet, en intégrant les outils de
collecte, d'alerte et de restitution
**Compétences concernées :** C20 (E5), C10 (E3), C7 (E2)

---

## Ce que ce document est

Le dispositif de monitorage est en place et fonctionne. Ce document ne le
présente pas : il **explique ce que chaque métrique mesure, ce qu'elle ne mesure
pas, et ce qu'on peut en conclure**.

La distinction n'est pas rhétorique. Une métrique se lit mal beaucoup plus
souvent qu'elle ne se collecte mal, et une lecture fausse est plus dangereuse
qu'une absence de mesure : elle produit une confiance. Chaque section ci-dessous
comporte donc une rubrique « ce qu'elle ne dit pas », qui est la partie utile.

---

## 1. Les trois volets, et où ils sont

| Volet | Réalisation | Emplacement |
|---|---|---|
| **Collecte** | Sonde branchée sur le mécanisme de rappels de LangChain ; journal en JSON Lines, une ligne par événement | `apps/monitoring/sondes.py`, `journal.py` |
| **Alerte** | Quatre seuils, avec plancher d'appels et délai de silence | `apps/monitoring/alertes.py` |
| **Restitution** | Exposition Prometheus sur `/monitorage/metriques`, tableau de bord Grafana provisionné par fichier | `apps/monitoring/metriques.py`, `vues.py`, `docker-compose.yml` |

Un choix structurant, motivé en décision 014 : **le journal n'est pas en base de
données.** Un incident qui touche PostgreSQL rendrait le journal indisponible au
moment précis où il servirait. Le fichier plat survit à la panne qu'il observe.

Un second : **la sonde est branchée globalement**, au point d'accroche de
LangChain, plutôt que site d'appel par site d'appel. Le projet compte une
vingtaine d'appels répartis dans quatre agents et un orchestrateur ; les
instrumenter un par un garantirait d'en oublier, et un monitorage qui couvre
quatre appels sur cinq donne une confiance qu'il ne mérite pas.

---

## 2. Les métriques du modèle

### 2.1 `eduai_appels_llm_total` — compteur

Étiquettes : `agent`, `modele`, `fournisseur`, `issue`.

**Ce qu'elle mesure.** Le nombre d'appels au fournisseur de modèles qui ont été
**menés à terme d'une manière ou d'une autre** — aboutis ou en erreur, l'issue
les distingue.

**Ce qu'elle ne dit pas.** Elle ne dit pas combien de requêtes les utilisateurs
ont adressées à l'application. Un agent peut appeler le modèle plusieurs fois
pour une seule requête, et une requête peut échouer avant d'atteindre le modèle.
**Le compteur d'appels au modèle n'est pas un compteur d'usage.**

**Comment la lire.** Par le rapport entre ses étiquettes plutôt que par sa
valeur absolue. La répartition par `agent` dit quel agent porte la charge ; la
répartition par `modele` permet de vérifier que le routage acté en décision 001
est bien celui qui s'applique — un modèle qui apparaît là où il n'est pas censé
être signale une variable d'environnement mal posée, ce qui est arrivé.

### 2.2 `eduai_erreurs_llm_total` — compteur

Étiquettes : code de retour du fournisseur, classe d'exception.

**Ce qu'elle mesure.** Les appels en échec, **ventilés par cause**.

**Pourquoi la ventilation est l'essentiel.** Un taux d'erreur global de 20 % ne
dit pas quoi faire. Les mêmes 20 % répartis par code disent trois choses
différentes : des `429` signalent un quota atteint, donc un problème de palier
tarifaire ; des `404` signalent un modèle retiré du catalogue, donc une
dépendance à corriger dans la configuration — c'est la panne du 25 août ; des
erreurs de connexion signalent une indisponibilité du fournisseur, sur laquelle
on ne peut rien.

**Ce qu'elle ne dit pas.** Elle ne compte que les erreurs **remontées jusqu'à la
sonde**. Un appel qui n'a jamais été émis — parce que le service qui devait le
faire ne démarrait pas — ne produit aucune erreur. C'est exactement la panne
Ollama du 25 au 28 août : trois jours d'indisponibilité, **zéro erreur
comptée**, parce qu'un service arrêté ne produit pas d'échec, il produit du
silence. Voir § 6.

### 2.3 `eduai_latence_llm_secondes` — histogramme

Étiquettes : `agent`, `modele`.

**Ce qu'elle mesure.** La durée écoulée entre le départ de l'appel et le retour
de la réponse complète, **du point de vue du processus appelant**.

**Ce qu'elle ne dit pas.** Elle ne sépare pas le temps de calcul du modèle du
temps de réseau, ni surtout du temps d'attente d'un quota. Le benchmark C7 l'a
établi de manière frappante : le client du fournisseur réessaie de lui-même
après un refus `429`, et son attente tombe **à l'intérieur** de l'appel
chronométré. Un appel a été relevé à 5,99 secondes alors que le modèle n'en
avait consommé qu'une fraction. **Une latence élevée n'est donc pas
nécessairement un modèle lent** ; elle peut être un compte au palier gratuit.

**Comment la lire.** Par ses quantiles, jamais par sa moyenne. Un histogramme
dont la médiane est basse et le neuvième décile élevé décrit un service
irrégulier, ce qu'une moyenne masque. Les valeurs de référence viennent du
benchmark, 90 appels mesurés :

| Modèle | Médiane | 9ᵉ décile |
|---|---|---|
| `openai/gpt-oss-20b` | 0,75 s | 1,20 s |
| `openai/gpt-oss-120b` | 0,98 s | 1,92 s |

Ces chiffres donnent le sens de l'échelle : une médiane qui doublerait
signalerait un changement réel, alors qu'une pointe isolée à 4 secondes est
ordinaire.

### 2.4 `eduai_jetons_total` — compteur

Étiquette : sens (entrée ou sortie).

**Ce qu'elle mesure.** Les jetons **rapportés par le fournisseur**, non estimés
depuis une longueur de texte. La distinction compte : une estimation par
comptage de caractères se trompe de 20 à 40 % selon la langue et le contenu, et
un coût calculé dessus serait faux d'autant.

**Ce qu'elle ne dit pas.** Les jetons de sortie **ne mesurent pas la longueur de
la réponse rendue à l'utilisateur** lorsque le modèle produit un raisonnement
visible. Le benchmark l'a montré : `qwen/qwen3.6-27b` consomme 2 052 jetons de
sortie pour un contenu utile comparable à celui que les autres rendent en moins
de 420. L'écart est du raisonnement, que l'utilisateur ne lit pas mais qu'il
paie. **Un compteur de jetons de sortie compte ce qui est facturé, pas ce qui
est livré.**

**Ce qu'elle ne dit pas non plus.** Une réponse tronquée au plafond de jetons se
lit dans ce compteur exactement comme une réponse naturellement courte. Seul le
rapprochement avec le plafond configuré les distingue.

### 2.5 `eduai_cout_estime_total` — compteur

**Ce qu'elle mesure.** Le cumul des coûts **estimés** : jetons rapportés ×
tarif de la table `apps/monitoring/tarifs.json`.

**Ce qu'elle ne dit pas, et c'est capital.** Ce n'est pas une facture. Toutes les
entrées de la table portent `"a_verifier": true` : **les tarifs n'ont pas été
confrontés à la grille du fournisseur.** Chaque événement de monitorage
transporte ce drapeau, précisément pour qu'un coût non vérifié ne puisse pas
être présenté comme un chiffre acquis.

**Comment la lire.** Par ses **rapports**, non par ses valeurs. Dire que le
modèle de qualité coûte 1,7 fois le modèle rapide reste vrai même si les deux
tarifs sont faux dans la même proportion ; dire qu'il coûte 0,236 $ pour mille
requêtes ne l'est que si le tarif l'est.

Un modèle absent de la table donne un coût **nul** — et non zéro. La distinction
est volontaire : un coût de zéro se confond avec un appel gratuit, un coût nul
se voit.

---

## 3. Les métriques du RAG

### 3.1 `eduai_recherches_rag_total` et `eduai_latence_rag_secondes`

Mêmes principes de lecture que leurs équivalents côté modèle.

### 3.2 `eduai_fragments_rendus` — histogramme

C'est la métrique **spécifique au projet**, celle qui n'apparaît dans aucun
tableau de bord générique, et elle mérite qu'on s'y arrête.

**Ce qu'elle mesure.** Le nombre de fragments **réellement rendus** par une
recherche.

**Pourquoi pas le nombre demandé.** Parce que le paramètre `k` d'une recherche
est une **intention**, et le nombre rendu un **effet**. Une recherche lancée
avec `k = 5` sur une collection qui n'en contient que 3 rend 3 fragments sans
lever la moindre erreur : le compteur d'appels dira « succès », la latence sera
bonne, et l'agent répondra sur un contexte au tiers de ce qu'il attendait. Seul
l'écart entre demandé et rendu révèle le problème.

**Comment la lire.** Un histogramme dont la masse se concentre en dessous du `k`
configuré signale un corpus trop petit ou un filtre trop restrictif — non une
panne. C'est la situation actuelle du projet : la collection du corpus
documentaire est vide, l'indexation étant écrite mais pas encore exécutée.

---

## 4. Les métriques du monitorage lui-même

Quatre métriques n'observent pas le modèle mais **l'appareil d'observation**.
Elles existent parce que le projet a connu une panne où la sonde s'annonçait
branchée et ne traçait rien pendant vingt-deux heures.

| Métrique | Ce qu'elle établit |
|---|---|
| `eduai_journal_evenements_emis_total` | Écritures **demandées** |
| `eduai_journal_lignes_ecrites_total` | Lignes **réellement écrites** |
| `eduai_journal_echecs_ecriture_total` | Écritures ayant échoué |
| `eduai_sonde_echecs_total` | Exceptions rattrapées **dans la sonde elle-même** |
| `eduai_journal_octets` | Taille du fichier, relue sur le disque à chaque collecte |

**Comment les lire ensemble.** C'est l'écart entre les deux premières qui porte
l'information : des événements émis qui n'arrivent pas sur le disque signalent
un disque plein, des droits manquants ou un chemin invalide. Une taille de
journal qui stagne pendant que le compteur d'événements progresse dit la même
chose autrement — et c'est pour cela que la taille est obtenue par un `stat` du
fichier plutôt que déduite du nombre d'événements : une valeur déduite ne peut
pas contredire celle dont elle est déduite.

`eduai_sonde_echecs_total` mérite un mot. La sonde n'a pas le droit de faire
tomber ce qu'elle observe : ses exceptions sont rattrapées. Mais **avaler une
erreur sans la compter reproduirait le motif que ce module existe pour
détecter** — d'où ce compteur, ventilé par méthode.

---

## 5. Les seuils d'alerte, et pourquoi ces valeurs

| Paramètre | Valeur | Raison |
|---|---|---|
| `APPELS_MINIMUM` | 5 | Sans plancher, le premier appel raté de la journée donnerait un taux d'erreur de 100 % et une alerte. Un taux calculé sur trop peu d'appels ne dit rien |
| `SEUIL_TAUX_ERREUR` | 0,20 | Au-delà d'un appel sur cinq en échec, la dégradation est perceptible par l'utilisateur |
| `SEUIL_LATENCE_SECONDES` | 10 | Délibérément large au regard des médianes mesurées, 0,75 à 0,98 s. Le seuil ne vise pas la lenteur ordinaire mais la panne : un appel à 10 secondes n'est plus un modèle lent, c'est une attente de quota ou un fournisseur en difficulté |
| `SILENCE_MINUTES` | 10 | Sans délai de silence, une indisponibilité durable produirait une alerte par appel, rendant illisible précisément ce qu'on cherche à observer. Vérifié par test : onze appels lents produisent une seule alerte |

Les quatre sont réglables par variable d'environnement, sans modification de
code.

---

## 6. La limite principale du dispositif

**Ce monitorage observe les appels qui passent. Il ne surveille pas la
disponibilité de ce dont il dépend.**

Un service externe arrêté ne produit aucun appel, donc aucune trace, donc aucun
taux d'erreur — et **le silence se confond avec le calme**. C'est ce qui a permis
à la panne Ollama de durer trois jours sans qu'aucune alerte ne se déclenche.
Elle a été découverte en cherchant autre chose.

Deux autres limites, à énoncer :

- **Les compteurs Prometheus sont mono-processus.** Serveur Django, service
  FastAPI et scripts tiennent chacun les leurs. Les agréger suppose un
  collecteur multiprocessus qui n'est pas en place : **les chiffres exposés
  décrivent un processus, pas le système.**
- **Il n'y a presque rien à observer.** Le journal de production contient 4
  appels au modèle et 2 recherches RAG, tous issus de vérifications manuelles.
  L'instrument est étalonné, l'objet à mesurer n'a pas encore eu lieu.

**Piste identifiée, non implémentée :** une sonde de disponibilité qui
interrogerait périodiquement les dépendances externes — Ollama, le fournisseur
de modèles, PostgreSQL — et consignerait leur état, plutôt que d'attendre qu'un
appel échoue pour l'apprendre.

---

## 7. Les déclencheurs de réentraînement — sans objet, et pourquoi

L'activité A5 du référentiel mentionne, parmi les usages du monitorage, « les
éventuels déclencheurs pour le réentraînement ». Le mot « éventuels » est
important : il admet que tous les projets n'en ont pas.

**EduAI Tutor n'en a pas, et ne peut pas en avoir.**

### La raison

Le projet **n'entraîne aucun modèle**. Il en **intègre** : `gpt-oss-120b` et
`gpt-oss-20b` sont servis par un fournisseur tiers, `qwen3:4b` et
`mxbai-embed-large` sont exécutés en local mais téléchargés, non produits ici.
Aucun jeu d'entraînement, aucun cycle d'apprentissage, aucun poids sous le
contrôle du projet. Un déclencheur de réentraînement supposerait quelque chose à
réentraîner.

### Pourquoi le dire plutôt que l'omettre

Une section absente se lit comme un oubli ; une section qui déclare le point
sans objet et l'explique se lit comme une analyse. Et l'analyse a une
conséquence pratique : elle désigne **ce qui remplace le réentraînement** dans
un projet d'intégration.

### Ce qui en tient lieu

Là où un projet d'entraînement surveille la dérive de son modèle pour décider de
le réapprendre, celui-ci surveille la dérive de **ses dépendances** pour décider
d'en changer. Trois signaux, tous outillés :

| Signal | Métrique | Décision qu'il déclenche |
|---|---|---|
| Un modèle disparaît du catalogue du fournisseur | `eduai_erreurs_llm_total` avec code `404` | Changer l'identifiant de modèle — la panne du 25 août |
| Le rapport coût-latence d'un modèle se dégrade | `eduai_latence_llm_secondes`, `eduai_jetons_total`, `eduai_cout_estime_total` | Rejouer le protocole du benchmark C7 et reconsidérer le routage |
| Le corpus cesse d'alimenter les réponses | `eduai_fragments_rendus` | Réindexer, ou étendre le corpus |

Le troisième est le plus proche d'un déclencheur de réentraînement au sens
propre : le RAG a bien une « base de connaissances » qui vieillit, et
`eduai_fragments_rendus` est la métrique qui dit qu'elle ne suffit plus. Mais ce
qu'on réentraîne alors est un **index**, pas un modèle — et la distinction doit
être tenue, sous peine de laisser croire à une capacité que le projet n'a pas.

### La conséquence, énoncée franchement

Ne pas entraîner de modèle **limite le projet** : il ne peut pas améliorer la
qualité de ses réponses autrement qu'en changeant de modèle, en modifiant ses
prompts ou en enrichissant son corpus. C'est une contrainte assumée, cohérente
avec le bloc de compétences visé — « intégrer des modèles et des services
d'intelligence artificielle » — et avec la contrainte matérielle réelle : la
machine du projet dispose d'un GPU de 4 Go.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `decisions/014-monitorage-hors-base-du-service-ia.md` | Pourquoi le journal n'est pas en base |
| `incidents/2026-08-28-sonde-branchee-sans-effet.md` | La panne qui a motivé les métriques du § 4 |
| `incidents/2026-08-28-ollama-service-en-boucle.md` | La panne que le dispositif n'a pas vue |
| `benchmark_modeles.md` | Les valeurs de référence des latences et des coûts |
| `apps/monitoring/` | Le code des trois volets |
