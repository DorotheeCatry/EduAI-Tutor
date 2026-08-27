/*
 * Paires « échec puis correction » issues des soumissions d'exercices.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage SQL
 * Compétence visée : C4 (épreuve E1) — minimisation des données personnelles
 *
 * Base interrogée : eduai_app (application Django), en lecture seule.
 * Base de destination : eduai_data, via le contrat commun des extracteurs.
 *
 * OBJECTIF DE COLLECTE
 * Constituer des documents de la forme « voici du code qui échoue, voici
 * l'erreur produite, voici le code qui a fonctionné ensuite ». C'est le seul
 * artefact que les productions d'apprenants apportent et qu'aucune source
 * externe ne fournit : Stack Overflow documente des questions, pas la
 * trajectoire de correction d'un débutant sur un exercice donné.
 *
 * CHOIX DE SÉLECTION
 * Deux soumissions du MÊME apprenant sur le MÊME exercice : la soumission en
 * échec, et la première réussite qui lui succède. Le rapprochement se fait
 * donc nécessairement par `user_id`.
 *
 * CHOIX DE FILTRAGE — minimisation (C4)
 * `user_id` sert à la jointure et n'est PAS projeté. C'est le point central de
 * cette requête : le lien entre deux soumissions d'un même apprenant est
 * nécessaire à la COLLECTE, il ne l'est pas au RÉSULTAT. Une fois la paire
 * constituée, le document se suffit à lui-même — il porte une erreur et sa
 * correction, pas une personne.
 *
 * Aucun identifiant pseudonyme n'est donc émis, ce que le paragraphe 5 du
 * document RGPD n'autorisait qu'en cas de nécessité. Ne sont projetés ni
 * `user_id`, ni `ip_address`, ni aucune colonne de `users_kodauser` — cette
 * table n'est même pas jointe.
 *
 * `ip_address` existe dans la table source, sans finalité établie. Elle est
 * appelée à disparaître de eduai_app (voir docs/decisions/005) ; en attendant,
 * cette requête ne la lit pas.
 *
 * CHOIX DE JOINTURE
 * Jointure latérale et non auto-jointure simple : pour chaque échec, on veut
 * LA PREMIÈRE réussite postérieure, pas toutes les réussites. Un `DISTINCT ON`
 * global sur (apprenant, exercice) donnerait la première réussite absolue et
 * perdrait les paires d'un apprenant qui réussit, régresse, puis réussit à
 * nouveau. La latérale corrèle correctement chaque échec à sa propre suite.
 *
 * La jointure sur `exercises_exercise` apporte l'énoncé et le thème : sans eux
 * un extrait de code corrigé n'est pas interprétable hors contexte.
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Fenêtre temporelle appliquée dans la sous-requête `echecs`, donc avant la
 *   latérale : celle-ci n'est évaluée que pour les échecs déjà retenus.
 * - `LIMIT 1` dans la latérale : le parcours s'arrête à la première ligne
 *   correspondante au lieu de matérialiser toutes les réussites.
 * - L'index `exercises_exercisesubmission_user_id_589ffaf0`, créé par Django,
 *   sert la corrélation. Aucun index n'est ajouté à eduai_app : son schéma
 *   appartient aux migrations Django, pas au pipeline (voir décision 006).
 * - Paramètre passé par psycopg (`%(fenetre_jours)s`) et non interpolé :
 *   la requête reste exécutable telle quelle et l'injection est exclue.
 */

WITH echecs AS (
    SELECT
        s.id,
        s.exercise_id,
        s.user_id,          -- utilisé pour la jointure, jamais projeté
        s.submitted_code,
        s.error_message,
        s.execution_output,
        s.status,
        s.submitted_at
    FROM exercises_exercisesubmission s
    WHERE s.status IN ('failed', 'error', 'timeout')
      AND s.submitted_at >= now() - make_interval(days => %(fenetre_jours)s)
      AND length(btrim(s.submitted_code)) > 0
)
SELECT
    e.id                                    AS id_echec,
    r.id                                    AS id_reussite,
    ex.title                                AS titre_exercice,
    ex.topic                                AS theme,
    ex.difficulty                           AS difficulte,
    ex.description                          AS enonce,
    e.submitted_code                        AS code_en_echec,
    e.error_message                         AS message_erreur,
    e.execution_output                      AS sortie_execution,
    e.status                                AS statut_echec,
    r.submitted_code                        AS code_corrige,
    e.submitted_at                          AS date_echec,
    r.submitted_at                          AS date_correction,
    round(
        EXTRACT(EPOCH FROM (r.submitted_at - e.submitted_at)) / 60.0
    )::int                                  AS minutes_jusqu_correction,
    -- Signal de progression au niveau de l'exercice, non de la personne :
    -- ces compteurs sont des agrégats déjà présents dans la table exercice.
    ex.attempts_count                       AS tentatives_exercice,
    ex.success_count                        AS reussites_exercice
FROM echecs e
JOIN LATERAL (
    SELECT s.id, s.submitted_code, s.submitted_at
    FROM exercises_exercisesubmission s
    WHERE s.user_id = e.user_id
      AND s.exercise_id = e.exercise_id
      AND s.status = 'success'
      AND s.submitted_at > e.submitted_at
    ORDER BY s.submitted_at
    LIMIT 1
) r ON true
JOIN exercises_exercise ex ON ex.id = e.exercise_id
ORDER BY e.submitted_at DESC
