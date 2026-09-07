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

## 7. La latence d'embarquement en production — mesurée, arbitrée, puis corrigée

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

### Correction du 31/08, au soir : la mesure d'hier était fausse, et ma conclusion avec

**Médiane passée de 28 secondes à 4,6.**

| Relevé | n | min | médiane | max |
|---|---|---|---|---|
| 31/08 matin | 9 | 14,0 s | **28,4 s** | 58,9 s |
| 31/08 soir | 7 | 3,5 s | **4,6 s** | 14,5 s |

Rien n'a changé du modèle, du processeur ni du corpus. Ce qui a changé est
`OLLAMA_KEEP_ALIVE=24h`, posé le soir même — **pour borner la mémoire**, sans
penser à la latence.

**Ollama décharge son modèle après cinq minutes d'inactivité.** Les neuf
mesures du matin étaient espacées : chacune rechargeait un modèle de 670 Mio
avant d'embarquer la requête. Ce que je mesurais n'était pas le coût de
l'inférence, c'était le coût du rechargement.

### Ce que cela dit de ma conclusion précédente

J'avais écarté le préchauffage en écrivant : « les neuf tirs sont **à chaud**,
le modèle déjà chargé ». **Je ne l'avais pas vérifié.** Je l'avais supposé, et
la supposition était fausse.

Le préchauffage n'était donc pas l'option écartée par la mesure : c'était la
réponse, et elle est arrivée par accident, en réglant autre chose.

C'est une occurrence de plus du motif que ce projet documente — affirmer un
état sans l'avoir constaté — dans le document même qui recommandait de mesurer
plutôt que de supposer. Le paragraphe fautif est conservé ci-dessous, non
réécrit.

### Ce que cela change pour la soutenance

Une recherche à 4,6 secondes de médiane est **démontrable en direct**. Le
maximum observé, 14,5 s, reste long mais tenable ; il correspond
vraisemblablement aux appels qui suivent une période creuse.

Le premier appel après un déploiement reste à ~90 s : le modèle se charge. À
prévoir avant la démonstration — une recherche à blanc suffit.

**Le seuil d'alerte de latence, réglé à 75 s hier sur la dispersion d'alors,
est désormais très au-dessus du régime réel.** Il ne se déclenchera plus
jamais, ce qui est le défaut inverse de celui qu'il corrigeait. À ré-dériver
sur le nouvel échantillon quand il sera plus fourni — et pas avant, faute de
refaire la même erreur dans l'autre sens.

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

---

## 12. ~~Sept foyers de données fabriquées~~ — levée le 31/08/2026

**Composants :** `apps/tracker/`, `apps/revision/`, `apps/quiz/`
**Nature :** l'interface présentait comme mesuré ce qui était fabriqué
**Statut :** **levée**, incident 011

Le chantier de la page d'accueil signalait « Python Basics 85 % » sur le
tableau de bord. Les vérifications successives en ont trouvé **sept**, et le tableau de bord
n'était pas le pire.

| Emplacement | Ce qui s'affichait |
|---|---|
| `tracker/views.py` | Temps d'étude = `total_courses * 25`, **taux de réussite = `60 + xp // 50`**, semaine d'activité dérivée du temps simulé, score des cours = `70 + xp // 30`, **trois sujets inventés ajoutés** quand l'apprenant n'en avait pas assez, objectifs hebdomadaires par modulo |
| `revision/flashcards.html` | **Toute la page** : séance inventée, 24 cartes maîtrisées, 92 % de réussite, 7 jours de série. La vue ne passait aucune donnée |
| `quiz/quiz_lobby.html` | 127 quiz terminés, 85 % d'exactitude, 12 jours, 3 h 42 — en dur, identiques sur tous les comptes |
| `exercises/views.py` | Les exercices de **repli**, créés quand la génération échoue, étaient rattachés à une compétence. Leur solution attendue est `return 'Hello World'` : trois échecs de génération auraient donné un niveau 2 |
| `chat/views.py` | `'timestamp': '12:34:56'` — trois fois, en dur. Chaque message du tuteur portait la même heure |
| `templates/base.html` | Un compteur JavaScript partant de **154 minutes**, incrémenté chaque minute, écrivant « Session: 2h 34m » dans un élément que la barre d'état venait de remplir avec la série réelle de l'apprenant |

### Le septième mérite d'être distingué

Les six premiers **inventaient** une donnée là où il n'y en avait pas. Le
septième **écrasait une donnée mesurée par une donnée fabriquée** : la barre
d'état affichait la série réelle, rendue par le serveur, et une minute plus
tard le JavaScript la remplaçait par un compteur parti de 154.

C'est la seule variante où la fabrication ne comble pas un vide, mais recouvre
une mesure.

### Ce qui distingue ce cas d'une maquette oubliée

Une valeur en dur dans un gabarit se comprend. Mais
`success_rate = min(95, 60 + (user.xp // 50))` est un **calcul**, écrit en
Python, commenté « Between 60% and 95% ». Quelqu'un a voulu que le chiffre ait
l'air vivant — et c'est précisément ce qui le rendait crédible. Un zéro se
remarque ; un chiffre vraisemblable, non.

C'est la forme **délibérée** du motif, et elle est plus grave que l'oubli : un
nombre qui bouge avec l'usage est cru.

### Ce qui a été fait

Tout est remplacé par du mesuré, ou **annoncé comme non mesuré**. Le champ
`total_study_time_minutes` n'est écrit par aucun code du projet : la page le dit
au lieu de le simuler. Les exercices de repli ne sont plus rattachés — un
exercice qui se réussit en secondes ne doit pas faire progresser une
compétence.

Un test échoue si l'une des valeurs inventées réapparaît sur l'une des quatre
pages.

### L'habitude, nommée

Sept occurrences ne sont plus des oublis : c'est une manière de travailler.

Elle a une logique, et il vaut mieux l'énoncer que la taire. Pour voir à quoi
une page ressemblera, on la remplit ; pour qu'elle ressemble à quelque chose,
on la remplit **avec du vraisemblable**. Puis la donnée réelle arrive ailleurs,
et le remplissage reste — parce qu'il ne casse rien, ne lève aucune erreur, et
qu'aucun test ne le regarde. Il ne se voit qu'à une chose : il est trop beau
pour un compte neuf.

**La règle qui en découle**, et qui vaut pour la suite du projet : une valeur
d'attente est écrite de façon à **échouer visiblement** si elle survit. Un
`0`, un `—`, un « non mesuré » ; jamais un 85 %, jamais une durée plausible,
jamais un nom de sujet crédible. Une maquette doit avoir l'air d'une maquette.

Le corollaire est déjà appliqué : les états vides de la page d'accueil sont
écrits comme une fonctionnalité, avec leurs propres tests. Un état vide soigné
est ce qui rend le remplissage inutile.

### Ce qui reste ouvert

`revision/review.html` n'a pas été examinée. Elle est atteignable, et le motif
ne s'est encore jamais arrêté de lui-même dans ce projet.

---

## 13. `attempts_count` compte les soumissions, pas les tentatives avant réussite

**Composant :** `apps/exercises/models.py`
**Nature :** champ correct dont le nom induit en erreur
**Statut :** **ouverte** — contournée partout, non renommée

Ce compteur s'incrémente à **chaque** soumission, y compris après la réussite.
Il dit le nombre total de soumissions ; son nom annonce les tentatives.

L'écart a été supposé dans le mauvais sens par deux personnes le même jour, en
concevant le bloc « à revoir ». Employé tel quel, il aurait classé comme
difficile un exercice réussi du premier coup puis retravaillé par curiosité.

**Aucune ligne de code n'est fausse** : le champ compte exactement ce qu'il
compte. C'est la lecture qui l'était, et c'est ce qui rend ce cas plus discret
que tous les autres — un nom est une promesse, et personne ne relit une
promesse tenue.

### Ce qui est fait, et ce qui ne l'est pas

Tout code qui a besoin des tentatives avant réussite compte les **soumissions
antérieures à la réussite**, avec le motif écrit sur place. Le champ n'est plus
lu pour cet usage.

Le renommer — en `soumissions_count`, ou en lui adjoignant une propriété
`tentatives_avant_reussite` — touche une migration, un modèle, plusieurs vues
et un gabarit. **À faire après le 14 septembre.** D'ici là, la réserve est ce
qui empêche l'erreur de se refaire.

---

## 14. `@csrf_exempt` sur les points de terminaison qui dépensent — deuxième occurrence

**Composants :** `apps/quiz/views.py` (corrigé), `apps/chat/views.py` (corrigé)
**Nature :** protection CSRF retirée sur des vues qui écrivent et qui dépensent
**Statut :** **les deux occurrences sont corrigées** ; la réserve reste ouverte
comme point de vigilance

**Trois** vues portaient `@csrf_exempt` — la troisième trouvée en écrivant
cette réserve, alors qu'elle affirmait qu'il n'en restait pas :

| Vue | Ce qu'elle fait | Corrigée le |
|---|---|---|
| `quiz.views.submit_quiz` | Écrit le score, les erreurs, le compteur de quiz du compte | 31/08 |
| `chat.views.send_message` | Déclenche un appel **facturé** et décompte le quota du compte | 31/08 |
| `exercises.views.submit_code` | Écrit une soumission, met à jour la progression, attribue des XP | 31/08 |

La troisième était en outre **inutile** : le gabarit envoyait déjà l'en-tête
`X-CSRFToken`. L'exemption ne servait donc rien, et ouvrait tout.

L'exemption est particulièrement mal placée sur la seconde : sans protection
CSRF, n'importe quelle page tierce ouverte dans le navigateur de l'apprenant
pouvait **épuiser son quota à son insu**, et faire payer les appels au projet.

### Pourquoi c'est une réserve et non un simple correctif

**Trois occurrences du même geste** dans trois applications différentes, sur les
trois vues qui, précisément, ne devaient pas le porter. Le motif est
compréhensible : `@csrf_exempt` fait taire une erreur 403 pendant qu'on
développe un appel JavaScript, et il ne se rappelle plus à personne ensuite —
comme les données d'attente de la réserve 12, il ne casse rien.

**La règle qui en découle** : un point de terminaison appelé en JavaScript
reçoit le jeton CSRF, jamais l'exemption. Le jeton coûte une ligne dans le
gabarit et un en-tête dans la requête.

### Une leçon sur la vérification elle-même

Cette réserve a d'abord été écrite en annonçant deux occurrences et en
concluant qu'aucune autre ne subsistait. **La vérification a été faite après
l'affirmation, et l'a démentie** : une troisième attendait dans
`apps/exercises`.

C'est le motif du projet retourné contre sa propre documentation — annoncer un
état sans l'avoir constaté. Le paragraphe est conservé tel quel plutôt que
réécrit en silence.

### Ce qui reste à faire

Aucun autre `@csrf_exempt` ne subsiste — vérifié **après** l'avoir écrit, cette
fois, par `grep -rn "^@csrf_exempt" apps/`. La réserve est conservée pour que
la quatrième occurrence, si elle vient, soit reconnue comme telle.

---

## 15. Supprimer un compte hôte efface les réponses de tous les participants

**Composant :** `apps/quiz/models.py`, `GameRoom.host`
**Nature :** effacement en cascade au-delà des données du compte supprimé
**Statut :** **ouverte**, non corrigée à dessein

```python
host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_rooms')
```

Supprimer un compte efface ses salles ; effacer une salle efface ses
participants, ses questions et ses réponses — **y compris celles des autres
personnes**. Une partie à dix joueurs disparaît parce que son hôte a exercé son
droit à l'effacement.

### Ce que cela touche vraiment

La route de suppression de compte, ouverte le 29/08 pour le RGPD, est un chemin
d'exécution réel de cette cascade. Un apprenant qui supprime son compte détruit
donc, sans le savoir, des données d'apprentissage appartenant à d'autres — dont
les erreurs qui alimentaient leur bloc « à revoir ».

L'écran de confirmation annonce ce qui sera supprimé, et il cite déjà « la
suppression des salles de quiz que vous avez hébergées retire aussi les
réponses des autres participants ». **La conséquence est donc annoncée, ce qui
la rend loyale — pas souhaitable.**

### Pourquoi ce n'est pas corrigé

Rendre l'hôte nullable, ou basculer en `SET_NULL`, change le comportement du
jeu : une salle sans hôte doit décider qui peut la lancer, la supprimer,
l'arrêter. C'est une règle de jeu à écrire, pas un attribut à changer.

**Même arbitrage que pour l'effacement de compte, et pour la même raison** :
toucher au comportement à quelques jours du rendu, sans le temps d'en mesurer
les effets, coûte plus que la réserve.

### À faire après le 14 septembre

Passer `host` en `SET_NULL`, et décider ce qu'est une salle sans hôte —
probablement : consultable, non relançable, supprimable par n'importe quel
participant après un délai. Les parties terminées n'ont de toute façon plus
besoin d'un hôte.

---

## 16. Les séances de conversation restent ouvertes, faute de fin identifiable

**Compétence concernée :** C20 (épreuve E5) — monitorage
**Statut :** consignée, **partiellement corrigée le 04/09/2026**

Cette réserve visait la génération de quiz multijoueur. Le relevé du 4
septembre montre qu'elle désignait le mauvais coupable, et qu'elle en taisait
deux autres :

| Type de séance | Ouvertes | Total |
|---|---|---|
| `chat` | **14** | 14 |
| `quiz` | 9 | 12 |
| `quiz_multijoueur` | **0** | 6 |
| `course_generation` | 3 | 3 |

Le multijoueur, seul cité, est désormais le seul entièrement clos — la
correction de l'incident 012 y a pourvu. La génération de cours est close
depuis ce jour : une génération a une fin nette, la réponse est là.

**Restent les conversations, et c'est délibéré.** Une séance de chat n'a pas de
fin identifiable : l'apprenant ferme l'onglet, revient une heure plus tard,
reprend le fil. Poser une fin arbitraire — un délai, un changement de page —
produirait une durée mesurée qui ne mesurerait rien. Mieux vaut une séance sans
durée, et qui le dit, qu'une durée fabriquée. C'est la règle que l'incident 011
a imposée au tableau de bord, et elle vaut ici.

**Ce que cela n'affecte pas.** Aucune moyenne affichée n'inclut ces séances :
le score moyen des quiz filtre sur `end_time__isnull=False`, et le temps
d'étude est annoncé comme non mesuré. Une séance ouverte est un quiz engendré,
pas un quiz fait — la distinction est dans le code, pas seulement ici.

**Pour lever la réserve**, il faudrait décider ce qu'est la fin d'une
conversation, puis le mesurer. C'est une question de produit avant d'être une
question de code.

## 17. Seize traductions devinées par `makemessages`, inertes mais fausses

**Compétence concernée :** C17 (épreuve E4) — internationalisation
**Statut :** consignée, deux entrées corrigées

`makemessages` propose une traduction lorsqu'une chaîne nouvelle ressemble à
une chaîne connue, et marque sa proposition `#, fuzzy`. Le catalogue français
en compte seize. Plusieurs sont franchement fausses :

| Chaîne | Traduction devinée |
|---|---|
| `Compétence` | « Terminé » |
| `Description` | « Question » |
| `Version` | « Révision » |
| `Votre question` | « 5 questions » |

**Elles ne s'affichent pas.** `compilemessages` exclut les entrées `fuzzy`, et
l'application sert alors la chaîne source — qui est déjà en français pour
toutes celles-là. Le risque n'est donc pas à l'écran : il est qu'un relecteur
défige une entrée par commodité, sans lire ce qu'elle propose.

Deux entrées ont été corrigées parce qu'elles portaient un identifiant anglais,
donc une vraie perte : `Preferred Language` et `Koda Avatars` s'affichaient en
anglais dans l'interface française alors que leur traduction existait, défigée.

### Ce que cette réserve dit du procédé

Le `#, fuzzy` est une **suggestion d'outil présentée comme un résultat**. Il
occupe la place d'une traduction, il en a la forme, et seule une ligne de
métadonnée le distingue. C'est une variante de la famille B appliquée à un
outil de développement : le catalogue affiche seize traductions, il en contient
seize de moins.

### Une troisième occurrence, le jour même

Dans la même session, `makemessages` a proposé « Joueurs au maximum » pour
`Players`, deviné à partir de `Max Players`. Sans relecture, le salon d'attente
aurait affiché « Joueurs au maximum (2/10) ». Le risque n'est donc pas
théorique : **toute chaîne nouvelle qui ressemble à une chaîne existante repart
avec une traduction fausse**, et c'est la relecture — pas l'outil — qui
l'arrête.

### À faire après le 14 septembre

Relire les entrées une à une, défiger celles qui sont justes, vider les
autres. Et ajouter un test qui échoue si une entrée `fuzzy` porte un identifiant
non français — le seul cas où l'inertie coûte quelque chose.

---

## 18. Douze classes présentes dans les gabarits ne produisent aucun style

**Compétence concernée :** C17 (épreuve E4) — application web
**Statut :** consignée, non corrigée

Le relevé exhaustif des classes des gabarits, fait pour vérifier la feuille
compilée (décision 034), a montré que douze d'entre elles ne sont stylées nulle
part — ni par Tailwind, ni par un `<style>` de gabarit, ni par
`static/css/custom.css`, lequel n'est d'ailleurs chargé par aucune page.

Elles se répartissent en trois familles :

| Classes | Origine |
|---|---|
| `tab-button`, `tab-content`, `avatar-option`, `tuteur-dock`, `test-actual`, `test-result`, `test-status`, `question-scroll-container` | accroches de JavaScript — jamais destinées à styler |
| `python`, `language-python` | posées pour Prism, la coloration syntaxique |
| `prose`, `prose-invert` | greffon `@tailwindcss/typography`, **non installé** |

Seules les deux dernières sont un vrai manque : `prose` et `prose-invert` sont
écrites sur les zones de contenu généré dans l'intention d'en soigner la
typographie, et elles n'ont jamais rien fait. Le rendu actuel est donc celui
que l'on voit, pas celui qui était visé.

### Pourquoi ce n'est pas corrigé

Installer le greffon changerait l'apparence de toutes les zones de contenu
généré — cours, réponses du tuteur, énoncés — trois jours avant le rendu, sans
le temps de relire chaque page. Le rendu actuel est correct ; il est seulement
plus sobre que prévu.

### À faire après le 14 septembre

Installer `@tailwindcss/typography`, l'ajouter aux greffons de
`theme/tailwind-v3/tailwind.config.js`, reconstruire, et relire les pages de
contenu généré. Retirer les accroches JavaScript de la liste d'exceptions du
test le jour où elles porteraient un style.

---

## 19. `current_streak` est lu pour accorder un bonus, et n'est jamais écrit

**Compétence concernée :** C20 (épreuve E5) — données du suivi
**Statut :** consignée, non corrigée

Le champ `current_streak` existe sur le compte et sur `UserProgress`. Il est
**lu** dans `agent_orchestrator.py` pour calculer un bonus d'expérience :

```python
streak_bonus = min(self.user.current_streak * 2, 20)
```

**Aucun code ne l'écrit jamais.** Il vaut donc zéro pour tout le monde, et le
bonus vaut zéro pour tout le monde.

### Pourquoi cette réserve compte plus qu'il n'y paraît

Le défaut est sans conséquence visible aujourd'hui : un bonus toujours nul ne
se remarque pas. Il devient dangereux dès qu'on s'appuie sur ce champ pour
**dire** quelque chose. En composant la salutation de Koda, « trois jours
d'affilée, bravo ! » était la phrase la plus naturelle à écrire — et elle
aurait été fausse pour chaque apprenant, sur toutes les pages, avec l'air
d'être la marque d'attention la plus soignée du produit.

C'est la famille B sous sa forme la plus coûteuse : **un compteur qui a l'air
d'un compteur**. Un test interdit désormais son emploi dans la salutation.

### À faire après le 14 septembre

Soit tenir la série — la mettre à jour à chaque séance close, avec une règle
explicite sur ce que « un jour » veut dire pour quelqu'un qui travaille à
cheval sur minuit — soit retirer le champ et le bonus qui en dépend. La
troisième voie, le laisser tel quel, est celle qui a failli produire un
mensonge.

---

## 20. Le périmètre de S6 épingle PyTorch 2.13 dans un corpus qui ne se périme pas

**Compétence concernée :** C1 (épreuve E1) — collecte ; C21 (E5)
**Statut :** consignée, assumée

`pytorch.org/docs/stable/` ne sert pas de documentation : c'est une page de
redirection en JavaScript, **quarante-cinq caractères de texte**, qui renvoie
vers une URL versionnée. La collecte vise donc `docs.pytorch.org/docs/2.13/`.

Le corpus, lui, ne porte aucune notion de version. Les fragments collectés
diront « PyTorch » sans dire « 2.13 », et **rien ne signalera leur péremption**
quand la bibliothèque évoluera. Un apprenant recevra en 2027 une signature de
fonction exacte pour 2026.

### Pourquoi ce n'est pas corrigé

Versionner le corpus demande de décider ce qu'on fait des fragments périmés :
les supprimer, les marquer, les laisser en les datant. C'est une question de
conception, pas un champ à ajouter — et elle vaut pour les six cibles, pas pour
la seule qui rend le problème visible.

### À faire après le 14 septembre

Porter la version de la source dans les métadonnées du fragment, au même titre
que la licence et l'attribution qui y voyagent déjà. Puis décider d'une règle
de péremption. La date de collecte, elle, est déjà enregistrée : c'est un point
de départ.

---

## 21. La montée de niveau et l'enrichissement par le parcours ne sont pas livrés

**Compétence concernée :** C17 (épreuve E4) — application web
**Statut :** consignée, non livrée, et le modèle est prêt à les recevoir

Le chantier des cours prévoyait six points. **Les quatre premiers sont livrés**
— modèle de données, page de cours, fiche, onglet à trois entrées. Les deux
derniers ne le sont pas.

### La montée de niveau

Le référentiel définit trois niveaux : imiter, adapter, transposer. Un cours de
niveau 2 **ne doit pas reformuler le niveau 1 en plus long** — ce qu'un modèle
produira spontanément si on lui demande « la version niveau 2 ».

Deux moyens de le contraindre, et ils vont ensemble : l'invite, qui dit que le
niveau 2 traite *quand ça casse et quels choix se posent* plutôt que *ce que
c'est* ; et **la mesure du recouvrement** avec le niveau précédent, qui refuse
la production si elle recopie.

**Sans la mesure, l'invite ne tient pas.** Ce projet a documenté assez de cas où
une intention non vérifiée ne produisait rien — c'est la famille B en entier. La
fonctionnalité n'est donc pas livrée à moitié : elle n'est pas livrée.

Le seuil ne sera pas fixé au jugé. Même méthode que pour le seuil de latence
(décision 024) : engendrer quelques niveaux 2, relever leur recouvrement réel
avec le niveau 1, et fixer le seuil sur ces valeurs.

### L'enrichissement déclenché par le parcours

Une erreur commise ailleurs sur une notion devrait faire apparaître une section
dans la fiche. **Le modèle le prévoit** : `AjoutDeFiche.origine` porte déjà la
valeur `parcours`, la règle de quota est tranchée et implémentée — cet ajout ne
décompte rien et l'affiche —, et la fiche sait rendre la mention « proposé par
votre parcours, offert ».

Ce qui manque est le déclencheur : le point du parcours qui décide qu'une erreur
mérite un enrichissement, et à quelle fréquence. C'est une règle pédagogique
avant d'être du code.

### Pourquoi maintenant

Deux jours avant le rendu des livrables écrits. Les points 1 à 4 forment un
ensemble cohérent et démontrable ; le point 5 exige une campagne de mesure avant
même d'être écrit. Livrer une montée de niveau qui reformule serait pire que ne
pas la livrer : elle donnerait l'illusion d'une progression.

### À faire après le 14 septembre

Mesurer le recouvrement, fixer le seuil, écrire l'invite de niveau, brancher le
déclencheur du parcours. Le modèle de données n'aura pas à changer.

---

## 22. Deux vues de génération d'exercices, identiques aux deux tiers

**Compétence concernée :** C17 (épreuve E4) — application web
**Statut :** consignée, **non corrigée délibérément**

`generate_exercise` et `generate_exercise_from_course`, dans
`apps/exercises/views.py`, comptent 265 et 239 lignes utiles pour une
**similarité de 67 %** : 116 lignes identiques de plus de trente caractères,
mesurées ligne à ligne.

Ce qui est dupliqué n'est pas de la plomberie : **l'invite envoyée au modèle
l'est intégralement**, y compris ses consignes les plus fines — « les tests
doivent appeler la MÊME fonction que celle définie dans la solution », « les
valeurs attendues doivent être le vrai résultat de votre fonction ».

### La conséquence concrète

Améliorer l'invite dans l'une laisse l'autre en arrière, **et rien ne le
signale** : les deux vues continuent de fonctionner, en produisant des
exercices de qualité différente selon le chemin emprunté. Une troisième copie
de la même consigne vit d'ailleurs dans `apps/agents/agent_coach.py`.

### Pourquoi ce n'est pas corrigé

Le cahier des charges l'interdit explicitement : « Aucun refactoring pour la
propreté », et « ne pas casser ce qui marche ». Fondre six cents lignes de code
éprouvé à deux jours du rendu, sur le chemin qui produit les exercices —
c'est-à-dire une preuve d'évaluation — échangerait un défaut connu et sans
effet visible contre un risque inconnu.

### À faire après le 14 septembre

Sortir l'invite dans `apps/agents/prompts/`, comme les quatre autres, et la
charger par `load_prompt`. C'est le geste qui rapporte le plus : il supprime
les trois copies d'un coup, sans toucher à la logique des vues.

---

## 23. Les médias sont servis par Django, pas par un serveur web

**Compétence concernée :** C13 (épreuve E3) — livraison et exécution
**Statut :** consignée, **arbitrage assumé**

Les photos de profil déposées par les apprenants sont servies par la vue
`serve` de Django, activée hors `DEBUG` dans `eduai_project/urls.py`. La
documentation de Django déconseille explicitement cette vue en production : elle
n'est ni optimisée ni durcie, et occupe un fil du serveur d'application le temps
de lire le fichier.

### Pourquoi elle est là quand même

L'alternative est un serveur web devant l'application, ou un stockage objet
externe. Les deux ajoutent une pièce à déployer, à configurer et à surveiller,
pour un volume qui se compte en dizaines d'images de profil.

Sans elle, la fonction ne marche pas du tout : jusqu'au 02/09/2026, `/media/`
n'était routé qu'en développement, et toute photo enregistrée rendait 404 en
production. Entre une fonction absente et une fonction servie modestement, le
projet retient la seconde et l'écrit.

### Ce qu'il faudrait faire pour lever la réserve

Servir `/media/` depuis le proxy de l'hébergeur, ou déposer les fichiers sur un
stockage objet et n'en garder que l'URL en base. Le second geste supprime aussi
le besoin de volume persistant.

---

## 24. L'image déployée peut être antérieure au correctif de la collection

**Composant :** `service_ia/`, image `eduai/service-ia`
**Nature :** écart possible entre le code du dépôt et ce qui tourne

Le conteneur `eduai_service_ia` du poste tourne l'image `eduai/service-ia:1.0.0`,
**construite le 29/08/2026 à 19 h 13**. Le correctif qui branche la recherche
documentaire sur la bonne collection — commit `aed93fe`, incident 006 — est de
**21 h 11 le même jour**, deux heures plus tard.

L'image porte donc encore le nom de collection écrit en dur :

```
$ docker run --rm --entrypoint sh eduai/service-ia:1.0.0 \
    -c "grep -n 'eduai_knowledge_base' /app/service_ia/main.py"
451:        "collection": "eduai_knowledge_base",
```

**Conséquence sur le poste, constatée :** `/ai/recherche` y interroge
`eduai_knowledge_base` — **387 fragments**, les supports de formation — et non
`eduai_corpus_documentaire`, qui en porte **24 004**. Le tuteur cherche dans
1,6 % du corpus, et répond quand même : rien n'échoue, la recherche rend cinq
fragments, et seule la sonde de santé trahit le nom de la collection.

**Ce qui n'est pas établi : l'état de l'hébergeur.** L'URL publique n'est pas
dans le dépôt, et la vérification n'a pas pu être faite. Si le déploiement
n'a pas été rejoué depuis le 29/08 au soir, la production est dans le même état.

**Le contrôle tient en une requête**, et il ne demande aucun secret :

```bash
curl -s https://<service-ia>/ai/sante | grep -o '"collection":"[^"]*"'
```

La sonde répond en JSON compact, sur une seule ligne : un `grep -A3` y rendrait
toute la charge utile. L'extraction du seul nom de collection est ce qui rend le
contrôle lisible d'un coup d'œil.

- `"collection": "eduai_corpus_documentaire"` → la production est à jour ;
- `"collection": "eduai_knowledge_base"` → **elle est antérieure au correctif**,
  et il faut republier l'image avant toute démonstration.

**Ce que cette réserve apprend, indépendamment de sa réponse.** Le correctif de
l'incident 006 est dans le dépôt, il est testé, et la matrice de traçabilité le
compte comme acquis. Il ne l'est que sur le code. **Un correctif n'est acquis
qu'une fois déployé et constaté sur le système en marche** — et le seul
contrôle qui l'aurait montré, la sonde de santé, existe et n'a pas été relu
depuis le 29/08.
