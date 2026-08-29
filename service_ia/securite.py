"""
Authentification, limitation de débit et garde-fous du service IA.

Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA
Compétence visée : C13 (épreuve E3) — sécurité de l'application

Le modèle de menace de cette API n'est pas celui de l'API du jeu de données.
Celle-ci ne lit pas un corpus : elle **dépense**. Chaque appel déclenche un
appel facturé au fournisseur de modèles. Le risque principal n'est donc ni la
fuite ni l'altération de données, mais l'épuisement du quota — par un tiers,
ou par un client légitime en boucle.
"""

from __future__ import annotations

import hmac
import logging
import os
import uuid

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

#: En-tête portant la clé de service.
NOM_ENTETE_CLE = "X-Cle-Service"

entete_cle = APIKeyHeader(
    name=NOM_ENTETE_CLE,
    auto_error=False,
    description=(
        "Clé de service, à obtenir auprès de l'organisme de formation. "
        "Cette API est consommée par des programmes, non par des navigateurs."
    ),
)


def _cles_valides() -> set[str]:
    """
    Lit les clés de service acceptées depuis l'environnement.

    Compétence visée : C13 (épreuve E3)

    Choix : plusieurs clés séparées par des virgules plutôt qu'une seule.
    Motivation : une clé par consommateur permet de révoquer celle qui fuit sans
    interrompre les autres. Une clé unique partagée transforme toute révocation
    en interruption de service, et une révocation qu'on n'ose pas faire n'est
    pas une révocation.

    Choix : aucune valeur de repli. Motivation : une clé par défaut dans le code
    est une clé publique. Son absence rend le service inutilisable, ce qui se
    voit immédiatement — contrairement à une clé devinable.
    """
    brut = os.environ.get("SERVICE_IA_CLES", "")
    return {cle.strip() for cle in brut.split(",") if cle.strip()}


async def verifier_cle(
    request: Request,
    # Déclaré en `Security` et non lu directement dans les en-têtes : c'est ce
    # qui fait apparaître le schéma d'authentification dans la documentation
    # OpenAPI. Sans cette dépendance, l'API fonctionne à l'identique mais un
    # consommateur qui lit la documentation ignore qu'un en-tête est exigé — et
    # découvre l'exigence par un 401 sans explication.
    _declaration: str | None = Security(entete_cle),
) -> str:
    """
    Contrôle la clé de service portée par la requête.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C13 (épreuve E3) — OWASP API2

    Choix : `hmac.compare_digest` plutôt que `==`. Motivation : la comparaison
    de chaînes de Python s'arrête au premier caractère différent, ce qui rend sa
    durée dépendante du préfixe commun. Un attaquant patient déduit la clé
    caractère par caractère. La comparaison à temps constant supprime ce canal.

    Choix : le même message et le même code pour une clé absente et pour une
    clé fausse. Motivation : distinguer les deux dirait à l'appelant si le nom
    de l'en-tête est correct, ce qui est déjà un renseignement.
    """
    cles = _cles_valides()
    if not cles:
        logger.error(
            "SERVICE_IA_CLES est absente ou vide : aucune clé n'est acceptée. "
            "Le service refuse tout appel plutôt que d'ouvrir l'accès."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service non configuré : aucune clé de service déclarée.",
        )

    fournie = request.headers.get(NOM_ENTETE_CLE) or ""

    # Choix : comparer des octets, jamais des chaînes. Motivation :
    # `hmac.compare_digest` refuse deux `str` dès que l'une porte un caractère
    # hors ASCII, et lève `TypeError` — « comparing strings with non-ASCII
    # characters is not supported ». Une clé mal formée (un copier-coller qui
    # embarque une lettre accentuée) sortait donc de cette fonction par une
    # exception, que FastAPI traduisait en 500. Trois conséquences, toutes
    # indésirables : l'appelant recevait une erreur serveur là où son appel
    # était simplement refusé ; le bruit de ces 500 aurait noyé les vraies
    # pannes internes ; et l'écart de code entre une clé fausse en ASCII (401)
    # et une clé fausse accentuée (500) renseignait un attaquant sur la nature
    # de sa saisie, ce que le reste de cette fonction s'applique justement à ne
    # pas faire. L'encodage préalable ramène tous les cas au même chemin : un
    # refus. Voir docs/incidents/2026-08-29-cle-non-ascii-erreur-serveur.md
    #
    # Choix : `surrogateescape` plutôt qu'un encodage strict. Motivation : les
    # octets non décodables d'une variable d'environnement arrivent en Python
    # sous forme de substituts, qu'un encodage strict rejetterait à son tour
    # par une `UnicodeEncodeError` — le même défaut déplacé d'un cran. Une clé
    # illisible doit aboutir à un refus, jamais à une exception.
    fournie_octets = fournie.encode("utf-8", "surrogateescape")

    for attendue in cles:
        if hmac.compare_digest(fournie_octets, attendue.encode("utf-8", "surrogateescape")):
            return attendue

    logger.warning(
        "Appel refusé — clé de service absente ou invalide, depuis %s",
        request.client.host if request.client else "origine inconnue",
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Clé de service absente ou invalide.",
        headers={"WWW-Authenticate": NOM_ENTETE_CLE},
    )


def cle_pour_limitation(request: Request) -> str:
    """
    Désigne l'entité à laquelle imputer un quota.

    Compétence visée : C9 (épreuve E2) — OWASP API4

    Choix : la clé de service, et l'adresse seulement à défaut. Motivation :
    limiter par adresse punit tous les consommateurs derrière un même réseau et
    n'arrête pas un client qui change d'adresse. La clé identifie le
    consommateur, ce qui est précisément la granularité voulue.

    Choix : la clé n'est pas mise telle quelle dans le compteur — seuls ses
    premiers caractères, préfixés. Motivation : les clés de limitation
    apparaissent dans les journaux de diagnostic ; y écrire un secret complet le
    divulguerait à quiconque lit ces journaux.
    """
    fournie = request.headers.get(NOM_ENTETE_CLE)
    if fournie:
        return f"cle:{fournie[:8]}"
    return f"ip:{request.client.host if request.client else 'inconnue'}"


def identifiant_incident() -> str:
    """
    Engendre un identifiant de corrélation pour une erreur.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C21 (épreuve E5)

    L'appelant reçoit cet identifiant, jamais la trace. Il le cite, et la trace
    complète se retrouve dans le journal de monitorage. Renvoyer la trace
    exposerait les chemins du serveur et les versions des bibliothèques.
    """
    return uuid.uuid4().hex[:12]


#: Quotas par défaut, surchargeables par variable d'environnement.
#:
#: Choix : un quota distinct pour les points de terminaison de génération et
#: pour la recherche. Motivation : une génération est un appel facturé au
#: fournisseur, une recherche ne touche que le vector store local. Les soumettre
#: au même plafond obligerait à brider la recherche au rythme de ce que coûte
#: la génération.
QUOTA_GENERATION = os.environ.get("SERVICE_IA_QUOTA_GENERATION", "30/minute")
QUOTA_RECHERCHE = os.environ.get("SERVICE_IA_QUOTA_RECHERCHE", "120/minute")
QUOTA_SANTE = os.environ.get("SERVICE_IA_QUOTA_SANTE", "60/minute")

#: Nombre maximal d'appels simultanés au fournisseur de modèles.
#:
#: Choix : un plafond de concurrence en plus du quota par minute. Motivation :
#: les deux ne protègent pas de la même chose. Le quota borne la consommation
#: dans le temps ; le plafond borne la charge instantanée. Trente appels lancés
#: dans la même seconde respectent un quota de trente par minute et saturent
#: pourtant la mémoire du service et le débit du fournisseur.
CONCURRENCE_MAX = int(os.environ.get("SERVICE_IA_CONCURRENCE_MAX", "4"))
