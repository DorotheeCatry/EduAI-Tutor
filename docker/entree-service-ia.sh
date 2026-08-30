#!/bin/sh
#
# Démarrage du conteneur du service IA.
#
# Compétence visée : C13 (épreuve E3) — livraison et exécution
# Compétence concernée : C9 (E2) — API du service IA
#
# Pourquoi ce script existe : le port d'écoute était écrit en dur dans le
# `CMD` de l'image. En local, c'est sans conséquence — on choisit son port et
# on publie celui qu'on veut. Chez l'hébergeur, non : Railway attribue un port
# par la variable `PORT` et n'interroge que celui-là. Le conteneur démarrait
# donc correctement, servait sur 8100, et la plateforme répondait
# « Application failed to respond » à toute requête (incident 008).
#
# Choix : un script, comme pour l'application web (`docker/entree-web.sh`), et
# non un `CMD` en forme shell. Motivation : la forme exec d'un `CMD` n'étend
# pas les variables d'environnement — `--port ${PORT}` y serait transmis
# littéralement. La forme shell les étendrait, mais le motif du repli ne
# tiendrait pas sur une ligne, et c'est ce motif qu'il faut pouvoir relire.

set -e

# Le port est imposé par l'hébergeur via $PORT. La valeur de repli sert au
# lancement local de l'image et au fichier de composition, qui publie 8100.
PORT_ECOUTE="${PORT:-8100}"

echo "[demarrage] uvicorn sur 0.0.0.0:${PORT_ECOUTE}"

# Choix : un seul travailleur. Motivation : les compteurs Prometheus vivent en
# mémoire du processus, et plusieurs travailleurs feraient collecter une
# fraction du trafic par le collecteur. Le passage à plusieurs travailleurs
# suppose d'activer l'agrégation multi-processus de prometheus_client.
#
# Choix : `--proxy-headers` et `--forwarded-allow-ips`. Motivation : la
# plateforme place un proxy devant le service. Sans ces options, toute requête
# paraît venir de l'adresse du proxy — or la limitation de débit se rabat sur
# l'adresse lorsqu'aucune clé de service n'est fournie, ce qui est le cas de
# `/ai/sante`. Le quota de la sonde serait alors partagé par tous les
# appelants au lieu d'être compté par appelant.
#
# Les binaires de l'environnement sont appelés directement, jamais par
# `uv run` : celui-ci resynchronise l'environnement avant d'exécuter la
# commande, donc accède au réseau et réinstalle les groupes exclus à la
# construction. Un service qui a besoin d'internet pour démarrer n'est pas un
# service déployé.
exec /app/.venv/bin/uvicorn service_ia.main:application \
    --host 0.0.0.0 \
    --port "${PORT_ECOUTE}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*'
