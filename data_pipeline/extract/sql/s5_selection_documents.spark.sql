/*
 * Sélection des documents pédagogiques du corpus big data.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage Spark SQL
 * Compétence visée : C1 (épreuve E1) — règles logiques de traitement
 *
 * OBJECTIF DE COLLECTE
 * Constituer, à partir de la table Parquet partitionnée, des documents
 * exploitables par le RAG : une question et sa réponse acceptée réunies en un
 * seul enregistrement. Une question sans réponse n'apporte rien à un tuteur ;
 * une réponse sans sa question perd son contexte.
 *
 * CHOIX DE JOINTURE
 * Auto-jointure de la table sur elle-même : `q` porte les questions
 * (type_post = 1), `r` la réponse que l'auteur de la question a acceptée
 * (`q.id_reponse_acceptee = r.id_post`). Jointure interne et non externe :
 * le critère de qualité retenu est précisément la présence d'une réponse
 * validée par le demandeur, signal de fiabilité plus sûr que le score seul,
 * qui récompense aussi la popularité du sujet.
 *
 * CHOIX DE FILTRAGE
 * - `q.annee >= :annee_min` : borne de fraîcheur. Une réponse technique de plus
 *   de dix ans décrit souvent une API disparue. Ce prédicat porte sur la
 *   colonne de partitionnement, donc il élague avant toute lecture.
 * - `q.score >= :score_min` : écarte le bruit. Le score est le solde des votes
 *   de la communauté, pas une métrique inventée pour l'occasion.
 * - `length(r.corps) >= :taille_min` : une réponse de deux lignes (« voir la
 *   documentation ») ne nourrit pas un index sémantique.
 * - Aucun filtre sur l'auteur : la colonne n'existe pas, elle n'a pas été
 *   extraite à la conversion (voir s5_conversion_parquet.spark.sql).
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Élagage de partitions par `annee`, colonne de partitionnement physique.
 * - Élagage de colonnes : seules les colonnes projetées sont lues sur le
 *   disque, propriété du format Parquet que le format XML ne permet pas.
 * - Refoulement des prédicats `score` et `type_post` dans le lecteur Parquet,
 *   évalués sur les statistiques de groupe de lignes avant décompression.
 * - Aucun indice de jointure forcé : le plan est laissé à l'exécution
 *   adaptative (`spark.sql.adaptive.enabled`), qui choisit la diffusion ou le
 *   remaniement selon la taille réelle des côtés. Forcer une diffusion
 *   fonctionnerait sur le dump Data Science et saturerait la mémoire du pilote
 *   sur celui de Stack Overflow — or les deux dumps passent par ce fichier.
 *
 * PARAMÈTRES
 * Passés par `spark.sql(..., args=...)` et non par interpolation de chaîne :
 * la requête reste un fichier exécutable tel quel et l'injection est exclue.
 */

SELECT
    q.id_post                                   AS id_question,
    q.titre                                     AS titre,
    q.corps                                     AS corps_question,
    r.corps                                     AS corps_reponse,
    q.mots_cles_bruts                           AS mots_cles_bruts,
    q.score                                     AS score_question,
    r.score                                     AS score_reponse,
    q.nombre_vues                               AS nombre_vues,
    q.nombre_reponses                           AS nombre_reponses,
    q.date_creation                             AS date_creation,
    q.annee                                     AS annee,
    -- La licence est portée par l'enregistrement : le corpus mêle des posts
    -- sous CC BY-SA 3.0 et 4.0 selon leur date de publication.
    coalesce(q.licence, 'CC BY-SA 4.0')         AS licence
FROM posts q
JOIN posts r
  ON r.id_post = q.id_reponse_acceptee
 AND r.type_post = 2
WHERE q.type_post = 1
  AND q.annee >= :annee_min
  AND q.score >= :score_min
  AND q.titre IS NOT NULL
  AND q.corps IS NOT NULL
  AND length(r.corps) >= :taille_min
ORDER BY q.score DESC, q.id_post
