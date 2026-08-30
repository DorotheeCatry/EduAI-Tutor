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

## 7. La latence d'embarquement en production, non arbitrée

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
| `POST /ai/recherche`, bout en bout | **3 s** | *non mesuré* |
| Latence comptée par le service | **3,7 s** | *non mesuré* |
| Mémoire du serveur d'embarquement | — | **800 Mo** (estimation initiale : 2 Go) |

Relevés du 30/08/2026. Le modèle est environ **trois fois plus lent** qu'en
local.

### Ce qui n'est pas mesuré, et pourquoi

Le temps de bout en bout d'un `POST /ai/recherche` en production. Il exige le
corpus sur le volume, qui n'est pas encore transféré. **Il sera mesuré, pas
supposé** : `docker/verifier-deploiement.sh` chronomètre désormais cette
requête et affiche, à côté, la latence que le service s'attribue — l'écart
entre les deux distingue le modèle du transport.

La mémoire, elle, n'est plus un sujet : 800 Mo mesurés contre 2 Go estimés.
C'est la latence qui coûte, pas l'empreinte.

### L'arbitrage, si la mesure est de l'ordre de quarante secondes

Trois options, aucune tranchée à ce jour :

| Option | Ce qu'elle donne | Ce qu'elle coûte |
|---|---|---|
| **Préchauffage** | Un modèle déjà chargé évite le coût du premier appel | Ne réduit pas le coût d'inférence lui-même ; ne sauve que si l'essentiel des 13,6 s est du chargement |
| **Modèle d'embarquement plus léger** | Inférence plus rapide sans GPU | **Impose de réindexer les 21 189 fragments** : les vecteurs d'un autre modèle n'ont aucun rapport avec ceux du corpus. Plus de dix-sept heures, et le corpus déployé devient inutilisable entre-temps |
| **Démonstration du RAG en local**, le reste déployé | Une recherche à 3 s devant le jury | Affaiblit la démonstration : ce qui est montré n'est plus ce qui est déployé, et il faut le dire |

Le choix dépend d'une mesure qui n'existe pas encore. Le faire maintenant
serait supposer.

**Ce qui ne change pas quelle que soit l'issue** : le déploiement lui-même, les
deux API, l'application et le monitorage ne dépendent pas de cette latence. Ce
qui est en jeu est la démonstrabilité d'une fonction, pas la validité du
déploiement.
