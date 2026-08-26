# 003 — Couche d'extraction : contrat commun et choix de la source API REST

**Date :** 26/08/2026
**Statut :** adoptée
**Compétences concernées :** C1 (E1), C3 (E1), C4 (E1)

## Contexte

Le référentiel exige l'extraction d'au moins cinq **types** de sources distincts
(service web, scraping, fichier de données, base de données, système big data).
Chaque script doit exposer les cinq étapes du critère C1 : point de lancement,
initialisation des dépendances et connexions, règles logiques de traitement,
gestion des erreurs, sauvegarde des résultats.

Deux questions se posaient avant d'écrire le premier extracteur : quelle
structure commune donner aux cinq scripts, et quelle source retenir pour le
type « service web ».

## Options envisagées

1. **Cinq scripts entièrement indépendants.** Lisibilité maximale de la
   couverture des cinq types, mais rien ne garantit que les cinq satisfassent
   le critère C1 de la même manière, ni qu'ils produisent des données
   agrégeables sans réconciliation manuelle en phase de transformation.
2. **Un extracteur générique paramétré par source.** Code plus court, mais le
   fait qu'il existe bien cinq types distincts disparaît derrière
   l'abstraction — exactement ce que le jury doit pouvoir constater d'un coup
   d'œil.
3. **Une classe de base minimale plus un fichier par source.**

## Décision

Option 3. `data_pipeline/extract/base_extractor.py` impose la structure en cinq
étapes et un contrat de données commun (`Enregistrement`), et chaque type de
source garde son fichier nommé explicitement (`s1_api_stackoverflow.py`, etc.).
L'abstraction s'arrête à la structure : la logique d'extraction, les contraintes
de licence et le traitement d'erreurs propres à chaque source restent visibles
dans leur fichier.

Deux choix associés :

- **Sortie en JSON Lines** plutôt qu'en CSV, parce que les cinq sources
  produisent des enregistrements de structures hétérogènes. L'homogénéisation
  relève de la transformation (C3) et n'a pas à être imposée à l'extraction.
- **Métadonnées de provenance sur chaque enregistrement** (source, type,
  licence, URL, date d'extraction). Exigé par la traçabilité C1 et le RGPD
  (C4) ; sans elles, un corpus RAG ne peut pas citer ses sources.

Pour la source de type « service web », l'API Stack Exchange (Stack Overflow)
est retenue. Le corpus existant couvre déjà la théorie ; ce qui lui manque, ce
sont les erreurs réelles et les cas limites rencontrés par des apprenants. La
valeur ajoutée est donc complémentaire du corpus, pas redondante. Le contenu
est sous licence CC BY-SA 4.0 : l'attribution est conservée dans chaque
enregistrement via `source_url` et `licence`. Le contenu est en anglais, ce qui
est assumé — c'est la langue de la source.

## Conséquences

- Le quota gratuit de l'API (300 requêtes/jour sans clé) impose une pagination
  bornée et une pause explicite entre appels. L'extraction complète consomme
  seize requêtes pour environ 1 350 enregistrements.
- L'API ne renvoie ni le corps des questions ni les réponses sans filtre
  personnalisé. La commande de régénération du filtre est documentée en
  en-tête du script : un identifiant de filtre peut être invalidé par le
  fournisseur, et l'extracteur produirait alors zéro enregistrement sans
  erreur apparente.
- Les sorties d'extraction sont exclues du dépôt (`data_pipeline/data/`) :
  elles sont reproductibles en relançant les scripts, et le dépôt ne doit pas
  accueillir de dumps volumineux.
