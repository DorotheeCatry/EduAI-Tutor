# Image du service IA (C9, Bloc 2).
#
# Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA
# Compétence visée : C13 (épreuve E3) — conteneurisation
#
# Choix : une image distincte de l'application Django. Motivation : le
# référentiel évalue séparément l'API du jeu de données (C5) et celle du
# service IA (C9). Deux images, deux conteneurs, deux cycles de vie : la panne
# de l'une ne fait pas tomber l'autre, et le périmètre de chacune est lisible
# sans explication.
#
# Choix : le dépôt entier est copié, et non le seul dossier service_ia.
# Motivation : le service réutilise les agents de `apps/agents`, la sonde de
# `apps/monitoring` et les réglages de `eduai_project`. Il ne les réimplémente
# pas — c'est la contrainte du chantier, et elle a une conséquence : le service
# a besoin du dépôt.

FROM python:3.13-slim

# uv est le gestionnaire de paquets du projet. L'installer depuis l'image
# officielle évite un téléchargement par curl et une vérification de somme.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Compte sans privilèges créé AVANT toute copie, et non après.
#
# Compétence visée : C13 (épreuve E3)
#
# Un service exposé ne tourne pas en root — réponse à OWASP API8. Mais la
# position de cette instruction compte autant que son existence : un
# `chown -R /app` placé après l'installation réécrit les métadonnées de chaque
# fichier, ce que Docker enregistre comme une COPIE COMPLÈTE de l'arborescence
# dans une nouvelle couche. Cette seule erreur ajoutait plus d'un gigaoctet à
# l'image, invisible dans le Dockerfile et bien réelle sur le disque.
RUN useradd --create-home --uid 1000 eduai
WORKDIR /app
RUN chown eduai:eduai /app
USER eduai

# Les dépendances sont installées AVANT la copie du code, et c'est mesuré :
# cette instruction prend 332 secondes. Placée après le `COPY . .`, elle serait
# rejouée à chaque modification du moindre fichier. Placée ici, elle n'est
# rejouée que lorsque pyproject.toml ou uv.lock changent — les reconstructions
# suivantes sont quasi instantanées.
#
# `--chown` à la copie plutôt qu'un `chown` après : le propriétaire est fixé au
# moment où le fichier entre dans la couche, sans la dupliquer.
COPY --chown=eduai:eduai pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Ce que cette copie EMBARQUE est décidé par .dockerignore : ni l'historique
# Git, ni le vector store, ni les données du pipeline, ni les journaux — tous
# montés en volume ou sans usage à l'exécution.
COPY --chown=eduai:eduai . .
RUN uv sync --frozen

EXPOSE 8100

# Sonde de vivacité interne à l'image : elle interroge /ai/sante, qui ne
# requiert pas de clé — précisément pour qu'un orchestrateur puisse la lire
# sans qu'on lui confie de secret.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/ai/sante', timeout=4).status==200 else 1)"

# Un seul travailleur : les compteurs Prometheus vivent en mémoire du
# processus, et plusieurs travailleurs feraient collecter une fraction du
# trafic par le collecteur. Le passage à plusieurs travailleurs suppose
# d'activer l'agrégation multi-processus de prometheus_client.
CMD ["uv", "run", "uvicorn", "service_ia.main:application", \
     "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
