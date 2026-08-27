#!/bin/bash
#
# Création du rôle PostgreSQL en lecture seule utilisé par l'API du jeu de
# données.
#
# Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données
# Compétence visée : C13 (épreuve E3) — moindre privilège
#
# Choix : un script shell et non un fichier .sql. Motivation : le mot de passe
# du rôle vient de l'environnement du conteneur. Un fichier .sql ne peut pas
# lire une variable d'environnement, et l'y écrire en dur reviendrait à
# versionner un secret — exactement ce que le projet s'interdit.
#
# Choix : ce rôle existe alors que le routeur Django refuse déjà les écritures
# et que les vues n'exposent aucune route d'écriture. Motivation : ces deux
# garanties vivent dans le code du projet. Celle-ci vit dans le moteur, et tient
# donc même si le code se trompe. Les trois échouent différemment, c'est tout
# l'intérêt de les superposer.
#
# Exécution : automatique au premier démarrage du volume, via
# /docker-entrypoint-initdb.d, dans l'ordre alphabétique des fichiers.

set -euo pipefail

if [ -z "${EDUAI_DATA_PASSWORD:-}" ]; then
    echo "06_role_lecture.sh : EDUAI_DATA_PASSWORD absente de l'environnement."
    echo "  Le rôle de lecture seule n'a PAS été créé, et l'API du jeu de"
    echo "  données ne pourra pas se connecter. Renseigner la variable dans"
    echo "  .env puis recréer le volume, ou créer le rôle à la main."
    exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v mdp="'${EDUAI_DATA_PASSWORD}'" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eduai_lecture') THEN
        CREATE ROLE eduai_lecture LOGIN;
    END IF;
END
$$;

ALTER ROLE eduai_lecture WITH PASSWORD :mdp;

-- Droits strictement nécessaires à une API de consultation.
GRANT CONNECT ON DATABASE eduai_data TO eduai_lecture;
GRANT USAGE   ON SCHEMA public       TO eduai_lecture;
GRANT SELECT  ON ALL TABLES IN SCHEMA public TO eduai_lecture;

-- Les tables créées après ce script héritent du même droit, sans intervention.
-- Sans cette ligne, une table ajoutée au schéma resterait invisible de l'API,
-- et le symptôme — « permission denied » sur une seule table — serait
-- déroutant.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO eduai_lecture;

-- Aucun droit n'est accordé sur eduai_app : l'API du jeu de données n'a rien
-- à y voir, et la base applicative porte les comptes des apprenants.

COMMENT ON ROLE eduai_lecture IS
    'Rôle de consultation du jeu de données, utilisé par l''API C5. SELECT uniquement.';
SQL

echo "06_role_lecture.sh : rôle eduai_lecture créé, SELECT uniquement."
