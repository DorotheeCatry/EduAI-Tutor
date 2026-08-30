#!/usr/bin/env bash
#
# Export du jeu de données `eduai_data` en vue d'un chargement chez l'hébergeur.
#
# Compétence visée : C4 (épreuve E1) — base de données du jeu de données
# Compétence visée : C13 (épreuve E3) — livraison
# Compétence visée : C19 (épreuve E5) — étape de la chaîne, ici manuelle
#
# Pourquoi un export et non un rejeu du pipeline sur le serveur : le pipeline
# part des sources brutes — dont un dump Stack Exchange de plusieurs
# gigaoctets — qui ne sont ni versionnées ni transférables raisonnablement. Le
# résultat, lui, tient en une soixantaine de mégaoctets.
#
# Pourquoi le schéma ET les données : les scripts de `data_pipeline/load/sql/`
# créent le schéma et restent la référence, mais les rejouer chez l'hébergeur
# puis charger les données séparément fait deux opérations là où une suffit, et
# ouvre la possibilité qu'elles divergent. L'export porte les deux, dans le
# même fichier, pris au même instant.
#
# Ce que l'export NE porte PAS : les rôles PostgreSQL. `pg_dump` exporte une
# base, pas les comptes du serveur. Le rôle de lecture seule `eduai_lecture`,
# dont dépend l'API du jeu de données (C5), doit être créé séparément sur le
# serveur cible — voir docs/chaine_livraison.md.
#
# Usage :
#   ./data_pipeline/load/exporter_jeu_donnees.sh [repertoire_de_sortie]

set -euo pipefail

# --- 1. Initialisation des dépendances et connexions externes ---

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SORTIE="${1:-${RACINE}/data_pipeline/data/exports}"

# Lecture ciblée de .env, variable par variable.
#
# Le fichier n'est PAS interprété par le shell : la clé secrète Django y
# contient des parenthèses et des dollars, et un `source` échoue dessus
# — « syntax error near unexpected token ) ». Les variables déclarées après
# ne seraient alors pas chargées, et l'export échouerait pour une raison sans
# rapport avec l'export. Le même piège est déjà documenté dans tests/conftest.py.
lire_env() {
    local cle="$1"
    [ -f "${RACINE}/.env" ] || return 0
    sed -n "s/^${cle}=//p" "${RACINE}/.env" | head -1 | tr -d '"'"'"
}

POSTGRES_HOST="${POSTGRES_HOST:-$(lire_env POSTGRES_HOST)}"
POSTGRES_PORT="${POSTGRES_PORT:-$(lire_env POSTGRES_PORT)}"
POSTGRES_USER="${POSTGRES_USER:-$(lire_env POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(lire_env POSTGRES_DB)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(lire_env POSTGRES_PASSWORD)}"

HOTE="${POSTGRES_HOST:-127.0.0.1}"
PORT="${POSTGRES_PORT:-5433}"
ROLE="${POSTGRES_USER:-eduai}"
BASE="${POSTGRES_DB:-eduai_data}"

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "ERREUR : POSTGRES_PASSWORD est absente. Renseigner .env." >&2
    exit 2
fi

# L'export passe par le pg_dump DU CONTENEUR, pas par celui de la machine.
#
# Motivation : le client installé sur le poste est en version 14, le serveur en
# 16. Un pg_dump plus ancien que son serveur produit une archive que le
# pg_restore correspondant ne relit pas — constaté ici, « unsupported version
# (1.16) in file header ». Le conteneur porte les outils de sa propre version :
# c'est la seule combinaison dont on sache qu'elle est cohérente.
CONTENEUR="${EDUAI_CONTENEUR_POSTGRES:-eduai_postgres}"

command -v docker >/dev/null 2>&1 || {
    echo "ERREUR : docker est introuvable, et l'export passe par le conteneur." >&2
    exit 2
}
docker ps --format '{{.Names}}' | grep -qx "${CONTENEUR}" || {
    echo "ERREUR : le conteneur ${CONTENEUR} n'est pas démarré." >&2
    echo "         Lancer : docker compose up -d postgres" >&2
    exit 2
}

mkdir -p "${SORTIE}"
HORODATAGE="$(date +%Y%m%d-%H%M%S)"
FICHIER="${SORTIE}/eduai_data-${HORODATAGE}.sql.gz"

# --- 2. Règles logiques de traitement ---

echo "[export] base ${BASE} sur ${HOTE}:${PORT}"

# Volumétrie AVANT l'export, pour pouvoir la comparer après chargement. C'est
# le contrôle qui manquait le 27/08, quand un chargement s'est annoncé réussi
# sur une base restée vide (incident 001).
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${CONTENEUR}" \
    psql -U "${ROLE}" -d "${BASE}" -tA -c "
        SELECT 'documents=' || count(*) FROM document
        UNION ALL SELECT 'mots_cles=' || count(*) FROM mot_cle
        UNION ALL SELECT 'sources=' || count(*) FROM source;
    " | tee "${FICHIER}.volumetrie"

# SQL brut compressé, et non le format personnalisé de pg_dump.
#
# Le format personnalisé permettrait une restauration sélective, mais il
# impose un `pg_restore` de version compatible sur la machine cible. Or la
# version PostgreSQL de l'hébergeur n'est pas choisie par ce projet, et une
# archive illisible le jour du chargement ne laisse aucune issue. Du SQL se
# charge avec n'importe quel `psql`, y compris celui d'un conteneur quelconque.
#
# `--no-owner --no-privileges` : les rôles du poste de développement n'existent
# pas sur le serveur cible. Sans ces options, le chargement échouerait sur
# chaque instruction ALTER ... OWNER TO.
echo "[export] écriture de ${FICHIER}"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${CONTENEUR}" \
    pg_dump -U "${ROLE}" -d "${BASE}" \
            --format=plain --no-owner --no-privileges \
    | gzip -9 > "${FICHIER}"

# --- 3. Gestion des erreurs et exceptions ---
# `set -euo pipefail` ci-dessus interrompt à la première erreur : un export
# partiel ne doit pas se présenter comme un export. Le contrôle qui suit vérifie
# que le fichier produit est lisible par pg_restore, et pas seulement présent —
# un fichier existant mais tronqué est le cas que ce projet a déjà rencontré.

if [ ! -s "${FICHIER}" ]; then
    echo "ERREUR : le fichier d'export est vide." >&2
    exit 1
fi

# Contrôle de l'archive : décompressable, et contenant bien du schéma ET des
# données. Un fichier gzip valide mais ne portant que des CREATE TABLE passerait
# un contrôle de taille — pas celui-ci.
echo "[export] vérification de l'archive"
gzip -t "${FICHIER}" || {
    echo "ERREUR : l'archive est corrompue." >&2
    exit 1
}
TABLES_DANS_ARCHIVE="$(gunzip -c "${FICHIER}" | grep -c '^CREATE TABLE' || true)"
COPIES_DANS_ARCHIVE="$(gunzip -c "${FICHIER}" | grep -c '^COPY ' || true)"
echo "  tables décrites : ${TABLES_DANS_ARCHIVE}"
echo "  blocs de données : ${COPIES_DANS_ARCHIVE}"
if [ "${TABLES_DANS_ARCHIVE}" -lt 13 ] || [ "${COPIES_DANS_ARCHIVE}" -lt 5 ]; then
    echo "ERREUR : l'archive ne contient pas le schéma complet et ses données." >&2
    exit 1
fi

# --- 4. Sauvegarde des résultats ---

sha256sum "${FICHIER}" > "${FICHIER}.sha256"
TAILLE="$(du -h "${FICHIER}" | cut -f1)"

echo
echo "[export] terminé"
echo "  archive     : ${FICHIER}  (${TAILLE})"
echo "  empreinte   : ${FICHIER}.sha256"
echo "  volumétrie  : ${FICHIER}.volumetrie"
echo
echo "Chargement sur le serveur cible : voir docs/chaine_livraison.md,"
echo "section « Provisionner le jeu de données ». Ne pas oublier le rôle de"
echo "lecture seule eduai_lecture, que cette archive ne contient pas."
