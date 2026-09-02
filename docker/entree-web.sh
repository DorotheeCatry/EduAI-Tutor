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

# --- Amorçage des données de référence ---
#
# Les migrations créent les tables ; elles ne les remplissent pas. Sans cette
# étape, le déploiement sert un onglet Référentiel et un catalogue de cours
# vides, alors que les fichiers source voyagent dans l'image. C'est le motif
# que le projet documente le plus souvent : vérifié dans un contexte, employé
# dans un autre.
#
# Choix : n'amorcer QUE si la table est vide, au lieu d'importer à chaque
# démarrage. Motivation mesurée : `importer_cours` met de côté les cours
# actifs et en publie de nouveaux à chaque exécution — sept cours et
# trente-six parties de plus par lancement. L'hébergeur redémarrant le
# conteneur à chaque déploiement, à chaque réveil et à chaque incident, la
# base accumulerait des générations identiques sans qu'aucune ne soit une
# vraie révision. La garde rend l'amorçage idempotent par construction.
#
# Conséquence à connaître : une mise à jour du contenu des cours n'est PAS
# reprise automatiquement par un redéploiement. Elle se demande à la main :
#   python manage.py importer_cours
#
# Choix : ces deux imports n'arrêtent pas le démarrage s'ils échouent, à la
# différence des migrations. Motivation : une migration ratée laisse un schéma
# incomplet, donc une application qui ment ; un amorçage raté laisse un
# catalogue vide, ce qui se voit et se répare sans couper le service. Un
# corpus mal formé ne doit pas rendre la plateforme entière injoignable.
# Toute valeur autre que « False » — y compris une valeur vide si la
# vérification elle-même échoue — vaut « ne pas amorcer ». Le doute penche
# du côté qui ne touche pas à la base.
echo "[demarrage] amorcage du referentiel et des cours si absents"

REFERENTIEL_PRESENT=$(/app/.venv/bin/python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduai_project.settings')
django.setup()
from apps.referentiel.models import Referentiel
print(Referentiel.objects.exists())
" 2>/dev/null | tail -1)

if [ "${REFERENTIEL_PRESENT}" = "False" ]; then
    /app/.venv/bin/python manage.py importer_referentiel \
        apps/referentiel/donnees/eduai-2026.json --activer \
        || echo "[demarrage] AVERTISSEMENT : referentiel non amorce"
else
    echo "[demarrage] referentiel deja en base"
fi

COURS_PRESENTS=$(/app/.venv/bin/python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduai_project.settings')
django.setup()
from apps.courses.models import CoursDeReference
print(CoursDeReference.objects.filter(remplace_le__isnull=True).exists())
" 2>/dev/null | tail -1)

if [ "${COURS_PRESENTS}" = "False" ]; then
    /app/.venv/bin/python manage.py importer_cours \
        || echo "[demarrage] AVERTISSEMENT : cours non amorces"
else
    echo "[demarrage] cours deja en base"
fi

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
