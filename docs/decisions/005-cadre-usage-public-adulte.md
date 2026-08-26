# 005 — Cadre d'usage : public adulte exclusivement

**Date :** 26/08/2026
**Statut :** adoptée — remplace l'hypothèse retenue en 001 et 004
**Compétences concernées :** C4 (E1), C13 (E3), C17 (E4)

## Contexte

Les documents antérieurs du dépôt posaient que « le public visé peut inclure
des mineurs ». Cette hypothèse conditionnait le volet RGPD de C4 et les
exigences de rédaction des interfaces.

## Décision

EduAI Tutor est une **plateforme de formation professionnelle au développement,
destinée à un public adulte exclusivement**. Aucun mineur n'est concerné.

## Conséquences

Ce cadre **écarte** deux obligations, et deux seulement :

- le régime de consentement de l'article 8 du RGPD, qui impose l'autorisation
  du titulaire de l'autorité parentale en dessous de 15 ans en France ;
- l'exigence de l'article 12.1 d'une information rédigée en des termes qu'un
  enfant peut comprendre.

Il **ne dispense d'aucune autre obligation**. Minimisation, durée de
conservation, droit d'accès, droit d'effacement et sécurité des traitements
restent entièrement applicables. Le cadre adulte est un rétrécissement du
périmètre, pas un allègement du RGPD — la confusion serait coûteuse à l'oral.

Il ne modifie ni le MCD ni le MLD de `eduai_data`, qui ne contiennent aucune
donnée à caractère personnel par construction.

## Documents portant encore l'hypothèse périmée

`docs/cahier-des-charges.md` (§ Sécurité, RGPD, accessibilité), `docs/etat-des-lieux.md`,
`docs/decisions/001` et `docs/decisions/004`.

Les deux entrées du journal de décisions ne sont pas corrigées : une entrée
consigne ce qui a été décidé à sa date, la présente entrée la remplace. Les
deux autres documents, qui énoncent la règle en vigueur, sont à mettre à jour.

## Point non résolu par cette décision

L'audit de `docs/etat-des-lieux.md` relève que l'application enregistre
**l'adresse IP de chaque soumission de code** (`ExerciseSubmission.ip_address`),
sans durée de conservation ni route d'effacement. Une adresse IP est une donnée
à caractère personnel quel que soit l'âge de la personne : le cadre adulte ne
règle pas ce point, qui reste à traiter pour C4 lors de la bascule de
`eduai_app` vers PostgreSQL.
