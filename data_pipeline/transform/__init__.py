"""
Couche de transformation du pipeline de données.

Compétence visée : C3 (épreuve E1) — nettoyage et agrégation des données

Cette couche est distincte de l'extraction (C1) et du chargement (C4). Elle lit
les sorties brutes des cinq extracteurs, les rend homogènes et comparables,
puis écrit un corpus unique que le chargeur versera dans `eduai_data`.

Choix : trois modules distincts plutôt qu'une fonction de nettoyage unique.
Motivation : le référentiel évalue trois opérations nommément — déduplication,
normalisation des dates, homogénéisation des formats. Les fondre en une seule
passe « propre » rendrait chacune invérifiable, alors qu'elles reposent sur des
règles différentes et échouent pour des raisons différentes.

Ordre d'application, imposé par `transformer.py` :

    1. normalisation_dates     — un seul format temporel avant toute comparaison
    2. homogeneisation_formats — champs, licences et mots-clés canoniques
    3. deduplication           — en dernier, sur des documents déjà canoniques

La déduplication vient en dernier délibérément : elle compare des contenus, et
comparer des contenus non encore normalisés laisserait passer des doublons qui
ne diffèrent que par des espaces ou un format de date.
"""
