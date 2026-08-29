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
