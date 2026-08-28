"""
Amorçage de Django dans le processus FastAPI.

Compétence visée : C9 (épreuve E2)

Les agents vivent dans des applications Django et touchent l'ORM — l'agent
Watcher enregistre les méprises des apprenants dans `eduai_app`. Les réutiliser
suppose donc un Django initialisé, même si aucune vue Django n'est servie ici.

Choix : `django.setup()` dans le processus FastAPI plutôt qu'un appel HTTP vers
l'application Django. Motivation : un appel HTTP ajouterait un saut réseau, une
sérialisation, une authentification et un mode de panne supplémentaires — pour
atteindre du code Python qui vit dans le même dépôt. Le service partage le
dépôt, il peut partager l'import.

Choix : l'amorçage se fait à l'import de ce module, appelé en tout premier par
`main.py`. Motivation : importer un modèle Django avant `django.setup()` lève
`AppRegistryNotReady`, un message qui ne dit pas ce qu'il faut faire. L'ordre
est donc imposé par la structure, pas laissé à la discipline.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

#: Racine du dépôt, ajoutée au chemin d'import pour retrouver `apps`.
RACINE = Path(__file__).resolve().parent.parent


def amorcer() -> None:
    """
    Initialise Django une seule fois pour le processus.

    Compétence visée : C9 (épreuve E2)
    """
    import sys

    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eduai_project.settings")

    import django
    from django.apps import apps as registre

    if registre.ready:
        return

    django.setup()
    logger.info(
        "Django amorcé dans le processus du service IA — les agents et la "
        "sonde de monitorage sont disponibles."
    )


amorcer()
