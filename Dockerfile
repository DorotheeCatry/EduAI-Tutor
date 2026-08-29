# Image de l'application web Django (Bloc 3).
#
# Compétence visée : C17 (épreuve E4) — application web
# Compétence visée : C13 (épreuve E3) — conteneurisation et livraison
#
# Choix : une image distincte de celle du service IA (`service_ia/Dockerfile`).
# Motivation : le référentiel évalue séparément l'API du jeu de données (C5,
# servie ici par Django REST Framework) et l'API du service IA (C9, en FastAPI).
# Deux images rendent la séparation lisible sans explication, et la panne de
# l'une ne fait pas tomber l'autre.
#
# Choix : le dépôt entier est copié. Motivation : l'application appelle les
# agents de `apps/agents`, la sonde de `apps/monitoring` et les modèles de
# `apps/api_data`. Ce que la copie embarque réellement est décidé par
# `.dockerignore` — et depuis le 29/08/2026, le corpus vectoriel en fait partie
# (voir plus bas).

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Compte sans privilèges créé AVANT toute copie.
#
# Compétence visée : C13 (épreuve E3)
#
# Un `chown -R /app` placé après l'installation réécrirait les métadonnées de
# chaque fichier, ce que Docker enregistre comme une copie complète de
# l'arborescence dans une nouvelle couche. La même erreur avait ajouté plus
# d'un gigaoctet à l'image du service IA — invisible dans le fichier, bien
# réelle sur le disque.
RUN useradd --create-home --uid 1000 eduai
WORKDIR /app
RUN chown eduai:eduai /app
USER eduai

# Dépendances avant le code : cette couche n'est rejouée que si pyproject.toml
# ou uv.lock changent, pas à chaque modification d'un gabarit.
COPY --chown=eduai:eduai pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Le corpus vectoriel dans sa propre couche, AVANT la copie du reste.
#
# Compétence visée : C13 (épreuve E3)
#
# Environ 219 Mio. Isolé ici, il n'est recopié que lorsqu'il change réellement ;
# noyé dans la copie du dépôt, il serait retransféré à chaque retouche de code.
# Le choix d'embarquer le corpus plutôt que de l'indexer au démarrage est
# documenté dans docs/decisions/021 : réindexer les 21 189 fragments demande
# plus de dix-sept heures, qu'aucun démarrage de conteneur ne peut porter.
COPY --chown=eduai:eduai apps/rag/chroma ./apps/rag/chroma

COPY --chown=eduai:eduai . .
RUN uv sync --frozen

# Collecte des fichiers statiques à la construction, et non au démarrage.
#
# Compétence visée : C13 (épreuve E3)
#
# Une collecte au démarrage rallongerait chaque redémarrage et écrirait dans un
# système de fichiers éphémère. À la construction, elle est faite une fois et
# ses erreurs arrêtent la construction — au lieu d'apparaître en production
# sous la forme d'une page sans feuille de style.
#
# Les trois variables ci-dessous n'existent QUE pendant cette instruction.
# Elles ne sont pas des valeurs de repli : les réglages refusent de se charger
# sans elles, et `collectstatic` n'ouvre aucune connexion à la base. Aucune ne
# subsiste dans l'image — la commande les définit pour sa seule durée.
RUN DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY="valeur-de-construction-sans-usage-a-l-execution" \
    POSTGRES_PASSWORD="valeur-de-construction-sans-usage-a-l-execution" \
    EDUAI_DATA_PASSWORD="valeur-de-construction-sans-usage-a-l-execution" \
    uv run python manage.py collectstatic --noinput --clear

# Port de repli. L'hébergeur impose le sien par la variable PORT, que le script
# de démarrage lit.
EXPOSE 8000

# Sonde de vivacité : la page de connexion, qui ne demande ni base chargée ni
# session ouverte.
#
# Choix : `http.client` et non `urllib.request`. Motivation : hors DEBUG,
# Django redirige tout le trafic en clair vers HTTPS. `urllib` suit la
# redirection, tente une connexion TLS sur un port qui n'en sert pas, et la
# sonde échoue alors que l'application va bien. `http.client` ne suit rien : il
# lit le code de retour, et un 301 prouve que Django répond.
#
# Choix : tout code inférieur à 500 vaut « vivant ». Motivation : la sonde
# répond à « le processus sert-il des requêtes ? », pas à « cette page est-elle
# celle que j'attends ? ». Exiger 200 ferait échouer la sonde à la première
# redirection de configuration.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import http.client,os,sys; c=http.client.HTTPConnection('127.0.0.1', int(os.environ.get('PORT','8000')), timeout=4); c.request('GET','/auth/login/'); sys.exit(0 if c.getresponse().status < 500 else 1)"

CMD ["./docker/entree-web.sh"]
