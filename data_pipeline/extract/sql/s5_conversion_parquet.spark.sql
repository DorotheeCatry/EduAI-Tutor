/*
 * Conversion du dump XML Stack Exchange en table colonne partitionnée.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage Spark SQL
 * Compétence visée : C4 (épreuve E1) — minimisation des données personnelles
 *
 * OBJECTIF DE COLLECTE
 * Transformer un fichier XML monolithique de 123 Mio (dump Data Science, 78 926
 * posts) — ou de 22 Gio (dump Stack Overflow) — en Parquet partitionné, lisible
 * par requête sans relire l'intégralité du fichier.
 *
 * CHOIX DE SÉLECTION
 * La vue `posts_brut` expose une ligne de texte par ligne du fichier. Les dumps
 * Stack Exchange écrivent exactement un élément `<row .../>` par ligne, ce qui
 * permet de traiter le XML comme une source ligne à ligne : chaque ligne est
 * découpable indépendamment, donc parallélisable sans état partagé. Un analyseur
 * XML global, lui, sérialiserait la lecture sur un seul flux.
 *
 * Les attributs sont extraits par `xpath_string`, fonction native de Spark SQL.
 * Aucune bibliothèque XML externe n'est donc nécessaire : pas de JAR à résoudre
 * au démarrage, et le traitement reste identique sur les deux volumes.
 *
 * CHOIX DE FILTRAGE — minimisation (C4)
 * Quatre attributs présents dans Posts.xml ne sont volontairement PAS extraits :
 *
 *     OwnerUserId            78 448 occurrences   identifiant persistant
 *     LastEditorUserId       28 401 occurrences   identifiant persistant
 *     OwnerDisplayName          635 occurrences   nom d'affichage en clair
 *     LastEditorDisplayName     184 occurrences   nom d'affichage en clair
 *
 * Comptages relevés sur le dump Data Science du 07/04/2024. Les écarter ici,
 * à la projection, et non après chargement : une donnée non extraite n'a besoin
 * ni de durée de conservation ni de procédure d'effacement. Même raisonnement
 * que pour l'objet `owner` de l'API Stack Exchange en S1.
 *
 * L'attribution exigée par CC BY-SA est assurée par l'URL reconstruite depuis
 * `Id`, qui pointe vers la page où Stack Exchange crédite lui-même l'auteur.
 *
 * Le fichier Users.xml du dump n'est jamais ouvert : il ne contient que des
 * données personnelles (nom d'affichage, site web, localisation, biographie).
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Partitionnement par `annee` à l'écriture : les requêtes aval filtrant sur
 *   une période ne lisent que les répertoires concernés (élagage de partitions).
 * - Typage explicite à la conversion plutôt qu'inférence : l'inférence impose
 *   une passe de lecture supplémentaire sur l'intégralité du dump.
 * - `WHERE` appliqué avant les appels `xpath_string` dans le plan logique :
 *   les lignes d'en-tête et de pied ne sont pas analysées.
 */

SELECT
    CAST(xpath_string(ligne, '/row/@Id')               AS BIGINT)    AS id_post,
    CAST(xpath_string(ligne, '/row/@PostTypeId')       AS INT)       AS type_post,
    CAST(NULLIF(xpath_string(ligne, '/row/@ParentId'), '')
                                                       AS BIGINT)    AS id_parent,
    CAST(NULLIF(xpath_string(ligne, '/row/@AcceptedAnswerId'), '')
                                                       AS BIGINT)    AS id_reponse_acceptee,
    NULLIF(xpath_string(ligne, '/row/@Title'), '')                   AS titre,
    xpath_string(ligne, '/row/@Body')                                AS corps,
    NULLIF(xpath_string(ligne, '/row/@Tags'), '')                    AS mots_cles_bruts,
    CAST(NULLIF(xpath_string(ligne, '/row/@Score'), '')      AS INT)  AS score,
    CAST(NULLIF(xpath_string(ligne, '/row/@ViewCount'), '')  AS INT)  AS nombre_vues,
    CAST(NULLIF(xpath_string(ligne, '/row/@AnswerCount'), '')AS INT)  AS nombre_reponses,
    CAST(xpath_string(ligne, '/row/@CreationDate')  AS TIMESTAMP)     AS date_creation,
    NULLIF(xpath_string(ligne, '/row/@ContentLicense'), '')           AS licence,
    -- Colonne de partitionnement. Calculée ici pour que l'écriture n'ait pas à
    -- réévaluer l'horodatage complet ligne par ligne.
    CAST(year(CAST(xpath_string(ligne, '/row/@CreationDate') AS TIMESTAMP))
                                                       AS INT)       AS annee
FROM posts_brut
WHERE trim(ligne) LIKE '<row %'
