"""
Sondes d'instrumentation du service IA.

Compétence visée : C20 (épreuve E5) — monitorage du service en production

Ce module branche une sonde sur le mécanisme de rappels de LangChain. Elle
observe :

  - chaque appel au fournisseur de modèles : agent, modèle, latence, jetons
    d'entrée et de sortie, issue, coût estimé ;
  - chaque recherche RAG : nombre de fragments réellement rendus, latence ;
  - chaque erreur, avec sa trace tronquée.

Choix : un rappel enregistré globalement plutôt qu'une modification de chaque
site d'appel. Motivation : le projet compte une vingtaine d'appels `invoke`
répartis dans quatre agents et un orchestrateur. Les instrumenter un par un
garantirait d'en oublier — et un monitorage qui couvre quatre appels sur cinq
donne une confiance qu'il ne mérite pas. Le point d'accroche global de
LangChain, celui-là même qu'utilise LangSmith, couvre par construction les
appels existants et ceux qui seront écrits demain.

Choix : la sonde ne mesure que des effets. Motivation : les quatre incidents du
projet partagent le même motif, un rapport de succès qui ne correspond à rien.
La sonde ne consigne donc pas « une recherche a été demandée avec k = 5 » mais
« la recherche a rendu 3 fragments ». Le paramètre demandé est une intention, le
nombre rendu est un effet. Quand les deux diffèrent, c'est précisément le
symptôme qu'on veut voir.
"""

from __future__ import annotations

import logging
import os
import threading
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from . import metriques
from .alertes import surveillance
from .couts import estimer
from .journal import journal, tronquer_trace

logger = logging.getLogger(__name__)

#: Agent courant, renseigné par les agents qui le déclarent.
#:
#: Choix : une variable de contexte plutôt qu'un paramètre transmis d'appel en
#: appel. Motivation : la chaîne d'appel traverse LangChain, qui ne transporte
#: pas nos arguments. La variable de contexte suit le fil d'exécution et la
#: tâche asynchrone, sans rien imposer aux signatures.
agent_courant: ContextVar[str] = ContextVar("agent_courant", default="inconnu")


def _fournisseur(nom_modele: str, classe: str) -> str:
    """
    Déduit le fournisseur d'un appel.

    Compétence visée : C20 (épreuve E5)

    Le fournisseur détermine s'il y a un coût : un modèle servi par Ollama
    tourne sur la machine et ne facture rien. La distinction se lit dans la
    classe du client LangChain, pas dans le nom du modèle — le même nom peut
    être servi par les deux.
    """
    classe = (classe or "").lower()
    if "groq" in classe:
        return "groq"
    if "ollama" in classe:
        return "ollama"
    return "inconnu"


class SondeServiceIA(BaseCallbackHandler):
    """
    Rappel LangChain consignant appels de modèles et recherches RAG.

    Compétence visée : C20 (épreuve E5)

    Choix : la sonde n'échoue jamais vers l'appelant. Motivation : une erreur
    dans le monitorage ferait tomber le service qu'il observe, ce qui est
    l'inverse de son objet. Toute exception est rattrapée, journalisée par le
    module `logging`, et comptée.

    Choix : mais les échecs de la sonde sont comptés et exposés. Motivation :
    avaler une erreur sans la compter reproduirait le motif que ce module
    existe pour détecter.
    """

    #: Nombre d'exceptions rattrapées dans la sonde elle-même.
    echecs_sonde = 0

    def __init__(self) -> None:
        super().__init__()
        # Instants de départ, par identifiant d'exécution LangChain.
        self._departs: dict[UUID, float] = {}
        self._contextes: dict[UUID, dict[str, Any]] = {}
        self._verrou = threading.Lock()

    # --- Appels au fournisseur de modèles ---

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str],
                     *, run_id: UUID, **extra: Any) -> None:
        self._demarrer(run_id, {
            "type": "appel_llm",
            "agent": agent_courant.get(),
            "modele": self._modele(serialized, extra),
            "fournisseur": _fournisseur(
                self._modele(serialized, extra), self._classe(serialized),
            ),
            # Longueur du prompt, pas son contenu : le prompt peut contenir du
            # code d'apprenant. Le journal de monitorage n'a pas à en conserver
            # une copie — voir docs/rgpd_eduai_data.md sur la minimisation.
            "longueur_prompt": sum(len(p or "") for p in (prompts or [])),
        })

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any,
                            *, run_id: UUID, **extra: Any) -> None:
        """
        Même traitement pour les modèles de conversation.

        Compétence visée : C20 (épreuve E5)

        `ChatGroq` et `ChatOllama` passent par ce rappel et non par
        `on_llm_start`. Ne brancher que le second aurait laissé la totalité des
        appels du projet hors du monitorage — l'erreur est facile à commettre et
        indétectable sans vérification.
        """
        longueur = 0
        try:
            for groupe in messages or []:
                for message in groupe or []:
                    longueur += len(str(getattr(message, "content", "")))
        except Exception:  # noqa: BLE001 — mesure accessoire, jamais bloquante
            longueur = -1

        self._demarrer(run_id, {
            "type": "appel_llm",
            "agent": agent_courant.get(),
            "modele": self._modele(serialized, extra),
            "fournisseur": _fournisseur(
                self._modele(serialized, extra), self._classe(serialized),
            ),
            "longueur_prompt": longueur,
        })

    def on_llm_end(self, response: Any, *, run_id: UUID, **extra: Any) -> None:
        try:
            base, latence = self._terminer(run_id)
            if base is None:
                return

            jetons = self._jetons(response)
            modele = jetons.pop("modele_rapporte", None) or base.get("modele")
            base["modele"] = modele

            evenement = {
                **base,
                "issue": "succes",
                "latence_secondes": latence,
                **jetons,
                # Nombre de réponses réellement rendues : un appel peut aboutir
                # en ne produisant rien, et c'est le cas qu'on veut voir.
                "reponses_rendues": self._compter_reponses(response),
            }

            if base.get("fournisseur") == "ollama":
                evenement.update({
                    "cout_estime": 0.0,
                    "devise": None,
                    "tarif_a_verifier": False,
                    "motif_sans_cout": None,
                    "commentaire_cout": "modele local, aucun coût fournisseur",
                })
            else:
                evenement.update(estimer(
                    modele, jetons.get("jetons_entree"), jetons.get("jetons_sortie"),
                ))

            journal.ecrire(evenement)
            self._compter_appel(evenement, latence)
            surveillance.enregistrer(
                en_erreur=False, latence=latence,
                contexte={"agent": base.get("agent"), "modele": modele,
                          "origine": "appel_llm"},
            )
        except Exception as exception:  # noqa: BLE001 — la sonde ne casse rien
            self._echec("on_llm_end", exception)

    def on_llm_error(self, error: BaseException, *, run_id: UUID,
                     **extra: Any) -> None:
        try:
            base, latence = self._terminer(run_id)
            base = base or {"type": "appel_llm", "agent": agent_courant.get()}

            evenement = {
                **base,
                "issue": "erreur",
                "latence_secondes": latence,
                "erreur_classe": type(error).__name__,
                "erreur_message": str(error)[:500],
                # Le code de retour du fournisseur, quand il est exposé : c'est
                # lui qui distingue un quota atteint d'un modèle retiré du
                # catalogue — la panne qu'a connue ce projet le 25/08.
                "code_retour": self._code_retour(error),
                "trace": tronquer_trace("".join(traceback.format_exception(
                    type(error), error, error.__traceback__,
                ))),
            }
            journal.ecrire(evenement)
            self._compter_appel(evenement, latence)
            surveillance.enregistrer(
                en_erreur=True, latence=latence,
                contexte={"agent": base.get("agent"),
                          "modele": base.get("modele"),
                          "origine": "appel_llm"},
            )
        except Exception as exception:  # noqa: BLE001
            self._echec("on_llm_error", exception)

    # --- Recherches dans le vector store ---

    def on_retriever_start(self, serialized: dict[str, Any], query: str,
                           *, run_id: UUID, **extra: Any) -> None:
        self._demarrer(run_id, {
            "type": "recherche_rag",
            "agent": agent_courant.get(),
            # Longueur de la requête, pas son texte : une question d'apprenant
            # peut être identifiante.
            "longueur_requete": len(query or ""),
        })

    def on_retriever_end(self, documents: Any, *, run_id: UUID,
                         **extra: Any) -> None:
        try:
            base, latence = self._terminer(run_id)
            if base is None:
                return

            fragments = list(documents or [])
            self._compter_recherche(base.get("agent"), "succes", latence,
                                    len(fragments))
            journal.ecrire({
                **base,
                "issue": "succes",
                "latence_secondes": latence,
                # Le nombre RENDU, jamais le k demandé. Une recherche qui
                # rend zéro fragment aboutit sans erreur et prive pourtant
                # l'agent de tout contexte : c'est le genre de succès vide que
                # ce projet a appris à ne pas croire.
                "fragments_rendus": len(fragments),
                "longueur_totale_fragments": sum(
                    len(getattr(f, "page_content", "") or "") for f in fragments
                ),
            })
            if not fragments:
                surveillance.enregistrer(
                    en_erreur=False, latence=latence,
                    contexte={"agent": base.get("agent"),
                              "origine": "recherche_rag_vide"},
                )
        except Exception as exception:  # noqa: BLE001
            self._echec("on_retriever_end", exception)

    def on_retriever_error(self, error: BaseException, *, run_id: UUID,
                           **extra: Any) -> None:
        try:
            base, latence = self._terminer(run_id)
            base = base or {"type": "recherche_rag", "agent": agent_courant.get()}
            self._compter_recherche(base.get("agent"), "erreur", latence, None)
            journal.ecrire({
                **base,
                "issue": "erreur",
                "latence_secondes": latence,
                "erreur_classe": type(error).__name__,
                "erreur_message": str(error)[:500],
                "trace": tronquer_trace("".join(traceback.format_exception(
                    type(error), error, error.__traceback__,
                ))),
            })
            surveillance.enregistrer(
                en_erreur=True, latence=latence,
                contexte={"agent": base.get("agent"), "origine": "recherche_rag"},
            )
        except Exception as exception:  # noqa: BLE001
            self._echec("on_retriever_error", exception)

    # --- Alimentation des métriques Prometheus ---

    @staticmethod
    def _compter_appel(evenement: dict[str, Any], latence: float | None) -> None:
        """
        Reporte un appel de modèle dans les métriques agrégées.

        Compétence visée : C20 (épreuve E5)

        Choix : les étiquettes sont toutes de cardinalité bornée — agent,
        modèle, fournisseur, issue, code de retour, classe d'exception.
        Motivation : Prometheus crée une série temporelle par combinaison
        d'étiquettes. Y mettre un identifiant de requête ou un message d'erreur
        ferait exploser le nombre de séries et rendrait la base inutilisable en
        quelques heures. Le détail variable appartient au JSON Lines, qui n'a
        pas cette contrainte — c'est l'une des raisons d'avoir les deux.
        """
        try:
            agent = evenement.get("agent") or "inconnu"
            modele = evenement.get("modele") or "inconnu"
            issue = evenement.get("issue") or "inconnue"

            metriques.appels_llm.labels(
                agent=agent, modele=modele,
                fournisseur=evenement.get("fournisseur") or "inconnu",
                issue=issue,
            ).inc()

            if latence is not None:
                metriques.latence_llm.labels(agent=agent, modele=modele).observe(latence)

            if issue == "erreur":
                metriques.erreurs_llm.labels(
                    agent=agent, modele=modele,
                    code_retour=str(evenement.get("code_retour") or "aucun"),
                    classe=evenement.get("erreur_classe") or "inconnue",
                ).inc()
                return

            for sens, cle in (("entree", "jetons_entree"), ("sortie", "jetons_sortie")):
                valeur = evenement.get(cle)
                if isinstance(valeur, int) and valeur > 0:
                    metriques.jetons.labels(
                        agent=agent, modele=modele, sens=sens,
                    ).inc(valeur)

            cout = evenement.get("cout_estime")
            if isinstance(cout, (int, float)) and cout > 0:
                metriques.cout_estime.labels(
                    modele=modele,
                    devise=evenement.get("devise") or "inconnue",
                    # Un coût reposant sur un tarif non confronté à la grille du
                    # fournisseur ne doit pas se confondre avec un coût établi.
                    tarif_verifie="non" if evenement.get("tarif_a_verifier") else "oui",
                ).inc(float(cout))
        except Exception as exception:  # noqa: BLE001
            logger.debug("[monitorage] métrique d'appel non reportée : %s", exception)

    @staticmethod
    def _compter_recherche(agent: str | None, issue: str, latence: float | None,
                           fragments: int | None) -> None:
        """
        Reporte une recherche RAG dans les métriques agrégées.

        Compétence visée : C20 (épreuve E5)

        `fragments` est le nombre RENDU. L'histogramme porte une borne à zéro
        pour isoler les recherches qui aboutissent sans rien rendre : un succès
        vide, que rien ne distingue d'un vrai succès dans un simple compteur.
        """
        try:
            agent = agent or "inconnu"
            metriques.recherches_rag.labels(agent=agent, issue=issue).inc()
            if latence is not None:
                metriques.latence_rag.labels(agent=agent).observe(latence)
            if fragments is not None:
                metriques.fragments_rendus.labels(agent=agent).observe(fragments)
        except Exception as exception:  # noqa: BLE001
            logger.debug("[monitorage] métrique de recherche non reportée : %s", exception)

    # --- Mécanique interne ---

    def _demarrer(self, run_id: UUID, contexte: dict[str, Any]) -> None:
        try:
            with self._verrou:
                self._departs[run_id] = _horloge()
                self._contextes[run_id] = contexte
        except Exception as exception:  # noqa: BLE001
            self._echec("_demarrer", exception)

    def _terminer(self, run_id: UUID) -> tuple[dict[str, Any] | None, float | None]:
        with self._verrou:
            depart = self._departs.pop(run_id, None)
            contexte = self._contextes.pop(run_id, None)
        latence = round(_horloge() - depart, 4) if depart is not None else None
        return contexte, latence

    @staticmethod
    def _classe(serialized: dict[str, Any]) -> str:
        chemin = (serialized or {}).get("id") or []
        return chemin[-1] if chemin else ""

    @staticmethod
    def _modele(serialized: dict[str, Any], extra: dict[str, Any]) -> str:
        """
        Retrouve le nom du modèle, quel que soit l'endroit où LangChain le range.

        Compétence visée : C20 (épreuve E5)

        Les clients ne s'accordent pas : `ChatGroq` expose `model_name`,
        `ChatOllama` expose `model`, et les métadonnées d'invocation peuvent
        porter l'un ou l'autre. Chercher aux quatre endroits coûte quelques
        lignes ; ne chercher qu'au premier produirait un journal où la moitié
        des appels sont attribués à un modèle « inconnu ».
        """
        params = (extra or {}).get("invocation_params") or {}
        kwargs = (serialized or {}).get("kwargs") or {}
        for source in (params, kwargs):
            for cle in ("model_name", "model", "model_id"):
                valeur = source.get(cle)
                if valeur:
                    return str(valeur)
        return "inconnu"

    @staticmethod
    def _jetons(response: Any) -> dict[str, Any]:
        """
        Extrait les jetons réellement facturés par le fournisseur.

        Compétence visée : C20 (épreuve E5)

        Choix : ne rien estimer si le fournisseur ne rapporte rien. Motivation :
        un décompte de jetons déduit d'une longueur de texte est une
        approximation à plus ou moins cinquante pour cent selon la langue. Mieux
        vaut un champ nul, qui se voit, qu'un chiffre plausible et faux.
        """
        sortie = (getattr(response, "llm_output", None) or {})
        usage = (
            sortie.get("token_usage")
            or sortie.get("usage")
            or {}
        )
        if not usage:
            # Certains clients ne renseignent l'usage que sur le message.
            try:
                message = response.generations[0][0].message
                usage = (getattr(message, "usage_metadata", None)
                         or (getattr(message, "response_metadata", {}) or {})
                         .get("token_usage") or {})
            except Exception:  # noqa: BLE001 — champ optionnel
                usage = {}

        return {
            "jetons_entree": usage.get("prompt_tokens") or usage.get("input_tokens"),
            "jetons_sortie": usage.get("completion_tokens") or usage.get("output_tokens"),
            "jetons_total": usage.get("total_tokens"),
            "modele_rapporte": sortie.get("model_name") or sortie.get("model"),
        }

    @staticmethod
    def _compter_reponses(response: Any) -> int:
        try:
            return sum(len(groupe) for groupe in (response.generations or []))
        except Exception:  # noqa: BLE001
            return -1

    @staticmethod
    def _code_retour(error: BaseException) -> Any:
        """
        Retrouve le code de retour HTTP d'une erreur de fournisseur.

        Compétence visée : C20 (épreuve E5)
        Compétence visée : C21 (épreuve E5)

        Un 429 est un quota atteint, un 404 un modèle retiré du catalogue, un
        503 une indisponibilité passagère. Les trois appellent des réactions
        différentes, et le projet a déjà connu la deuxième : un modèle codé en
        dur retiré par Groq (voir docs/decisions/001).
        """
        for attribut in ("status_code", "http_status", "code"):
            valeur = getattr(error, attribut, None)
            if valeur is not None:
                return valeur
        reponse = getattr(error, "response", None)
        return getattr(reponse, "status_code", None) if reponse is not None else None

    def _echec(self, methode: str, exception: BaseException) -> None:
        type(self).echecs_sonde += 1
        try:
            metriques.echecs_sonde.labels(methode=methode).inc()
        except Exception:  # noqa: BLE001
            pass
        logger.warning(
            "[monitorage] sonde %s en échec (%s : %s) — %d échec(s) cumulé(s). "
            "Le service n'est pas affecté, la trace de cet appel est perdue.",
            methode, type(exception).__name__, exception, type(self).echecs_sonde,
        )


def _horloge() -> float:
    """
    Horloge monotone pour la mesure de durée.

    Compétence visée : C20 (épreuve E5)

    Choix : `perf_counter` et non `time.time`. Motivation : une synchronisation
    d'horloge pendant un appel produirait avec `time.time` une latence négative
    ou aberrante. L'horloge monotone ne recule pas.
    """
    import time

    return time.perf_counter()


#: Sonde partagée par le processus.
sonde = SondeServiceIA()

#: Variable de contexte lue par le point d'accroche global de LangChain.
#:
#: Choix : la sonde est la VALEUR PAR DÉFAUT de la variable, et non une valeur
#: posée par `set()` au démarrage.
#:
#: Motivation : une variable de contexte posée par `set()` n'est visible que
#: dans le contexte qui l'a posée et dans ceux qui en dérivent. Or chaque
#: requête HTTP s'exécute dans sa propre tâche asyncio — sous FastAPI — ou dans
#: son propre fil — sous WSGI. Aucune n'hérite du contexte du démarrage. La
#: sonde paraissait donc branchée, l'annonçait dans les journaux, et ne traçait
#: aucun appel de requête.
#:
#: Le défaut a été constaté sur le service IA : un appel de recherche aboutit
#: en erreur, la réponse HTTP est correcte, et rien n'apparaît au journal de
#: monitorage. C'est exactement le motif que ce paquet existe pour détecter —
#: un composant qui se déclare opérationnel sans produire d'effet.
#:
#: Une valeur par défaut, elle, est lue par tout contexte, quel que soit le fil
#: ou la tâche qui l'interroge.
_sonde_active: ContextVar[SondeServiceIA | None] = ContextVar(
    "sonde_monitorage", default=sonde,
)

_installee = False


def installer() -> bool:
    """
    Branche la sonde sur le mécanisme de rappels global de LangChain.

    Compétence visée : C20 (épreuve E5)

    Une fois installée, la sonde reçoit les rappels de tous les appels de
    modèles et de toutes les recherches, sans qu'aucun site d'appel n'ait à la
    connaître.

    Choix : le monitorage est actif par défaut et se coupe par variable
    d'environnement, non l'inverse. Motivation : un monitorage qu'il faut penser
    à activer n'est pas actif le jour de l'incident.

    Returns:
        True si la sonde est branchée, False sinon — auquel cas la raison est
        journalisée.
    """
    global _installee

    if _installee:
        return True

    if os.environ.get("MONITORAGE_ACTIF", "true").strip().lower() in ("0", "false", "non"):
        logger.info("[monitorage] désactivé par MONITORAGE_ACTIF.")
        return False

    try:
        from langchain_core.tracers.context import register_configure_hook
    except ImportError as exception:
        logger.error(
            "[monitorage] point d'accroche global indisponible dans cette "
            "version de langchain-core (%s) : les appels ne seront PAS "
            "instrumentés.", exception,
        )
        return False

    try:
        register_configure_hook(_sonde_active, inheritable=True)
        # Aucun `set()` : la sonde est déjà la valeur par défaut de la variable,
        # donc visible depuis tout fil et toute tâche. Un `set()` ici ne
        # porterait que sur le contexte du démarrage — voir le commentaire de
        # `_sonde_active`.
        _installee = True
        journal.ecrire({
            "type": "demarrage_monitorage",
            "message": "Sonde du service IA branchée sur les rappels LangChain.",
            "processus": os.getpid(),
            "fichier_journal": str(journal.fichier_du_jour()),
        })
        logger.info(
            "[monitorage] sonde branchée — journal : %s",
            journal.fichier_du_jour(),
        )
        return True
    except Exception as exception:  # noqa: BLE001
        logger.error(
            "[monitorage] branchement impossible (%s : %s) : les appels ne "
            "seront PAS instrumentés.", type(exception).__name__, exception,
        )
        return False


def sous_agent(nom: str):
    """
    Décorateur déclarant l'agent courant pour la durée d'une méthode.

    Compétence visée : C20 (épreuve E5)

    Usage :

        @sous_agent("pedagogue")
        def generate_course(self, topic): ...

    Choix : un décorateur plutôt qu'un bloc `with` autour du corps.
    Motivation : le bloc imposerait de réindenter des méthodes existantes de
    cinquante lignes, dans un code qui fonctionne et qu'on approche à dix jours
    du rendu. Le décorateur ajoute une ligne et n'en déplace aucune.
    """
    import functools

    def decorateur(fonction):
        @functools.wraps(fonction)
        def enveloppe(*args, **kwargs):
            with contexte_agent(nom):
                return fonction(*args, **kwargs)
        return enveloppe
    return decorateur


def contexte_agent(nom: str):
    """
    Déclare l'agent courant pour la durée d'un bloc.

    Compétence visée : C20 (épreuve E5)

    Usage :

        with contexte_agent("researcher"):
            resultat = chaine.invoke(question)

    Sans cette déclaration, les événements portent l'agent « inconnu ». Le
    monitorage reste exploitable — modèle, latence et jetons sont mesurés — mais
    la répartition par agent, qui est ce qui permet d'arbitrer le routage des
    modèles, manque.
    """
    from contextlib import contextmanager

    @contextmanager
    def _bloc():
        jeton = agent_courant.set(nom)
        try:
            yield
        finally:
            agent_courant.reset(jeton)

    return _bloc()
