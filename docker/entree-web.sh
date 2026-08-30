#!/bin/sh
#
# Démarrage du conteneur de l'application web.
#
# Compétence visée : C13 (épreuve E3) — livraison et exécution
#
# Choix : un script plutôt qu'un `CMD` en une ligne. Motivation : deux choses
# doivent avoir lieu dans l'ordre au démarrage, et une seule ligne les rendrait
# illisibles. Le script est versionné, donc relisible par le jury.
#
# Choix : `set -e`. Motivation : sans lui, une migration en échec laisserait le
# serveur démarrer sur un schéma incomplet — l'application répondrait, avec des
# erreurs de colonne manquante à la première requête. Mieux vaut un conteneur
# qui refuse de démarrer : l'hébergeur le signale, une page cassée non.

set -e

# Les binaires de l'environnement sont appelés directement, jamais par
# `uv run`. Motivation : `uv run` resynchronise l'environnement avant
# d'exécuter la commande. Au démarrage d'un conteneur, cela signifie une
# tentative d'installation de paquets — donc un accès réseau, une latence, et
# un échec possible si le registre est injoignable. Un service qui a besoin
# d'internet pour démarrer n'est pas un service déployé.
echo "[demarrage] application des migrations"
/app/.venv/bin/python manage.py migrate --noinput

# Le port est imposé par l'hébergeur via $PORT. La valeur de repli sert au
# lancement local de l'image, hors de la plateforme.
PORT_ECOUTE="${PORT:-8000}"

echo "[demarrage] uvicorn sur 0.0.0.0:${PORT_ECOUTE}"
#
# Choix : `eduai_project.asgi` et non `wsgi`. Motivation : le projet déclare
# ASGI_APPLICATION et embarque Channels. Servir en WSGI ferait taire les
# WebSockets sans que rien ne le dise — et le projet a déjà documenté ce que
# coûtent les fonctions qui se taisent au lieu d'échouer.
#
# Choix : un seul travailleur. Motivation : la couche de canaux est en mémoire
# de processus (InMemoryChannelLayer), et le compteur Prometheus aussi.
# Plusieurs travailleurs les fragmenteraient sans qu'aucune erreur n'apparaisse.
exec /app/.venv/bin/uvicorn eduai_project.asgi:application \
    --host 0.0.0.0 \
    --port "${PORT_ECOUTE}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*'
