"""
Application FastAPI du service IA.

Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA
Compétence visée : C13 (épreuve E3) — sécurité de l'application
Compétence visée : C20 (épreuve E5) — monitorage

Lancement :

    uv run uvicorn service_ia.main:application --host 127.0.0.1 --port 8100

Documentation interactive : /ai/docs — schéma OpenAPI : /ai/openapi.json

Choix : un service distinct de l'application Django, et non une seconde
application Django. Motivation : le référentiel évalue séparément l'API du jeu
de données (C5) et celle du service IA (C9). Deux processus et deux frameworks
rendent le périmètre de chacune lisible sans qu'il faille l'expliquer — et la
panne de l'un ne fait pas tomber l'autre. Voir docs/decisions/015.
"""

from __future__ import annotations

# L'amorçage de Django doit précéder tout import d'agent : ces derniers
# touchent l'ORM, et les importer avant `django.setup()` lève une exception
# dont le message ne dit pas quoi faire.
from . import amorce  # noqa: F401  — importé pour son effet de bord

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Importé après `amorce`, qui charge Django : le module de quotas déclare un
# modèle et ne peut pas être importé avant que le registre des applications
# soit prêt.
from apps.quotas.service import QuotaDepasse
from apps.rag.utils import COLLECTION_DOCUMENTAIRE

from . import agents
from .schemas import (
    DemandeCours,
    DemandeExercice,
    DemandeExplication,
    DemandeFeedback,
    DemandeRecherche,
    ErreurAPI,
    EtatFournisseur,
    FragmentRAG,
    ReponseGeneration,
    ReponseRecherche,
    ReponseSante,
)
from .securite import (
    QUOTA_GENERATION,
    QUOTA_RECHERCHE,
    QUOTA_SANTE,
    cle_pour_limitation,
    identifiant_incident,
    verifier_cle,
)

logger = logging.getLogger(__name__)

VERSION_API = "1.0.0"

limiteur = Limiter(key_func=cle_pour_limitation)


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    """
    Prépare le service au démarrage et le referme proprement.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C20 (épreuve E5)

    Choix : la sonde de monitorage est branchée explicitement ici. Motivation :
    elle l'est déjà par `AppConfig.ready()` de l'application des agents, que
    `django.setup()` déclenche — mais s'appuyer sur cet effet de bord rendrait
    le monitorage du service IA dépendant d'un détail d'initialisation de
    Django. L'appel est idempotent ; le rendre explicite le rend vérifiable.
    """
    from apps.monitoring.journal import journal
    from apps.monitoring.sondes import installer

    branchee = installer()
    journal.ecrire({
        "type": "demarrage_service_ia",
        "message": "API du service IA démarrée.",
        "processus": os.getpid(),
        "sonde_branchee": branchee,
        "version_api": VERSION_API,
    })
    logger.info(
        "Service IA démarré — sonde de monitorage %s",
        "branchée" if branchee else "NON branchée",
    )
    yield
    journal.ecrire({
        "type": "arret_service_ia",
        "message": "API du service IA arrêtée.",
        "processus": os.getpid(),
    })


application = FastAPI(
    title="EduAI Tutor — API du service IA",
    version=VERSION_API,
    description=(
        "API REST exposant le service d'intelligence artificielle du projet "
        "(Bloc 2, compétence C9).\n\n"
        "Elle est **distincte de l'API du jeu de données** (C5), servie par "
        "Django REST Framework sous le préfixe `/api/dataset/`. Les deux "
        "périmètres ne partagent ni leur framework, ni leur processus, ni leur "
        "modèle de menace : celle-ci ne lit pas un corpus, elle **dépense** — "
        "chaque appel déclenche un appel facturé au fournisseur de modèles.\n\n"
        "**Authentification.** Toutes les routes de `/ai/` exigent l'en-tête "
        "`X-Cle-Service`, sauf `/ai/sante`, qui doit rester interrogeable par "
        "un orchestrateur sans lui confier de secret.\n\n"
        "**Quotas.** La génération est plafonnée plus bas que la recherche : "
        "la première appelle le fournisseur, la seconde n'interroge que le "
        "vector store local.\n\n"
        "**Monitorage.** Chaque appel est tracé — agent, modèle, latence, "
        "jetons, coût estimé — dans le journal JSON Lines du projet et dans "
        "les métriques Prometheus."
    ),
    docs_url="/ai/docs",
    redoc_url="/ai/redoc",
    openapi_url="/ai/openapi.json",
    lifespan=cycle_de_vie,
)
application.state.limiter = limiteur
application.add_middleware(SlowAPIMiddleware)


# --- Traitement des erreurs ---

@application.exception_handler(RateLimitExceeded)
async def quota_depasse(request: Request, exception: RateLimitExceeded):
    """
    Répond à un dépassement de quota.

    Compétence visée : C9 (épreuve E2) — OWASP API4
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErreurAPI(
            detail=(
                "Quota dépassé. Cette API déclenche des appels facturés au "
                "fournisseur de modèles ; le plafond protège le service et le "
                "budget de l'organisme."
            ),
            code="quota_depasse",
        ).model_dump(),
    )


@application.exception_handler(QuotaDepasse)
async def plafond_journalier_atteint(request: Request, exception: QuotaDepasse):
    """
    Répond quand le plafond global de générations du jour est atteint.

    Compétence visée : C9 (épreuve E2) — OWASP API4
    Compétence visée : C13 (épreuve E3) — maîtrise du coût

    Choix : 429 comme pour le débit, et non 503. Motivation : 503 annoncerait
    une panne, et inviterait le client à réessayer aussitôt. Le service n'est
    pas en panne : il a atteint une limite volontaire, et rien ne changera
    avant demain.

    Choix : ce plafond est distinct du débit par clé traité au-dessus. Le débit
    borne la cadence d'un consommateur, ce plafond borne le volume du jour tous
    consommateurs confondus — application web comprise. Les deux peuvent se
    déclencher séparément, et le message dit lequel.
    """
    logger.warning("Plafond journalier de générations atteint : %s", exception.message)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErreurAPI(
            detail=exception.message,
            code="plafond_journalier_atteint",
        ).model_dump(),
    )


@application.exception_handler(agents.ServiceIndisponible)
async def service_indisponible(request: Request, exception: agents.ServiceIndisponible):
    """
    Répond quand une dépendance du service est hors d'usage.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C21 (épreuve E5)
    """
    incident = identifiant_incident()
    logger.error("[%s] Dépendance indisponible : %s", incident, exception)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErreurAPI(
            detail="Une dépendance du service est momentanément indisponible.",
            code="dependance_indisponible",
            identifiant_incident=incident,
        ).model_dump(),
    )


@application.exception_handler(Exception)
async def erreur_inattendue(request: Request, exception: Exception):
    """
    Filet de dernier recours.

    Compétence visée : C9 (épreuve E2) — OWASP API8
    Compétence visée : C21 (épreuve E5)

    Choix : la trace part au journal de monitorage, l'appelant ne reçoit qu'un
    identifiant. Motivation : une trace renvoyée au client expose les chemins
    du serveur, les versions des bibliothèques et parfois des valeurs de
    configuration. L'identifiant permet de retrouver la trace complète côté
    service, ce qui donne le diagnostic sans la divulgation.
    """
    import traceback

    from apps.monitoring.journal import journal, tronquer_trace

    incident = identifiant_incident()
    journal.ecrire({
        "type": "erreur_api_ia",
        "identifiant_incident": incident,
        "chemin": request.url.path,
        "erreur_classe": type(exception).__name__,
        "erreur_message": str(exception)[:500],
        "trace": tronquer_trace("".join(traceback.format_exception(
            type(exception), exception, exception.__traceback__,
        ))),
    })
    logger.exception("[%s] Erreur inattendue sur %s", incident, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErreurAPI(
            detail="Erreur interne du service.",
            code="erreur_interne",
            identifiant_incident=incident,
        ).model_dump(),
    )


# --- Points de terminaison de génération ---

@application.post(
    "/ai/cours",
    response_model=ReponseGeneration,
    summary="Générer un cours",
    description=(
        "Produit un cours sur le sujet demandé, adapté au niveau indiqué. "
        "Le contexte est enrichi par le corpus quand celui-ci est disponible ; "
        "`fragments_utilises` dit combien de fragments ont réellement servi."
    ),
    tags=["Génération"],
    dependencies=[Depends(verifier_cle)],
)
@limiteur.limit(QUOTA_GENERATION)
async def generer_cours(request: Request, demande: DemandeCours) -> ReponseGeneration:
    """
    Génère un cours.

    Compétence visée : C9 (épreuve E2)
    """
    resultat = await agents.generer_cours(demande.sujet, demande.difficulte.value)
    return ReponseGeneration(**resultat)


@application.post(
    "/ai/explication",
    response_model=ReponseGeneration,
    summary="Réexpliquer une notion",
    description=(
        "Réexplique une notion autrement qu'un cours, avec un exemple concret. "
        "`niveau_apprenant` décrit l'apprenant et non le contenu : c'est lui "
        "qui décide de l'angle."
    ),
    tags=["Génération"],
    dependencies=[Depends(verifier_cle)],
)
@limiteur.limit(QUOTA_GENERATION)
async def expliquer(request: Request, demande: DemandeExplication) -> ReponseGeneration:
    """
    Réexplique une notion.

    Compétence visée : C9 (épreuve E2)
    """
    resultat = await agents.expliquer(
        demande.notion, demande.niveau_apprenant.value,
    )
    return ReponseGeneration(**resultat)


@application.post(
    "/ai/exercice",
    response_model=ReponseGeneration,
    summary="Générer un exercice",
    tags=["Génération"],
    dependencies=[Depends(verifier_cle)],
)
@limiteur.limit(QUOTA_GENERATION)
async def generer_exercice(request: Request,
                           demande: DemandeExercice) -> ReponseGeneration:
    """
    Génère un exercice de code.

    Compétence visée : C9 (épreuve E2)
    """
    resultat = await agents.generer_exercice(
        demande.sujet, demande.nombre_questions,
    )
    return ReponseGeneration(**resultat)


@application.post(
    "/ai/feedback",
    response_model=ReponseGeneration,
    summary="Retour sur une soumission de code",
    description=(
        "Produit un retour bref et actionnable sur du code soumis.\n\n"
        "**Aucun identifiant d'apprenant n'est accepté par ce point de "
        "terminaison** : le retour porte sur du code, pas sur une personne. "
        "Ce qui n'est pas reçu ne peut pas être transmis au fournisseur."
    ),
    tags=["Génération"],
    dependencies=[Depends(verifier_cle)],
)
@limiteur.limit(QUOTA_GENERATION)
async def donner_feedback(request: Request,
                          demande: DemandeFeedback) -> ReponseGeneration:
    """
    Produit un retour sur une soumission.

    Compétence visée : C9 (épreuve E2)
    """
    resultat = await agents.donner_feedback(
        demande.enonce, demande.code_soumis, demande.message_erreur,
    )
    return ReponseGeneration(**resultat)


# --- Recherche seule ---

@application.post(
    "/ai/recherche",
    response_model=ReponseRecherche,
    summary="Rechercher dans le corpus, sans génération",
    description=(
        "Interroge le corpus sans appeler de modèle de langage.\n\n"
        "Ce point de terminaison sert au diagnostic : quand une réponse est "
        "mauvaise, il permet de trancher entre un mauvais contexte et une "
        "mauvaise synthèse. Sans lui, les deux causes se confondent."
    ),
    tags=["Recherche"],
    dependencies=[Depends(verifier_cle)],
)
@limiteur.limit(QUOTA_RECHERCHE)
async def rechercher(request: Request,
                     demande: DemandeRecherche) -> ReponseRecherche:
    """
    Recherche dans le corpus.

    Compétence visée : C9 (épreuve E2)
    """
    resultat = await agents.rechercher(demande.requete, demande.nombre_fragments)
    fragments = [
        FragmentRAG(
            extrait=(getattr(f, "page_content", "") or "")[:2000],
            source=(getattr(f, "metadata", {}) or {}).get("source_url")
            or (getattr(f, "metadata", {}) or {}).get("source"),
            metadonnees=getattr(f, "metadata", {}) or {},
        )
        for f in resultat["fragments"]
    ]
    return ReponseRecherche(
        requete=demande.requete,
        fragments_demandes=demande.nombre_fragments,
        fragments_rendus=len(fragments),
        fragments=fragments,
        latence_secondes=resultat["latence_secondes"],
    )


# --- Santé ---

@application.get(
    "/ai/sante",
    response_model=ReponseSante,
    summary="État du service",
    description=(
        "État constatable localement : agents disponibles, routage des "
        "modèles, corpus, sonde de monitorage.\n\n"
        "**Cette sonde n'appelle pas le fournisseur.** Un appel réel serait "
        "facturé, et une sonde interrogée toutes les quinze secondes coûterait "
        "plus que le service. `disponibilite_fournisseur` dit donc si le "
        "fournisseur est *configuré*, pas s'il *répond* — l'état réel se lit "
        "dans les métriques, où les codes de retour des appels effectifs sont "
        "comptés."
    ),
    tags=["Exploitation"],
)
@limiteur.limit(QUOTA_SANTE)
async def sante(request: Request) -> ReponseSante:
    """
    Rend l'état du service.

    Compétence visée : C9 (épreuve E2)
    Compétence visée : C20 (épreuve E5)

    Choix : ce point de terminaison n'exige pas de clé. Motivation : une sonde
    de santé est interrogée par un orchestrateur, un équilibreur ou un
    superviseur, auxquels on ne confie pas un secret d'appel. Elle ne divulgue
    que des noms de modèles et des décomptes, jamais de contenu.
    """
    from apps.agents.tools.model_config import AGENTS_CONNUS, get_model_for
    from apps.monitoring.journal import journal
    from apps.monitoring.sondes import sonde

    routage = {agent: get_model_for(agent) for agent in AGENTS_CONNUS}

    fournisseurs = [
        EtatFournisseur(
            nom="groq",
            configure=bool(os.environ.get("GROQ_API_KEY")),
            detail=(
                "Clé présente dans l'environnement."
                if os.environ.get("GROQ_API_KEY")
                else "Aucune clé : le service basculerait sur le repli local."
            ),
        ),
        EtatFournisseur(
            nom="ollama",
            configure=bool(os.environ.get("OLLAMA_BASE_URL")),
            detail=os.environ.get("OLLAMA_BASE_URL")
            or "Adresse non configurée ; repli local indisponible.",
        ),
    ]

    chemin_corpus = Path("apps/rag/chroma")
    corpus = {
        "present": chemin_corpus.is_dir(),
        "chemin": str(chemin_corpus),
        # Le nom était écrit en dur et désignait l'autre collection : la sonde
        # annonçait donc un corpus que la recherche n'interroge pas. Une sonde
        # qui décrit autre chose que le service rendu est pire qu'une absence
        # de sonde — le projet en a documenté le cas (incident 003).
        "collection": COLLECTION_DOCUMENTAIRE,
    }

    verification = journal.verifier()
    monitorage = {
        "journal": verification["fichier"],
        "evenements_emis": verification["evenements_emis"],
        "lignes_ecrites_sur_disque": verification["lignes_valides_sur_disque"],
        "echecs_ecriture": verification["echecs_ecriture_signales"],
        "echecs_sonde": sonde.echecs_sonde,
    }

    # Le statut découle de ce qui est constaté, jamais déclaré d'avance.
    aucun_fournisseur = not any(f.configure for f in fournisseurs)
    if aucun_fournisseur:
        statut = "indisponible"
    elif not corpus["present"] or verification["echecs_ecriture_signales"]:
        statut = "degrade"
    else:
        statut = "operationnel"

    return ReponseSante(
        statut=statut,
        version_api=VERSION_API,
        agents_disponibles=list(AGENTS_CONNUS),
        routage_modeles=routage,
        disponibilite_fournisseur=fournisseurs,
        corpus_rag=corpus,
        monitorage=monitorage,
    )
