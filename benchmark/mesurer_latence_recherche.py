"""
Mesure la latence de `POST /ai/recherche`, et redérive le seuil d'alerte.

Compétence visée : C20 (épreuve E5) — seuils de monitorage dérivés de la mesure
Compétences concernées : C11 (E3) — indicateurs ; C21 (E5)

Pourquoi ce script existe. La décision 024 a dérivé le seuil de latence de
production de neuf mesures, le 31/08 au matin, et elle se termine par une
condition de révision : « un changement de l'un des trois demande de rejouer les
neuf mesures, pas d'ajuster la valeur à vue ». Le soir même,
`OLLAMA_KEEP_ALIVE=24h` a divisé la médiane par six sans que personne rejoue
quoi que ce soit. Rejouer neuf mesures à la main, c'est ce qui n'a pas été fait ;
ce script est ce qui rend l'oubli moins probable la fois suivante.

Choix : le script **ne modifie aucun réglage**. Il mesure, applique les deux
règles de la décision 024, et propose une valeur. Poser un seuil reste une
décision, et une décision se consigne — pas s'applique par un script.

Choix : un appel de préchauffage, mesuré mais exclu de la statistique. Le
protocole d'origine mesurait « à chaud, modèle déjà chargé ». Mélanger le
premier appel aux autres mesurerait le chargement du modèle, pas l'inférence —
et c'est précisément la confusion que la décision 024 avait écartée.

Sortie : docs/benchmark/latence-recherche-<horodatage>.json
Lancement :
    uv run python -m benchmark.mesurer_latence_recherche \\
        --url https://<service-ia> --tirs 9
"""

from __future__ import annotations

# --- 1. Initialisation des dépendances et connexions externes ---

import argparse
import json
import logging
import os
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mesure_latence")

SORTIE = Path("docs/benchmark")

# Une requête de longueur et de nature ordinaires. Elle n'est pas choisie pour
# être rapide : elle est choisie pour ressembler à ce qu'un apprenant tape.
REQUETE = "comment lire un fichier ligne par ligne en Python"
FRAGMENTS = 5


# --- 2. Règles logiques de traitement ---

def etat_de_la_machine(url: str) -> dict:
    """
    Consigne le contexte de la mesure, sans quoi elle n'est pas interprétable.

    Compétence visée : C20 (épreuve E5)

    Une latence ne veut rien dire seule. Deux relevés du même service, l'un sur
    un poste chargé et l'autre au repos, ne se comparent pas — et c'est
    exactement ce qui a rendu la mesure du 31/08 matin trompeuse.
    """
    etat = {
        "cible": url,
        "environnement": "hébergeur" if url.startswith("https://") else "poste",
        "systeme": platform.platform(),
        "processeurs": os.cpu_count(),
    }
    try:
        etat["charge_1min"] = round(os.getloadavg()[0], 2)
    except OSError:      # indisponible hors Unix
        etat["charge_1min"] = None
    return etat


def un_tir(url: str, cle: str, delai: int = 180) -> tuple[float, int, int | None]:
    """
    Un appel de recherche, chronométré du côté de l'appelant.

    Compétence visée : C20 (épreuve E5)

    Choix : mesurer du côté appelant plutôt que de lire `latence_secondes` de
    la réponse. Motivation : c'est l'attente réelle de l'utilisateur qui
    intéresse un seuil d'alerte, transport compris. La latence rapportée par le
    service est relevée en plus, et l'écart entre les deux dit ce que pèse le
    réseau.
    """
    corps = json.dumps(
        {"requete": REQUETE, "nombre_fragments": FRAGMENTS}).encode("utf-8")
    requete = urllib.request.Request(
        f"{url.rstrip('/')}/ai/recherche", data=corps, method="POST",
        headers={"Content-Type": "application/json", "X-Cle-Service": cle},
    )
    debut = time.perf_counter()
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        charge = json.loads(reponse.read())
        code = reponse.status
    duree = time.perf_counter() - debut
    return duree, code, charge.get("fragments_rendus")


def deriver_le_seuil(mesures: list[float]) -> dict:
    """
    Applique les deux règles de la décision 024 et propose un seuil.

    Compétence visée : C20 (épreuve E5)

    Les deux règles sont indépendantes : l'une part de la dispersion, l'autre
    du pire cas observé. Qu'elles convergent est ce qui donne confiance dans la
    valeur ; qu'elles divergent est une information, et le script le dit plutôt
    que de choisir à la place de qui lit.
    """
    moyenne = statistics.mean(mesures)
    ecart_type = statistics.stdev(mesures) if len(mesures) > 1 else 0.0
    maximum = max(mesures)

    regle_dispersion = moyenne + 2.5 * ecart_type
    regle_pire_cas = maximum * 1.3
    ecart_relatif = (abs(regle_dispersion - regle_pire_cas)
                     / max(regle_dispersion, regle_pire_cas))

    # Arrondi vers le bas au multiple de 5 : un seuil ne doit pas être plus
    # permissif que ce que la mesure justifie.
    propose = int(min(regle_dispersion, regle_pire_cas) // 5 * 5)

    return {
        "n": len(mesures),
        "minimum": round(min(mesures), 2),
        "mediane": round(statistics.median(mesures), 2),
        "moyenne": round(moyenne, 2),
        "ecart_type": round(ecart_type, 2),
        "maximum": round(maximum, 2),
        "regle_1_moyenne_plus_2_5_ecarts_types": round(regle_dispersion, 2),
        "regle_2_maximum_plus_30_pourcent": round(regle_pire_cas, 2),
        "les_deux_regles_convergent": ecart_relatif < 0.15,
        "ecart_entre_les_regles_pourcent": round(100 * ecart_relatif, 1),
        "seuil_propose_secondes": propose,
    }


# --- 3. Gestion des erreurs et exceptions ---

def campagne(url: str, cle: str, tirs: int) -> dict:
    """
    Enchaîne le préchauffage puis les tirs, en tolérant les échecs isolés.

    Compétence visée : C20 (épreuve E5), C21 (E5)

    Un tir en échec n'est pas une latence : sa durée mesure un refus, pas une
    recherche. Il est compté et écarté de la statistique — c'est la leçon du
    benchmark C7, où l'attente d'un quota avait failli être moyennée avec des
    temps de calcul.
    """
    logger.info("Préchauffage — ce tir est mesuré mais exclu de la statistique")
    try:
        prechauffage, _, _ = un_tir(url, cle)
        logger.info("Préchauffage : %.2f s", prechauffage)
    except (urllib.error.URLError, TimeoutError, OSError) as erreur:
        logger.error("Préchauffage impossible : %s", erreur)
        raise SystemExit(
            "La cible ne répond pas. Vérifiez l'URL et la clé de service."
        ) from erreur

    mesures: list[float] = []
    echecs: list[dict] = []
    for n in range(1, tirs + 1):
        try:
            duree, code, fragments = un_tir(url, cle)
        except urllib.error.HTTPError as erreur:
            logger.warning("Tir %d : HTTP %s — écarté", n, erreur.code)
            echecs.append({"tir": n, "code": erreur.code})
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as erreur:
            logger.warning("Tir %d : %s — écarté", n, erreur)
            echecs.append({"tir": n, "erreur": str(erreur)})
            continue

        if fragments == 0:
            # Une recherche qui ne rend rien n'a pas fait le même travail.
            logger.warning("Tir %d : 0 fragment rendu — écarté", n)
            echecs.append({"tir": n, "motif": "aucun fragment rendu"})
            continue

        logger.info("Tir %d/%d : %.2f s (%s fragments)", n, tirs, duree, fragments)
        mesures.append(duree)

    if len(mesures) < 2:
        raise SystemExit(
            f"{len(mesures)} tir(s) exploitable(s) : trop peu pour dériver un seuil."
        )

    return {
        "horodatage": datetime.now(timezone.utc).isoformat(),
        "protocole": {
            "requete": REQUETE,
            "fragments_demandes": FRAGMENTS,
            "tirs_demandes": tirs,
            "prechauffage_secondes": round(prechauffage, 2),
            "note": "un tir à la fois, modèle déjà chargé, préchauffage exclu",
        },
        "contexte": etat_de_la_machine(url),
        "mesures_secondes": [round(m, 2) for m in mesures],
        "tirs_ecartes": echecs,
        "derivation": deriver_le_seuil(mesures),
    }


# --- 4. Sauvegarde des résultats ---

def sauvegarder(rapport: dict) -> Path:
    """
    Écrit le relevé, horodaté, sans écraser le précédent.

    Compétence visée : C20 (épreuve E5)

    Choix : un fichier par campagne plutôt qu'un fichier écrasé. Un seuil se
    défend par l'historique de ses dérivations, pas par sa dernière valeur.
    """
    SORTIE.mkdir(parents=True, exist_ok=True)
    horodatage = rapport["horodatage"].replace(":", "-").split(".")[0]
    chemin = SORTIE / f"latence-recherche-{horodatage}.json"
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def resumer(rapport: dict) -> None:
    """Rend le relevé lisible sans ouvrir le JSON."""
    d = rapport["derivation"]
    c = rapport["contexte"]
    print()
    print(f"  Cible ............... {c['cible']}  ({c['environnement']})")
    print(f"  Tirs exploitables ... {d['n']}   écartés : {len(rapport['tirs_ecartes'])}")
    print(f"  Préchauffage ........ {rapport['protocole']['prechauffage_secondes']} s (exclu)")
    print(f"  min / médiane / max . {d['minimum']} / {d['mediane']} / {d['maximum']} s")
    print(f"  moyenne / écart-type  {d['moyenne']} / {d['ecart_type']} s")
    print(f"  Règle 1 (moy + 2,5 σ)  {d['regle_1_moyenne_plus_2_5_ecarts_types']} s")
    print(f"  Règle 2 (max + 30 %)   {d['regle_2_maximum_plus_30_pourcent']} s")
    convergence = ("convergent" if d["les_deux_regles_convergent"]
                   else f"DIVERGENT de {d['ecart_entre_les_regles_pourcent']} %")
    print(f"  Les deux règles ..... {convergence}")
    print(f"  Seuil proposé ....... {d['seuil_propose_secondes']} s")
    if not d["les_deux_regles_convergent"]:
        print("\n  Les deux règles ne convergent pas : la dispersion est trop")
        print("  forte pour que neuf tirs suffisent. Augmenter le nombre de tirs")
        print("  avant de poser un seuil.")
    print()


# --- 5. Point de lancement ---

def main() -> int:
    analyseur = argparse.ArgumentParser(
        description="Mesure la latence de /ai/recherche et redérive le seuil.")
    analyseur.add_argument(
        "--url", required=True,
        help="Adresse du service IA (https://… pour l'hébergeur).")
    analyseur.add_argument(
        "--tirs", type=int, default=9,
        help="Nombre de tirs retenus, hors préchauffage (défaut : 9).")
    arguments = analyseur.parse_args()

    cle = os.environ.get("SERVICE_IA_CLE") or os.environ.get("SERVICE_IA_CLES", "")
    cle = cle.split(",")[0].strip()
    if not cle:
        logger.error("Aucune clé de service : posez SERVICE_IA_CLE dans l'environnement.")
        return 2

    logger.info("Campagne sur %s — %d tirs", arguments.url, arguments.tirs)
    rapport = campagne(arguments.url, cle, arguments.tirs)
    chemin = sauvegarder(rapport)
    resumer(rapport)
    logger.info("Relevé écrit dans %s", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
