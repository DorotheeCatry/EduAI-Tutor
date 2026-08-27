/*
 * Erreurs conceptuelles relevées par l'agent Watcher.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage SQL
 * Compétence visée : C4 (épreuve E1) — minimisation des données personnelles
 *
 * Base interrogée : eduai_app (application Django), en lecture seule.
 *
 * OBJECTIF DE COLLECTE
 * Recueillir les méprises conceptuelles que les agents ont détectées pendant
 * les sessions : la question posée, la réponse erronée de l'apprenant, la
 * réponse correcte. Là où la requête des soumissions porte sur du code, celle-ci
 * porte sur la compréhension — deux natures d'erreur distinctes, deux documents
 * distincts dans le corpus.
 *
 * CHOIX DE SÉLECTION
 * Le triplet question / réponse donnée / réponse correcte, avec le thème et le
 * type de méprise. Ces quatre champs suffisent à constituer un document
 * autoportant, exploitable par le tuteur sans autre contexte.
 *
 * CHOIX DE FILTRAGE — minimisation (C4)
 * `user_id` n'est ni projeté ni utilisé. Aucune colonne de `users_kodauser`
 * n'est lue, et la table n'est pas jointe.
 *
 * Les lignes dont la question ou la réponse correcte est vide sont écartées :
 * un document sans énoncé ni correction n'apprend rien et pollue l'index
 * sémantique. Le filtrage est fait ici plutôt qu'en Python — la base sait
 * compter des caractères, et écarter une ligne au plus tôt évite de la
 * transporter.
 *
 * CHOIX DE JOINTURE
 * Aucune, délibérément. La table se suffit : elle porte déjà l'énoncé, la
 * réponse et la correction. Joindre `users_kodauser` pour obtenir un nom
 * d'apprenant introduirait précisément la donnée personnelle que ce pipeline
 * s'interdit de collecter. L'absence de jointure est ici une décision de
 * minimisation, pas une simplification.
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Fenêtre temporelle en premier prédicat : elle est la plus sélective, et
 *   `timestamp` porte l'ordre naturel d'insertion de la table.
 * - `btrim` et `length` évalués côté base : le tri des lignes vides ne remonte
 *   pas jusqu'au client.
 * - Paramètre passé par psycopg (`%(fenetre_jours)s`), jamais interpolé.
 * - Aucun index ajouté à eduai_app : son schéma appartient aux migrations
 *   Django (voir décision 006). Le volume attendu de cette table reste
 *   modeste ; un balayage séquentiel y est le plan raisonnable.
 */

SELECT
    m.id                        AS id_erreur,
    m.topic                     AS theme,
    m.mistake_type              AS type_erreur,
    m.question                  AS question,
    m.user_answer               AS reponse_donnee,
    m.correct_answer            AS reponse_correcte,
    m.reviewed                  AS revue,
    m.timestamp                 AS date_erreur
FROM agents_usermistake m
WHERE m.timestamp >= now() - make_interval(days => %(fenetre_jours)s)
  AND length(btrim(m.question)) > 0
  AND length(btrim(m.correct_answer)) > 0
ORDER BY m.timestamp DESC
