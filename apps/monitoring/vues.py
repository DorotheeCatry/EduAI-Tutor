"""
Point de terminaison des métriques Prometheus.

Compétence visée : C20 (épreuve E5) — monitorage du service en production
Compétence visée : C13 (épreuve E3) — exposition maîtrisée d'un service

Choix : une vue Django plutôt que le serveur HTTP autonome de
`prometheus_client`. Motivation : ce dernier ouvre un second port, qu'il
faudrait publier, protéger et surveiller séparément. La vue réutilise le port
et la pile existants, et hérite des réglages de sécurité déjà en place.
"""

from __future__ import annotations

import ipaddress
import logging
import os

from django.http import HttpRequest, HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .metriques import REGISTRE, rafraichir_taille_journal

logger = logging.getLogger(__name__)

#: Réseaux autorisés à collecter les métriques.
#:
#: Compétence visée : C13 (épreuve E3)
#:
#: Choix : une liste de réseaux et non une authentification. Motivation : un
#: collecteur Prometheus ne sait pas porter de jeton applicatif sans
#: configuration supplémentaire, et /metrics n'expose aucune donnée
#: personnelle — des compteurs, des latences, des noms de modèles. Le risque
#: est la divulgation d'informations d'exploitation, que le cloisonnement
#: réseau traite mieux qu'un secret partagé de plus.
#:
#: Par défaut : la boucle locale et les réseaux privés de conteneurs. Le
#: collecteur tourne dans un conteneur Docker sur la même machine.
RESEAUX_AUTORISES = [
    reseau.strip()
    for reseau in os.environ.get(
        "MONITORAGE_RESEAUX_METRIQUES",
        "127.0.0.0/8,::1/128,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8",
    ).split(",")
    if reseau.strip()
]


def _autorise(adresse: str | None) -> bool:
    """
    Dit si une adresse appelante a le droit de collecter les métriques.

    Compétence visée : C13 (épreuve E3)

    Choix : refuser une adresse illisible plutôt que l'accepter. Motivation :
    une adresse qu'on ne sait pas analyser est une adresse dont on ne sait rien.
    """
    if not adresse:
        return False
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        logger.warning("[monitorage] adresse d'appel illisible : %r", adresse)
        return False
    for reseau in RESEAUX_AUTORISES:
        try:
            if ip in ipaddress.ip_network(reseau, strict=False):
                return True
        except ValueError:
            logger.warning("[monitorage] réseau autorisé mal formé : %r", reseau)
    return False


def metriques(request: HttpRequest) -> HttpResponse:
    """
    Expose les métriques du service IA au format Prometheus.

    Compétence visée : C20 (épreuve E5)

    Choix : la taille du journal est relue sur le disque à chaque collecte.
    Motivation : c'est la seule mesure de ce module qui constate un effet plutôt
    qu'un compteur interne. Un journal dont le nombre d'événements augmente
    pendant que le fichier stagne est un journal qui n'écrit plus — invisible
    pour qui ne regarde que les compteurs, et c'est exactement le motif des cinq
    incidents du projet.
    """
    adresse = request.META.get("REMOTE_ADDR")
    if not _autorise(adresse):
        logger.warning(
            "[monitorage] collecte refusée depuis %s — réseaux autorisés : %s",
            adresse, ", ".join(RESEAUX_AUTORISES),
        )
        return HttpResponse(
            "Collecte des métriques réservée aux réseaux déclarés.\n",
            status=403, content_type="text/plain; charset=utf-8",
        )

    rafraichir_taille_journal()
    return HttpResponse(
        generate_latest(REGISTRE),
        content_type=CONTENT_TYPE_LATEST,
    )
