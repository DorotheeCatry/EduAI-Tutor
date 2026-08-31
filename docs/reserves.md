# Réserves connues

**Date de mise à jour :** 29 août 2026

Ce document recense ce qui, dans le dépôt, **ne fait pas ce qu'il a l'air de
faire**, ou ne le fait qu'en partie. Il ne remplace ni le journal de décisions,
qui dit pourquoi un choix a été fait, ni les dossiers d'incident, qui racontent
une panne et sa résolution. Il répond à une autre question : *que croirait à
tort quelqu'un qui lirait ce dépôt sans le connaître ?*

Le projet a documenté cinq incidents dont le motif commun est qu'une action et
son effet ne coïncidaient pas — un chargeur annonçant 6 836 documents sur une
base vide, une sonde de monitorage se déclarant branchée sans rien tracer. Ce
registre est la version préventive du même constat : signaler plutôt que
laisser croire.

---

## 1. Le quiz multijoueur n'a pas de client

**Composant :** `apps/quiz/consumers.py`, `apps/quiz/routing.py`
**Nature :** fonctionnalité serveur sans interface

Le consommateur WebSocket du quiz multijoueur est complet côté serveur :
connexion à un salon, diffusion de l'état, génération des questions, envoi des
questions une à une, collecte des réponses, calcul des résultats, fin de
partie.

**Aucun gabarit du projet n'ouvre de connexion WebSocket.** Une recherche de
`WebSocket`, `onmessage` ou `socket` dans `apps/quiz/templates/` ne renvoie
rien. Le code serveur existe, il est atteignable, il n'est appelé par personne.

Deux conséquences à ne pas confondre :

- **Ce qui fonctionne** : le quiz solo, servi par les vues Django classiques
  (`quiz_start`), avec génération par le Coach. C'est ce qui sera démontré.
- **Ce qui n'est pas démontrable** : le mode multijoueur temps réel.

Le chemin serveur a néanmoins été corrigé le 29 août, parce qu'il constituait
une dépense possible sans quota : il générait des questions sans utilisateur
identifié. Il est désormais imputé à l'hôte du salon et son résultat n'est plus
ignoré. **Corriger un chemin mort reste utile — le code inerte d'aujourd'hui est
le code appelé de demain** — mais cela ne le rend pas vivant pour autant.

---

## 2. Le corpus vectoriel est monté en écriture

**Composant :** `docker-compose.yml`, service `service_ia`
**Nature :** protection retirée, risque assumé

Le montage du corpus portait `:ro`. ChromaDB s'appuyant sur SQLite, qui écrit
son journal WAL et ses verrous même en lecture, la protection empêchait
l'ouverture de la base et rendait `/ai/recherche` inutilisable.

Le `:ro` a été retiré. Le conteneur du service IA peut donc écrire dans
`apps/rag/chroma`. Le risque est borné — corpus reconstructible, aucune donnée
personnelle, aucune route d'écriture exposée — mais il n'est pas nul.

Détail complet : décision `018-corpus-vectoriel-monte-en-ecriture.md`,
incident `2026-08-29-corpus-vectoriel-monte-en-lecture-seule.md`.

---

## 3. Le quota se remet à zéro à minuit, pas 24 heures après

**Composant :** `apps/quotas/service.py`
**Nature :** écart assumé entre l'intention et l'implémentation

Le plafond individuel est de cinq générations « par jour », et le jour est le
jour calendaire. Une personne peut donc consommer cinq générations à 23 h 50 et
cinq autres à 00 h 10.

Une fenêtre glissante de 24 heures exigerait d'horodater chaque génération,
c'est-à-dire de constituer un journal nominatif d'activité — une donnée
personnelle que la minimisation du RGPD déconseille de détenir (C4). Le plafond
global, lui, reste borné par jour, et c'est lui qui protège le budget.

Détail : décision `019-quotas-de-generation-avant-mise-en-ligne.md`.

---

## 4. Les messages du quota sont en français, l'interface en anglais

**Composant :** `apps/quotas/service.py`, `templates/quotas/`
**Nature :** incohérence de langue, assumée

L'interface de l'application est majoritairement en anglais, héritage de son
développement initial. Les messages ajoutés en août 2026 — refus de quota,
compteur de générations restantes — sont en français.

Le choix est délibéré : ces messages sont ceux que le jury lira pendant la
démonstration, et l'homogénéisation linguistique de toute l'interface n'est pas
un chantier ouvrable avant le 4 septembre. L'incohérence est visible ; elle est
signalée ici plutôt que découverte.


---

## 5. L'interface dépend de deux CDN externes

**Composant :** `templates/base.html` et gabarits d'authentification
**Nature :** dépendance externe non maîtrisée à l'exécution

Les pages chargent Tailwind depuis `cdn.tailwindcss.com` et les icônes depuis
`unpkg.com`. Le projet compile pourtant sa propre feuille Tailwind
(`theme/static/css/dist`), servie par WhiteNoise — les deux mécanismes
coexistent, et c'est le CDN qui l'emporte sur ces pages.

Trois conséquences :

- une panne ou un blocage de l'un des deux CDN suffit à rendre l'interface
  illisible, sans que le serveur signale quoi que ce soit ;
- ~~la version chargée est `@latest` pour les icônes, donc non figée~~ —
  **corrigé le 29/08/2026.** Les deux références flottantes ont été figées sur
  ce que les URL servaient ce jour-là, vérifié par comparaison d'empreintes :
  Tailwind `3.4.17` et Lucide `1.37.0`. Le rendu du jour est donc inchangé,
  et une publication amont ne peut plus le modifier pendant la période de
  soutenance ;
- l'adresse IP de chaque visiteur est communiquée à deux tiers, ce qui est à
  signaler dans la documentation RGPD si l'application est ouverte au-delà de
  la démonstration.

Ce qui subsiste après correction : la disponibilité des deux CDN et la fuite
d'adresse IP vers deux tiers. Rien de tout cela n'empêche la démonstration.
C'est une dépendance réelle, qu'il vaut mieux avoir écrite que découvrir
pendant une soutenance.

---

## 6. ~~L'image de l'application pèse 5,7 Gio~~ — levée le 30/08/2026

**Composant :** `Dockerfile`
**Nature :** coût de déploiement, non bloquant
**Statut :** **levée**, mesures à l'appui

L'image construite pesait 5,7 Gio décompressés. Trois retraits l'ont ramenée à
**1,3 Go**, et celle du service IA de 5,3 Go à **1,26 Go** :

| Retrait | Gain | Ce qui rendait le poids inutile |
|---|---|---|
| Cache `uv` (`UV_NO_CACHE=1`) | −1 816 Mio | Le cache reste dans la couche qui l'a créé, pour un contenu qui ne sert qu'à la construction |
| PySpark hors du socle | −344 Mio | Importé par le seul extracteur big data, exécuté hors ligne sur le poste |
| Corpus vectoriel | −219 Mio | Monté depuis un volume persistant (décision 023) |

La réserve annonçait que « toucher au découpage des dépendances à six jours du
rendu risque plus que cela ne rapporte ». L'arbitrage a changé pour une raison
précise : la chaîne publie désormais ces images à chaque livraison, et
l'hébergeur les télécharge à chaque déploiement. Un poids qui ne coûtait qu'un
disque local coûte maintenant du temps à chaque étape.

Le déplacement de PySpark est resté circonscrit : un groupe de dépendances
`pipeline`, installé par défaut sur le poste et en intégration continue
(`default-groups`), écarté des seules images (`--no-default-groups`). La source
big data reste installable, testée, et exigée par C1 — c'est son lieu
d'installation qui a changé, pas son existence.

Ce qui subsiste : la séparation de ChromaDB en service distinct (décision 018)
reste à reprendre après le 14 septembre.

---

## 7. La latence d'embarquement en production — mesurée, arbitrée, assumée

**Composant :** serveur d'embarquement déployé (`docker/ollama/Dockerfile`)
**Nature :** performance en conditions réelles ; peut rendre le RAG non
démontrable devant un jury
**Statut :** **ouverte** — mesure partielle, arbitrage en attente

Le RAG embarque chaque requête avant de chercher dans le corpus. Sur le poste,
Ollama dispose de la machine ; chez l'hébergeur, **il n'y a pas de GPU**.

### Ce qui est mesuré

| Mesure | Poste | Railway |
|---|---|---|
| `/api/embeddings`, 9 jetons | — | **13,6 s** |
| `/api/embeddings`, 343 jetons | — | **52,2 s** |
| `POST /ai/recherche`, premier appel après démarrage | — | **90 s** |
| `POST /ai/recherche`, à chaud — 9 tirs | **3 s** | **médiane 28 s**, de **14 s** à **59 s** |
| Latence comptée par le service | **3,7 s** | 13,4 s à 56,3 s — soit la quasi-totalité du temps constaté |
| Mémoire du serveur d'embarquement | — | **800 Mo** (estimation initiale : 2 Go) |

Relevés du 30/08/2026. Le modèle est environ **trois fois plus lent** qu'en
local.

### Ce que la mesure du 31/08 apprend

Le corpus est en place sur le volume, la recherche fonctionne, et neuf tirs à
chaud donnent une **médiane de 28 secondes**, entre 14 et 59.

Trois enseignements, tous issus des chiffres :

- **Le préchauffage est écarté par la mesure.** Les neuf tirs sont *à chaud*,
  le modèle déjà chargé, et ils restent entre 14 et 59 secondes. Le coût n'est
  pas au chargement, il est à l'inférence — préchauffer ne réduirait que les
  90 secondes du tout premier appel.
- **Ce n'est pas le transport.** Le service s'attribue 13,4 s sur 14 s
  constatées, et 56,3 s sur 58,9 s. Le réseau ne pèse rien ; c'est
  l'embarquement de la requête qui prend tout.
- **La dispersion est le fait le plus gênant.** Un facteur quatre entre le
  meilleur et le pire tir, sans que la requête change de nature. Une
  démonstration devant jury tomberait aussi bien sur 14 que sur 59 secondes, et
  on ne peut pas promettre laquelle.

La mémoire, elle, n'est plus un sujet : 800 Mo mesurés contre 2 Go estimés.
C'est la latence qui coûte, pas l'empreinte.

### L'arbitrage, si la mesure est de l'ordre de quarante secondes

Trois options, aucune tranchée à ce jour :

| Option | Ce qu'elle donne | Ce qu'elle coûte |
|---|---|---|
| ~~**Préchauffage**~~ | ~~Un modèle déjà chargé évite le coût du premier appel~~ | **Écartée le 31/08 par la mesure** : les neuf tirs à chaud restent entre 14 et 59 s. Ne sauverait que les 90 s du premier appel |
| **Modèle d'embarquement plus léger** | Inférence plus rapide sans GPU | **Impose de réindexer les 21 189 fragments** : les vecteurs d'un autre modèle n'ont aucun rapport avec ceux du corpus. Plus de dix-sept heures, et le corpus déployé devient inutilisable entre-temps |
| **Démonstration du RAG en local**, le reste déployé | Une recherche à 3 s devant le jury | Affaiblit la démonstration : ce qui est montré n'est plus ce qui est déployé, et il faut le dire |

### L'option « plus de processeur », mesurée le 31/08

C'était la seule option sans réindexation, donc la seule ouvrable à quatre
jours du rendu. Elle a été chiffrée avant d'être choisie.

**Ce que l'hébergeur impose aujourd'hui**, relevé par `railway metrics` : tous
les services sont plafonnés à **2 vCPU et 1024 Mio**. Ce sont les limites du
palier d'essai, non un réglage par service : les relever est une décision
d'abonnement. Le serveur d'embarquement occupe **1010 Mio sur 1024, soit 99 %**
— il vit à son plafond mémoire.

**Le gain a été mesuré en local**, en rejouant la même image d'embarquement
sous les mêmes contraintes, puis sans elles :

| Contexte | Texte court | Texte long |
|---|---|---|
| Poste bridé à **2 vCPU / 1 Go** — les plafonds de l'hébergeur | **0,43 s** | **4,86 s** |
| Poste entier, **8 vCPU / 8 Go** | **0,23 s** | **2,27 s** |
| **Railway, 2 vCPU** (mesures du 30/08) | **13,6 s** | **52,2 s** |

Moyennes de trois tirs, modèle préchargé hors mesure.

**Deux enseignements, et le second n'était pas attendu.**

Quadrupler les vCPU rapporte **un facteur deux environ**, pas quatre :
l'inférence ne se parallélise pas linéairement. Reporté à la médiane constatée
en production, 28 secondes, un passage à 8 vCPU ferait espérer **une quinzaine
de secondes**. C'est mieux, ce n'est pas démontrable.

Surtout : à **contraintes identiques**, le poste est 11 à 32 fois plus rapide
que l'hébergeur. Le problème n'est donc pas le *nombre* de vCPU alloués, mais
leur *vitesse* — des cœurs partagés, mutualisés, dont la dispersion d'un facteur
quatre observée en production porte la signature. Aucune quantité de vCPU de
cette qualité ne ramènera la recherche à trois secondes.

**Réserve mesurée, non levée.** Relever le plafond reste utile pour la mémoire —
99 % d'occupation expose à un arrêt brutal du service — mais ne rend pas le RAG
démontrable en direct. Rien ne garantit non plus que les cœurs d'un palier
payant soient les mêmes, et cela ne se mesure qu'en payant.

### Décision

**On assume et on documente**, conformément à l'arbitrage du 31/08 : pas de
changement de modèle d'embarquement à quatre jours du rendu — il imposerait de
réindexer 21 189 fragments et de retéléverser deux volumes.

Ce qui est dit en soutenance, plutôt que découvert : la recherche documentaire
est déployée, fonctionnelle et vérifiée sur l'URL publique ; elle répond en une
trentaine de secondes chez l'hébergeur contre trois secondes en local, faute de
GPU et sur des cœurs mutualisés ; l'écart est mesuré, sa cause est identifiée,
et la démonstration en direct se fait donc en local si le temps de la soutenance
l'exige.

**Ce qui ne change pas quelle que soit l'issue** : le déploiement lui-même, les
deux API, l'application et le monitorage ne dépendent pas de cette latence. Ce
qui est en jeu est la démonstrabilité d'une fonction, pas la validité du
déploiement.

---

## 8. ~~Les deux services se connectent à PostgreSQL en superutilisateur~~ — levée le 31/08/2026

**Composant :** variables d'environnement de `web` et `service-ai` chez l'hébergeur
**Nature :** moindre privilège non appliqué à la connexion applicative
**Statut :** **levée le jour même**, vérifications à l'appui

Les deux services portent `POSTGRES_USER=postgres`, le superutilisateur créé
par le modèle PostgreSQL de l'hébergeur. Une injection SQL aboutie, ou une
erreur de ciblage dans une migration, s'exercerait donc sans aucune borne : les
deux bases, les rôles, l'instance entière.

Ce n'est pas le cas de l'API du jeu de données, qui utilise bien `eduai_lecture`
— rôle de lecture seule créé le 31/08, **et vérifié dans les deux sens** : il
lit les 6 836 documents, il ne peut ni écrire, ni créer une table, ni depuis ce
jour se connecter à `eduai_app`. C'est le reste de l'application qui passe en
superutilisateur.

### La correction, appliquée le 31/08

Le rôle `eduai_application` — sans privilège de superutilisateur — a été créé,
et les 46 objets de `eduai_app` lui ont été transférés objet par objet. **Pas
par `REASSIGN OWNED`** : cette commande s'applique à tout ce que le rôle
possède, y compris des objets partagés de l'instance, et `postgres` est le rôle
d'amorçage du serveur. Une boucle explicite ne touche que le schéma visé.

Un détail a d'abord fait échouer le transfert, et il valait mieux qu'il échoue :
les séquences rattachées à une colonne d'identité ne se transfèrent pas
séparément de leur table. Le bloc étant transactionnel, rien n'avait été
modifié à moitié.

### Ce qui a été vérifié, dans les deux sens

| Vérification | Attendu | Constaté |
|---|---|---|
| `eduai_application` est superutilisateur ? | non | **false** |
| Lit les tables applicatives | oui | **1 compte lu** |
| `CREATE TABLE` puis `DROP TABLE` — une migration | possible | **possible** |
| Se connecte à `eduai_data` | refus | **permission denied for database** |
| `eduai_lecture` lit toujours le jeu de données | oui | **6 836 documents** |
| Migrations Django au redéploiement | passent | **« No migrations to apply »**, sous le nouveau rôle |
| Application web après bascule | répond | **`/auth/login/` 200** |

`REVOKE CONNECT ON DATABASE eduai_data FROM PUBLIC` complète la symétrie :
`eduai_app` avait été fermée au pseudo-rôle `PUBLIC` la veille, `eduai_data` ne
l'était pas.

### Un effet de bord utile

Les deux services portaient une **copie littérale** du mot de passe
superutilisateur, et non une référence : le renouveler aurait mis les deux
services à terre sans prévenir. Ils dépendent désormais du mot de passe du rôle
applicatif, et le mot de passe superutilisateur peut être renouvelé sans les
toucher.

### Ce qui reste

Le rôle applicatif est propriétaire du schéma, donc capable de le modifier —
c'est nécessaire aux migrations Django. Un découpage plus fin, séparant le rôle
qui migre de celui qui sert les requêtes, serait la étape suivante. Elle n'est
pas ouverte avant le 14 septembre.

---

## 9. « L'empreinte en dernier » ne protège pas d'un échec en première position

**Composant :** procédure de transfert du corpus (`docs/chaine_livraison.md`, § 7.4)
**Nature :** limite de conception du contrôle d'intégrité, non erreur d'exécution
**Statut :** **ouverte**, constatée le 31/08/2026

La procédure de transfert pose une règle : téléverser `EMPREINTE.json` **en
dernier**, parce que c'est elle qui atteste que le corpus est complet. Un
transfert interrompu laisse alors un corpus partiel sans empreinte, donc
visiblement incomplet.

**Cette règle ne couvre que la dernière moitié du problème.**

Le 31/08, au transfert vers le volume de l'application web, la **première**
montée — la collection pédagogique — a échoué sur un `Timeout`. Les quatre
suivantes ont réussi, empreinte comprise. Résultat : **un corpus incomplet
attesté complet**, et attesté par le dispositif même qui existe pour l'éviter.

L'ordre des opérations ne protège que d'une interruption *à la fin*. Il ne dit
rien d'un échec *au début* suivi d'une reprise qui se poursuit comme si de rien
n'était.

### Ce qui a rattrapé le coup, et qui n'était pas le dispositif

Une comparaison fichier par fichier des tailles, volume contre poste, faite à la
main après avoir lu le mot `Timeout` dans la sortie. Autrement dit : la
vigilance de l'opérateur, pas le contrôle. Un transfert lancé sans regarder la
sortie aurait produit exactement la même attestation mensongère.

### La correction, et pourquoi elle n'est pas encore faite

Elle est connue : **vérifier chaque partie avant d'écrire l'attestation**. Le
transfert devrait être un script unique qui téléverse, relit la liste distante,
compare tailles et nombre de fichiers à la source, et n'envoie `EMPREINTE.json`
qu'ensuite — l'attestation portant alors sur une vérification, non sur un ordre
d'exécution.

Ce n'est pas fait à quatre jours du rendu, parce que le corpus est en place sur
les deux volumes et vérifié. Écrire ce script maintenant ajouterait du code non
éprouvé à un chemin qui fonctionne.

**Ce que cette réserve dit du motif récurrent du projet.** Les huit incidents
documentés partagent une forme : une action et son effet ne coïncident pas sans
qu'on aille le constater. Celui-ci ajoute une nuance — le contrôle existait, il
était correct, et il a quand même attesté du faux, parce qu'il vérifiait
**l'ordre** des opérations et non **leur résultat**. Un contrôle qui repose sur
une convention d'exécution n'est pas un contrôle : c'est une convention.

---

## 10. L'interface est traduite, le contenu pédagogique ne l'est pas

**Composant :** corpus vectoriel, cours et exercices générés
**Nature :** limite fonctionnelle assumée de l'internationalisation
**Statut :** **ouverte**, énoncée le 31/08/2026

L'interface passe désormais du français à l'anglais selon le choix de
l'apprenant. **Ce qu'elle affiche à l'intérieur, non.**

| Élément | Langue | Pourquoi |
|---|---|---|
| Menus, boutons, formulaires, messages | fr ou en, au choix | Traduits, catalogues `locale/` |
| Fragments du corpus RAG | **anglais** | Stack Overflow et la documentation Python sont en anglais |
| Cours générés | français | L'orchestrateur passe `language_preference` au modèle |
| Quiz et exercices générés | fr ou en | Idem, le modèle génère dans la langue demandée |

Un apprenant qui choisit l'anglais obtient donc une interface anglaise, des
cours anglais — et des sources citées en anglais, ce qui est cohérent. Un
apprenant francophone obtient une interface et des cours français, **mais des
extraits de corpus en anglais**, puisque c'est la langue des documents
d'origine.

### Pourquoi le corpus n'est pas traduit

Traduire 21 189 fragments demanderait un appel au modèle par fragment, puis une
réindexation complète — les vecteurs d'un texte traduit n'ont aucun rapport
avec ceux de l'original. Ce serait plusieurs dizaines d'heures de traitement
pour dégrader la matière : une réponse technique traduite automatiquement perd
la précision de ses termes, et c'est précisément ce qu'un apprenant vient
chercher.

**Ce n'est pas un contournement, c'est le comportement attendu d'un RAG.** La
recherche documentaire cite ses sources ; une source citée dans une autre
langue que l'originale n'est plus une citation.

### Ce qu'il faut en dire

À l'oral, et dans l'interface le jour où le public le justifiera : le service
est bilingue pour ce qu'il dit lui-même, et monolingue pour ce qu'il cite. Les
extraits du corpus portent déjà leur attribution — titre, licence, source — ce
qui rend leur origine visible ; il manque l'indication de leur langue.

### Ce qui serait à faire, après le 14 septembre

Porter la langue de chaque fragment dans ses métadonnées à l'indexation, et
l'afficher à côté de l'attribution. Le champ n'existe pas aujourd'hui dans le
corpus indexé — l'ajouter suppose de rejouer l'indexation, ce que la réserve 7
a déjà écarté pour d'autres raisons.

---

## 11. Les erreurs de quiz sont rattachées au sujet, non à la notion

**Composant :** `apps/agents/agent_coach.py` — invite de génération de quiz
**Nature :** granularité du suivi, limite fonctionnelle
**Statut :** **ouverte**, tenue en réserve le 31/08/2026

Depuis l'incident 010, une erreur de quiz est enregistrée sous le sujet du quiz
entier — « les listes en Python » — et non sous la notion de la question qui a
échoué. Un quiz de dix questions couvrant l'indexation, le découpage et les
compréhensions produit dix erreurs portant le même libellé.

**Ce que cela permet quand même** : le bloc « à revoir » de la page d'accueil
fonctionne. Il désigne un sujet à retravailler, ce qui est utile et honnête.

**Ce que cela empêche** : distinguer deux notions à l'intérieur d'un même quiz,
donc rattacher finement une erreur à une compétence du référentiel.

### Pourquoi ce n'est pas corrigé maintenant

Le corriger suppose de modifier l'invite du coach pour qu'il produise une
notion par question. **Modifier une invite change le comportement de
génération**, et à quatre jours du rendu il n'y aurait pas le temps de mesurer
ce que ce changement fait par ailleurs : format de la réponse, taux d'échec de
l'analyse JSON, qualité des questions. Un modèle qu'on réoriente sans mesurer
est un modèle dont on ne sait plus ce qu'il fait.

C'est l'arbitrage explicite du 31/08 : le sujet du quiz suffit à ce que la page
doit montrer, et le gain de finesse ne vaut pas le risque de régression sur la
génération.

### À faire après le 14 septembre

Ajouter un champ `notion` par question dans l'invite et dans le schéma attendu,
mesurer le taux d'analyse réussie avant et après, puis rattacher l'erreur à
cette notion plutôt qu'au sujet. Les erreurs déjà enregistrées garderont le
libellé du sujet : elles ne sont pas rattrapables, et ce paragraphe est leur
explication.
