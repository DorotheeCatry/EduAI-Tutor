/*
 * Création des bases de l'instance PostgreSQL.
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * Objectif : une seule instance, deux bases distinctes.
 *   - eduai_data : jeu de données collecté par le pipeline (C4)
 *   - eduai_app  : données de l'application Django (C17)
 *
 * Choix : deux bases plutôt qu'un schéma unique ou deux instances.
 * Motivation : leurs cycles de vie diffèrent. Le pipeline doit pouvoir purger
 * et recharger eduai_data sans qu'aucune erreur ne puisse atteindre les
 * comptes des apprenants. Un simple schéma ne donnerait pas cette garantie —
 * un TRUNCATE mal ciblé traverse les schémas d'une même base. Deux instances
 * l'auraient donnée aussi, au prix d'un second conteneur, d'un second port et
 * d'une seconde sauvegarde, pour un projet qui tient sur une machine.
 *
 * eduai_data est créée par le conteneur lui-même à partir de POSTGRES_DB.
 * Ce script ne crée donc que la seconde.
 *
 * Exécution : automatique au premier démarrage du volume, via
 * /docker-entrypoint-initdb.d. L'ordre alphabétique des fichiers fait foi.
 */

-- Base applicative Django. Créée vide : les tables viendront des migrations,
-- qui restent la source de vérité du schéma applicatif (C17).
CREATE DATABASE eduai_app
    ENCODING  'UTF8'
    LC_COLLATE 'C'
    LC_CTYPE   'C'
    TEMPLATE   template0;

COMMENT ON DATABASE eduai_app IS
    'Application Django : utilisateurs, cours, exercices, quiz. Schéma géré par les migrations Django.';

COMMENT ON DATABASE eduai_data IS
    'Jeu de données collecté par le pipeline d''extraction (cinq types de sources). Aucune donnée à caractère personnel.';
