#!/usr/bin/env bash
#
# Reconstruit la feuille de style de l'application.
#
# Compétence visée : C17 (épreuve E4) — application web
# Compétence concernée : C13 (E3) — déploiement
#
# À lancer après TOUTE modification de gabarit qui introduit une classe
# Tailwind nouvelle. Sans reconstruction, la classe ne produit aucun style et
# rien ne le signale : la page s'affiche, simplement de travers. Le test
# `tests/test_coquille_interface.py` échoue dans ce cas — c'est lui qui
# remplace la vigilance.
#
# Pourquoi le binaire autonome et non `manage.py tailwind build` : le nécessaire
# `django-tailwind` installé est en Tailwind 4, alors que l'application a
# toujours été rendue par du Tailwind 3.4.17 ; et sa construction échoue de
# toute façon sur le Node 12 de la machine (décision 034).

set -euo pipefail

VERSION="3.4.17"
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BINAIRE="${RACINE}/theme/tailwind-v3/tailwindcss"

if [[ ! -x "${BINAIRE}" ]]; then
    echo "Téléchargement du binaire autonome Tailwind ${VERSION}…"
    curl -sSL -o "${BINAIRE}" \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/v${VERSION}/tailwindcss-linux-x64"
    chmod +x "${BINAIRE}"
fi

"${BINAIRE}" \
    -c "${RACINE}/theme/tailwind-v3/tailwind.config.js" \
    -i "${RACINE}/theme/tailwind-v3/entree.css" \
    -o "${RACINE}/static/css/tailwind.css" \
    --minify

echo "Feuille écrite : static/css/tailwind.css"
echo "Ne pas oublier de la committer : l'image de déploiement est bâtie sur le clone."
