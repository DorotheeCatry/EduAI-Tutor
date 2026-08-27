/*
 * Métriques de volumétrie du corpus big data.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage Spark SQL
 * Compétence visée : C20 (épreuve E5) — mesure et suivi d'un traitement
 *
 * OBJECTIF DE COLLECTE
 * Produire le décompte par partition qui sert de preuve chiffrée à l'oral :
 * volumétrie traitée, répartition dans le temps, part réellement retenue après
 * filtrage. C'est cette table, comparée entre le dump Data Science et celui de
 * Stack Overflow, qui justifie le recours à un moteur distribué plutôt qu'à un
 * script Python séquentiel.
 *
 * CHOIX DE SÉLECTION
 * Agrégation par année, c'est-à-dire par partition physique. Le décompte est
 * donc lisible comme une carte du partitionnement lui-même : une partition
 * anormalement volumineuse signale un découpage à revoir.
 *
 * CHOIX DE FILTRAGE
 * Aucun. La requête décrit la table entière, y compris les lignes que la
 * sélection écarte — c'est précisément l'écart entre les deux qui est informatif.
 *
 * OPTIMISATIONS APPLIQUÉES
 * - `count(*)` par colonne de partitionnement : Spark répond depuis les
 *   métadonnées Parquet sans décompresser les données.
 * - `count_if` plutôt que des sous-requêtes corrélées : une seule passe.
 */

SELECT
    annee,
    count(*)                                              AS posts_total,
    count_if(type_post = 1)                               AS questions,
    count_if(type_post = 2)                               AS reponses,
    count_if(type_post = 1 AND id_reponse_acceptee IS NOT NULL)
                                                          AS questions_resolues,
    round(avg(CASE WHEN type_post = 1 THEN score END), 2) AS score_moyen_question,
    max(length(corps))                                    AS taille_corps_max
FROM posts
GROUP BY annee
ORDER BY annee
