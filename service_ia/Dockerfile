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

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Les dépendances sont installées avant la copie du code : une modification du
# code ne réinvalide alors pas la couche d'installation, qui est la plus longue.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# Compte sans privilèges : un service exposé ne tourne pas en root.
# Réponse à OWASP API8, « Security Misconfiguration ».
RUN useradd --create-home --uid 1000 eduai \
    && chown -R eduai:eduai /app
USER eduai

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
