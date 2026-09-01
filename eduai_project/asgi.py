"""
Configuration ASGI du projet.

Compétence visée : C17 (épreuve E4) — application web
Compétence concernée : C13 (E3) — déploiement

Le projet a servi un temps deux protocoles : HTTP, et WebSocket pour un quiz
multijoueur. Le routage WebSocket a été retiré le 01/09/2026 avec le consumer
qu'il servait — 465 lignes qu'aucun client n'appelait, doublées par une
implémentation par sondage HTTP qui, elle, fonctionne (décision 031).

Ce fichier reste en ASGI : `Channels` sert toujours l'application, le
déploiement lance `uvicorn` sur `eduai_project.asgi`, et le passage à WSGI
ferait taire un jour une fonctionnalité asynchrone sans que rien ne le dise.
"""

import os

from django.core.asgi import get_asgi_application

# Django est initialisé avant tout import de code touchant aux modèles : sans
# cela, le registre des applications n'est pas encore peuplé.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduai_project.settings')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
})
