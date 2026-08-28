"""
Exécution du protocole de comparaison de modèles.

Compétence visée : C7 (épreuve E2) — comparaison de services d'IA
Compétence visée : C20 (épreuve E5) — le monitorage existant sert de mesure

Le protocole est décrit dans docs/benchmark_modeles.md, écrit et commité AVANT
ce fichier. Ce module ne fait que l'appliquer : quatre modèles, dix prompts,
trois répétitions, appels séquentiels.

Choix : aucune sonde n'est écrite ici. Motivation : le projet dispose déjà d'un
monitorage qui trace agent, modèle, latence, jetons et coût pour tout appel
passant par LangChain. Ajouter un chronomètre propre au benchmark produirait des
chiffres impossibles à confronter à ceux de la production, et laisserait planer
le doute sur lequel des deux dit vrai.

Choix : le chronomètre local est tout de même relevé, à côté de celui de la
sonde. Motivation : ce n'est pas une redondance mais un contrôle. Ils mesurent
deux choses distinctes — la sonde mesure le temps du fournisseur, l'appelant
mesure le temps qu'il a réellement attendu. Un écart entre les deux se lit, et
si la sonde ne produit aucune ligne, l'écart devient infini et le signale. C'est
la leçon de l'incident 003 : une sonde annoncée branchée qui ne traçait rien
pendant vingt-deux heures. Ici, l'absence de trace est un résultat consigné,
pas un silence.

Sortie : data_pipeline/data/benchmark/
  - mesures.jsonl   une ligne par appel, mesures et métadonnées
  - reponses.jsonl  une ligne par appel, le texte produit
  - monitorage/     le journal brut de la sonde, isolé de celui de production

--- Point de lancement ---
    uv run python -m benchmark.executer [--modeles ...] [--repetitions N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# --- 1. Initialisation des dépendances et connexions externes -------------

#: Répertoire de sortie du benchmark.
#:
#: Choix : un journal de monitorage séparé de celui de production. Motivation :
#: cent vingt appels artificiels versés dans le journal du service fausseraient
#: les taux d'erreur et les latences médianes qu'on y observe. Le benchmark
#: mesure un banc d'essai, pas un service en usage.
REPERTOIRE_SORTIE = Path("data_pipeline/data/benchmark")
REPERTOIRE_MONITORAGE = REPERTOIRE_SORTIE / "monitorage"

# La variable doit être posée AVANT l'import du journal : son répertoire est
# résolu une seule fois, à l'import du module.
REPERTOIRE_MONITORAGE.mkdir(parents=True, exist_ok=True)
os.environ["MONITORAGE_REPERTOIRE"] = str(REPERTOIRE_MONITORAGE)
os.environ.setdefault("MONITORAGE_ACTIF", "true")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apps.monitoring.journal import journal  # noqa: E402
from apps.monitoring.sondes import contexte_agent, installer  # noqa: E402
from benchmark.prompts import (  # noqa: E402
    JETONS_SORTIE_MAX,
    MODELES,
    PROMPTS,
    REPETITIONS,
    TEMPERATURE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("benchmark")

#: Délai entre deux appels, en secondes.
#:
#: Choix : une pause explicite plutôt qu'un enchaînement au plus vite.
#: Motivation : Groq applique une limite de débit par minute. Sans pause, une
#: partie des mesures serait des refus 429, et les latences relevées
#: mélangeraient le temps du modèle et le temps d'attente d'un quota. On
#: mesurerait alors la limite tarifaire, pas le modèle.
#:
#: La valeur vient d'une mesure : à 0,5 seconde, un essai sur les dix prompts a
#: produit trois refus 429 sur les trois derniers appels. Six secondes tiennent
#: la cadence sous la limite de jetons par minute du palier gratuit.
PAUSE_ENTRE_APPELS = 6.0

#: Attente après un refus pour dépassement de quota, en secondes.
#:
#: Choix : attendre le renouvellement de la fenêtre plutôt que de réessayer
#: aussitôt. Motivation : les limites de Groq se renouvellent à la minute ;
#: réessayer plus tôt ne ferait que consommer une tentative de plus.
ATTENTE_APRES_QUOTA = 65.0

#: Tentatives maximales sur un même appel après refus pour quota.
TENTATIVES_MAX = 3


def est_un_refus_de_quota(exception: BaseException) -> bool:
    """
    Reconnaît un refus pour dépassement de limite de débit.

    Compétence visée : C7 (épreuve E2)

    Choix : reconnaître le cas sur le code 429 et non sur le texte du message.
    Motivation : le texte change d'un fournisseur à l'autre et d'une version à
    l'autre ; le code de statut, lui, est normalisé. Le message n'est consulté
    qu'en second recours, quand aucun code n'est exposé.
    """
    for attribut in ("status_code", "code", "http_status"):
        if getattr(exception, attribut, None) == 429:
            return True
    reponse = getattr(exception, "response", None)
    if getattr(reponse, "status_code", None) == 429:
        return True
    return "429" in str(exception) or "rate limit" in str(exception).lower()


def construire_client(modele: dict[str, str], jetons_max: int = JETONS_SORTIE_MAX):
    """
    Instancie le client de conversation d'un modèle, fournisseur par fournisseur.

    Compétence visée : C7 (épreuve E2)

    Choix : ne pas passer par `apps.agents.tools.llm_loader.get_llm`.
    Motivation : ce chargeur route sur la PRÉSENCE de la clé Groq, pas sur le
    modèle demandé — avec une clé configurée, il enverrait `qwen3:4b` à Groq,
    qui ne le connaît pas. Le benchmark a besoin de choisir son fournisseur
    explicitement. Le chargeur n'est pas modifié pour autant : il convient à
    l'usage de l'application, où un seul fournisseur sert à la fois.

    Choix : température et plafond de jetons imposés ici, identiques pour tous.
    Motivation : les défauts diffèrent d'un fournisseur à l'autre, et une
    comparaison dont les paramètres varient ne compare rien.

    Choix : `max_retries=0`, c'est-à-dire les tentatives automatiques du client
    DÉSACTIVÉES. Motivation : c'est le point qui décide de la validité des
    mesures. Le client Groq réessaie de lui-même après un refus 429, en
    patientant plusieurs secondes — et cette attente tombe **à l'intérieur** de
    l'appel chronométré, aussi bien par la sonde que par l'appelant. Un essai a
    ainsi relevé 5,99 secondes pour un appel dont le modèle n'a consommé qu'une
    fraction : le reste était de l'attente de quota. La mesure aurait décrit le
    palier tarifaire du compte, pas le modèle. Le refus est donc laissé remonter,
    et l'appel entier est rejoué par le protocole, mesure comprise.
    """
    if modele["fournisseur"] == "groq":
        from langchain_groq import ChatGroq

        cle = os.getenv("GROQ_API_KEY")
        if not cle:
            raise RuntimeError("GROQ_API_KEY absente de l'environnement")
        return ChatGroq(
            model_name=modele["nom"],
            api_key=cle,
            temperature=TEMPERATURE,
            max_tokens=jetons_max,
            max_retries=0,
        )

    if modele["fournisseur"] == "ollama":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=modele["nom"],
            temperature=TEMPERATURE,
            num_predict=jetons_max,
        )

    raise ValueError(f"fournisseur inconnu : {modele['fournisseur']}")


# --- 2. Règles logiques de traitement -------------------------------------

def derniere_trace_llm(depuis_ligne: int) -> tuple[dict | None, int]:
    """
    Relit le journal de la sonde et rend la trace d'appel produite depuis un point.

    Compétence visée : C20 (épreuve E5)

    Choix : relire le fichier plutôt qu'interroger un compteur en mémoire.
    Motivation : c'est la règle que le projet applique depuis l'incident de
    chargement — un composant rapporte son effet, pas son intention. Une trace
    qu'on croit écrite et qui n'est pas sur le disque n'existe pas.

    Renvoie la dernière trace de type `appel_llm` trouvée au-delà de
    `depuis_ligne`, et le nombre total de lignes du fichier.
    """
    chemin = journal.fichier_du_jour()
    if not chemin.is_file():
        return None, 0

    lignes = chemin.read_text(encoding="utf-8").splitlines()
    trace = None
    for ligne in lignes[depuis_ligne:]:
        if not ligne.strip():
            continue
        try:
            evenement = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if evenement.get("type") == "appel_llm" and "issue" in evenement:
            trace = evenement
    return trace, len(lignes)


def executer_un_appel(client, modele, prompt, repetition, curseur):
    """
    Passe un appel, relève les deux mesures et rend une ligne de résultat.

    Compétence visée : C7 (épreuve E2)

    La latence de l'appelant et celle de la sonde sont consignées côte à côte.
    Elles ne mesurent pas la même chose et leur écart est une information.

    Choix : un refus pour quota fait rejouer l'appel ENTIER, chronomètre remis à
    zéro, plutôt que de conserver la mesure obtenue après attente. Motivation :
    une latence qui contient une attente de quota ne mesure pas le modèle. Le
    nombre de tentatives écartées est consigné dans `tentatives` — l'information
    n'est pas perdue, elle est simplement sortie de la latence.
    """
    ligne = {
        "horodatage": datetime.now(timezone.utc).isoformat(),
        "modele": modele["nom"],
        "fournisseur": modele["fournisseur"],
        "prompt": prompt.identifiant,
        "agent": prompt.agent,
        "intitule": prompt.intitule,
        "repetition": repetition,
        "tentatives": 0,
    }
    texte = None

    for tentative in range(1, TENTATIVES_MAX + 1):
        ligne["tentatives"] = tentative
        debut = time.perf_counter()
        try:
            # Le contexte d'agent est ce qui permet à la sonde d'attribuer
            # l'appel : sans lui, toutes les traces porteraient « inconnu ».
            with contexte_agent(prompt.agent):
                reponse = client.invoke(prompt.texte)
            texte = getattr(reponse, "content", str(reponse))
            ligne["issue"] = "succes"
            ligne["latence_appelant_secondes"] = round(time.perf_counter() - debut, 4)
            break

        # --- 3. Gestion des erreurs et exceptions -------------------------
        except KeyboardInterrupt:
            # Une interruption volontaire n'est pas un échec du modèle : on la
            # laisse remonter plutôt que de la consigner comme une mesure.
            raise

        except Exception as exception:  # noqa: BLE001
            ligne["latence_appelant_secondes"] = round(time.perf_counter() - debut, 4)

            if est_un_refus_de_quota(exception) and tentative < TENTATIVES_MAX:
                # Le cas prévu, et le seul qui donne lieu à un nouvel essai : la
                # mesure est jetée, pas conservée après attente.
                logger.warning(
                    "%s / %s : quota atteint (tentative %d/%d), mesure écartée, "
                    "attente de %.0f s",
                    modele["nom"], prompt.identifiant, tentative, TENTATIVES_MAX,
                    ATTENTE_APRES_QUOTA,
                )
                # La trace produite par la sonde pour l'appel refusé est sautée :
                # le curseur avance pour qu'elle ne soit pas prise pour la mesure.
                _, curseur = derniere_trace_llm(curseur)
                time.sleep(ATTENTE_APRES_QUOTA)
                continue

            # Tout le reste : modèle retiré du catalogue, réponse malformée,
            # service injoignable, ou quota persistant après trois tentatives. On
            # consigne la classe, qui distingue ces cas, et on poursuit le
            # protocole — interrompre les cent vingt appels sur un refus isolé
            # perdrait les mesures déjà acquises.
            ligne.update({
                "issue": "erreur",
                "erreur_classe": type(exception).__name__,
                "erreur_message": str(exception)[:300],
                "quota": est_un_refus_de_quota(exception),
            })
            logger.error("%s / %s : %s — %s", modele["nom"], prompt.identifiant,
                         type(exception).__name__, str(exception)[:200])
            break

    trace, curseur = derniere_trace_llm(curseur)
    if trace is None:
        # Le cas de l'incident 003, consigné plutôt que passé sous silence : la
        # sonde s'annonçait branchée et ne traçait rien.
        ligne.update({"trace_sonde": "absente", "latence_secondes": None,
                      "jetons_entree": None, "jetons_sortie": None,
                      "cout_estime": None})
        logger.warning("%s / %s : aucune trace de monitorage pour cet appel",
                       modele["nom"], prompt.identifiant)
    else:
        ligne.update({
            "trace_sonde": "presente",
            "latence_secondes": trace.get("latence_secondes"),
            "jetons_entree": trace.get("jetons_entree"),
            "jetons_sortie": trace.get("jetons_sortie"),
            "cout_estime": trace.get("cout_estime"),
            "devise": trace.get("devise"),
            "tarif_a_verifier": trace.get("tarif_a_verifier"),
            "modele_rapporte": trace.get("modele"),
        })

    return ligne, texte, curseur


# --- 4. Sauvegarde des résultats ------------------------------------------

def ecrire(chemin: Path, enregistrement: dict) -> None:
    """
    Ajoute une ligne JSON au fichier, immédiatement.

    Compétence visée : C7 (épreuve E2)

    Choix : écriture ligne à ligne plutôt qu'un dépôt final. Motivation : une
    campagne de cent vingt appels dure plusieurs minutes et peut être
    interrompue — quota, réseau, arrêt volontaire. Les mesures déjà obtenues
    doivent survivre à l'interruption.
    """
    with chemin.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")


def main() -> int:
    """
    Point de lancement du benchmark.

    Compétence visée : C7 (épreuve E2)
    """
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--modeles", nargs="*", default=None,
        help="restreindre aux modèles nommés (défaut : les quatre du protocole)",
    )
    analyseur.add_argument(
        "--repetitions", type=int, default=REPETITIONS,
        help=f"répétitions par couple modèle/prompt (défaut : {REPETITIONS})",
    )
    analyseur.add_argument(
        "--pause", type=float, default=PAUSE_ENTRE_APPELS,
        help="pause entre deux appels, en secondes",
    )
    analyseur.add_argument(
        "--jetons-max", type=int, default=JETONS_SORTIE_MAX,
        help=f"plafond de jetons de sortie (défaut du protocole : {JETONS_SORTIE_MAX})",
    )
    analyseur.add_argument(
        "--sortie", type=Path, default=REPERTOIRE_SORTIE,
        help="répertoire de sortie ; en changer permet une mesure complémentaire "
             "sans polluer les mesures du protocole",
    )
    options = analyseur.parse_args()

    modeles = [m for m in MODELES if not options.modeles or m["nom"] in options.modeles]
    if not modeles:
        logger.error("aucun modèle retenu ; connus : %s",
                     ", ".join(m["nom"] for m in MODELES))
        return 2

    if not installer():
        logger.error("la sonde de monitorage n'a pas pu être installée : "
                     "sans elle, aucune mesure de jetons n'est possible")
        return 3

    # Une mesure hors protocole doit écrire ailleurs, et le dire. Verser des
    # appels passés sous d'autres paramètres dans `mesures.jsonl` produirait un
    # tableau dont les lignes ne seraient plus comparables entre elles — sans
    # que rien ne le signale.
    options.sortie.mkdir(parents=True, exist_ok=True)
    fichier_mesures = options.sortie / "mesures.jsonl"
    fichier_reponses = options.sortie / "reponses.jsonl"
    if options.jetons_max != JETONS_SORTIE_MAX:
        logger.warning(
            "plafond de jetons %d au lieu de %d : ces mesures sont HORS "
            "PROTOCOLE et ne se comparent pas au tableau principal",
            options.jetons_max, JETONS_SORTIE_MAX,
        )

    attendus = len(modeles) * len(PROMPTS) * options.repetitions
    logger.info("début du benchmark : %d modèles × %d prompts × %d répétitions "
                "= %d appels", len(modeles), len(PROMPTS), options.repetitions,
                attendus)

    curseur = 0
    passes = 0
    reussis = 0
    indisponibles: list[str] = []

    for modele in modeles:
        try:
            client = construire_client(modele, options.jetons_max)
        except Exception as exception:  # noqa: BLE001
            # Un fournisseur injoignable retire son modèle du protocole sans
            # interrompre les autres. L'absence est consignée, pas déduite.
            logger.error("%s : client inconstructible (%s) — modèle NON MESURÉ",
                         modele["nom"], exception)
            indisponibles.append(modele["nom"])
            ecrire(fichier_mesures, {
                "modele": modele["nom"], "fournisseur": modele["fournisseur"],
                "issue": "non_mesure", "erreur_message": str(exception)[:300],
                "horodatage": datetime.now(timezone.utc).isoformat(),
            })
            continue

        logger.info("── %s (%s)", modele["nom"], modele["fournisseur"])
        for repetition in range(1, options.repetitions + 1):
            for prompt in PROMPTS:
                ligne, texte, curseur = executer_un_appel(
                    client, modele, prompt, repetition, curseur,
                )
                passes += 1
                if ligne["issue"] == "succes":
                    reussis += 1
                # Le plafond effectif est consigné dans chaque ligne : sans lui,
                # rien ne distinguerait sur le disque une mesure du protocole
                # d'une mesure complémentaire passée sous d'autres paramètres.
                ligne["jetons_max"] = options.jetons_max
                ecrire(fichier_mesures, ligne)
                if texte is not None:
                    ecrire(fichier_reponses, {
                        "modele": modele["nom"], "prompt": prompt.identifiant,
                        "repetition": repetition, "reponse": texte,
                    })
                logger.info(
                    "   %-22s %-4s rep%d  %s  %.2fs  %s jetons",
                    modele["nom"], prompt.identifiant, repetition,
                    ligne["issue"], ligne["latence_appelant_secondes"],
                    ligne.get("jetons_sortie"),
                )
                time.sleep(options.pause)

    logger.info("fin du benchmark : %d appels passés, %d réussis sur %d attendus",
                passes, reussis, attendus)
    if indisponibles:
        logger.warning("modèles NON MESURÉS : %s", ", ".join(indisponibles))
    logger.info("mesures : %s", fichier_mesures)
    logger.info("réponses : %s", fichier_reponses)

    verification = journal.verifier()
    logger.info("journal de la sonde : %d lignes valides, %d illisibles",
                verification["lignes_valides_sur_disque"],
                verification["lignes_illisibles"])

    # Un modèle indisponible n'est pas un échec du benchmark : c'est un
    # résultat. Le code de retour ne signale que l'absence totale de mesure.
    return 0 if reussis else 1


# --- 5. Point de lancement ------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
