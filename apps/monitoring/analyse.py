"""
Lecture hors ligne du journal de monitorage.

Compétence visée : C20 (épreuve E5) — exploitation des traces

Choix : un outil de lecture distinct des sondes. Motivation : la sonde écrit
dans le processus du service, où tout calcul se paie sur le temps de réponse.
L'analyse, elle, tourne quand on veut, sur le fichier complet, et voit le trafic
de tous les processus — là où la fenêtre d'alerte en mémoire ne voit que celui
du sien.

Lancement :

    uv run python -m apps.monitoring.analyse                 # journée courante
    uv run python -m apps.monitoring.analyse --jours 7       # semaine écoulée
    uv run python -m apps.monitoring.analyse --fichier <chemin>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .journal import REPERTOIRE_JOURNAL


def lire(fichiers: list[Path]) -> Iterator[dict[str, Any]]:
    """
    Lit les événements de plusieurs journaux, en ignorant les lignes illisibles.

    Compétence visée : C20 (épreuve E5)

    Choix : les lignes illisibles sont comptées et non fatales. Motivation : un
    journal dont la dernière ligne est tronquée par un arrêt brutal reste
    exploitable pour tout ce qui précède — et c'est précisément après un arrêt
    brutal qu'on vient le lire.
    """
    for fichier in fichiers:
        if not fichier.is_file():
            continue
        with fichier.open(encoding="utf-8") as flux:
            for ligne in flux:
                if not ligne.strip():
                    continue
                try:
                    yield json.loads(ligne)
                except json.JSONDecodeError:
                    yield {"type": "_ligne_illisible", "fichier": fichier.name}


def resumer(evenements: Iterator[dict[str, Any]]) -> dict[str, Any]:
    """
    Produit le rapport de période.

    Compétence visée : C20 (épreuve E5)

    Choix : la médiane et le neuvième décile plutôt que la seule moyenne.
    Motivation : la moyenne d'une latence est tirée par quelques appels très
    lents et ne décrit l'expérience de personne. Le décile dit ce que subissent
    les dix pour cent les moins bien servis, qui sont ceux qui se plaignent.
    """
    latences: dict[str, list[float]] = defaultdict(list)
    par_agent: Counter[str] = Counter()
    par_modele: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    erreurs: Counter[str] = Counter()
    codes_retour: Counter[str] = Counter()
    alertes: list[dict[str, Any]] = []
    fragments: list[int] = []
    jetons_entree = jetons_sortie = 0
    cout_total = 0.0
    cout_incertain = False
    appels_sans_cout: Counter[str] = Counter()
    total = illisibles = recherches_vides = 0
    # Compté séparément des fragments : une recherche en erreur n'a pas de
    # nombre de fragments, et l'oublier ferait annoncer « 0 recherche » à côté
    # d'une latence de recherche non nulle — le genre d'écart que ce module
    # existe précisément pour ne pas produire.
    recherches_total = recherches_erreur = 0

    for evenement in evenements:
        total += 1
        genre = evenement.get("type")

        if genre == "_ligne_illisible":
            illisibles += 1
            continue

        if genre == "alerte":
            alertes.append(evenement)
            continue

        latence = evenement.get("latence_secondes")
        if isinstance(latence, (int, float)):
            latences[genre].append(float(latence))

        if genre == "appel_llm":
            par_agent[evenement.get("agent") or "inconnu"] += 1
            par_modele[evenement.get("modele") or "inconnu"] += 1
            issues[evenement.get("issue") or "inconnue"] += 1

            if evenement.get("issue") == "erreur":
                erreurs[evenement.get("erreur_classe") or "inconnue"] += 1
                code = evenement.get("code_retour")
                if code is not None:
                    codes_retour[str(code)] += 1

            jetons_entree += evenement.get("jetons_entree") or 0
            jetons_sortie += evenement.get("jetons_sortie") or 0

            cout = evenement.get("cout_estime")
            if isinstance(cout, (int, float)):
                cout_total += float(cout)
                if evenement.get("tarif_a_verifier"):
                    cout_incertain = True
            elif evenement.get("motif_sans_cout"):
                appels_sans_cout[evenement["motif_sans_cout"]] += 1

        elif genre == "recherche_rag":
            recherches_total += 1
            if evenement.get("issue") == "erreur":
                recherches_erreur += 1
                erreurs[evenement.get("erreur_classe") or "inconnue"] += 1
            rendus = evenement.get("fragments_rendus")
            if isinstance(rendus, int):
                fragments.append(rendus)
                if rendus == 0:
                    recherches_vides += 1

    def distribution(valeurs: list[float]) -> dict[str, float] | None:
        if not valeurs:
            return None
        ordonnees = sorted(valeurs)
        return {
            "appels": len(ordonnees),
            "mediane": round(statistics.median(ordonnees), 3),
            "decile_9": round(ordonnees[min(len(ordonnees) - 1,
                                            int(len(ordonnees) * 0.9))], 3),
            "maximum": round(ordonnees[-1], 3),
        }

    appels = issues.get("succes", 0) + issues.get("erreur", 0)
    return {
        "evenements_lus": total,
        "lignes_illisibles": illisibles,
        "appels_llm": appels,
        "taux_erreur": round(issues.get("erreur", 0) / appels, 3) if appels else None,
        "issues": dict(issues),
        "erreurs_par_classe": dict(erreurs),
        "codes_retour": dict(codes_retour),
        "par_agent": dict(par_agent),
        "par_modele": dict(par_modele),
        "latence_appel_llm": distribution(latences.get("appel_llm", [])),
        "latence_recherche_rag": distribution(latences.get("recherche_rag", [])),
        "recherches_rag": recherches_total,
        "recherches_rag_en_erreur": recherches_erreur,
        "recherches_rag_sans_resultat": recherches_vides,
        "fragments_rendus_moyenne": (
            round(sum(fragments) / len(fragments), 2) if fragments else None
        ),
        "jetons_entree": jetons_entree,
        "jetons_sortie": jetons_sortie,
        "cout_estime_total": round(cout_total, 6) if cout_total else 0.0,
        "cout_repose_sur_tarif_a_verifier": cout_incertain,
        "appels_sans_cout": dict(appels_sans_cout),
        "alertes": len(alertes),
        "alertes_par_nature": dict(Counter(a.get("nature") for a in alertes)),
    }


def afficher(rapport: dict[str, Any]) -> None:
    """
    Met le rapport en forme pour la console.

    Compétence visée : C20 (épreuve E5)
    """
    print()
    print("RAPPORT DE MONITORAGE — service IA")
    print("=" * 68)
    print(f"  Événements lus            {rapport['evenements_lus']}")
    if rapport["lignes_illisibles"]:
        print(f"  Lignes illisibles         {rapport['lignes_illisibles']}  "
              "(écriture tronquée ou entrelacée)")
    print(f"  Appels au fournisseur     {rapport['appels_llm']}")
    if rapport["taux_erreur"] is not None:
        print(f"  Taux d'erreur             {rapport['taux_erreur']:.1%}")
    for cle, libelle in [("latence_appel_llm", "Latence appel LLM   "),
                         ("latence_recherche_rag", "Latence recherche RAG")]:
        d = rapport.get(cle)
        if d:
            print(f"  {libelle}     médiane {d['mediane']:.2f} s | "
                  f"d9 {d['decile_9']:.2f} s | max {d['maximum']:.2f} s")
    print(f"  Recherches RAG            {rapport['recherches_rag']}"
          f"  dont {rapport['recherches_rag_en_erreur']} en erreur"
          f" et {rapport['recherches_rag_sans_resultat']} sans résultat")
    if rapport["fragments_rendus_moyenne"] is not None:
        print(f"  Fragments rendus (moy.)   {rapport['fragments_rendus_moyenne']}")
    print(f"  Jetons                    {rapport['jetons_entree']} entrée / "
          f"{rapport['jetons_sortie']} sortie")
    marque = "  ⚠ tarif non vérifié" if rapport["cout_repose_sur_tarif_a_verifier"] else ""
    print(f"  Coût estimé               {rapport['cout_estime_total']}{marque}")
    if rapport["appels_sans_cout"]:
        print(f"  Appels sans coût estimé   {rapport['appels_sans_cout']}")
    print(f"  Alertes                   {rapport['alertes']} "
          f"{rapport['alertes_par_nature'] or ''}")
    for cle, libelle in [("par_agent", "Par agent"), ("par_modele", "Par modèle"),
                         ("erreurs_par_classe", "Erreurs"),
                         ("codes_retour", "Codes de retour")]:
        if rapport.get(cle):
            print(f"  {libelle:24}  {rapport[cle]}")
    print("=" * 68)


def main(argv: list[str] | None = None) -> int:
    """
    Point de lancement de l'analyse.

    Compétence visée : C20 (épreuve E5)
    """
    analyseur = argparse.ArgumentParser(
        description="Rapport de monitorage du service IA, lu depuis les journaux.",
    )
    analyseur.add_argument("--jours", type=int, default=1,
                           help="Nombre de jours à couvrir, en remontant (défaut : 1).")
    analyseur.add_argument("--fichier", type=Path, default=None,
                           help="Journal précis à lire, au lieu d'une période.")
    analyseur.add_argument("--json", action="store_true",
                           help="Sortie brute en JSON, pour un traitement aval.")
    arguments = analyseur.parse_args(argv)

    if arguments.fichier:
        fichiers = [arguments.fichier]
    else:
        aujourdhui = datetime.now(timezone.utc).date()
        fichiers = [
            REPERTOIRE_JOURNAL / f"monitorage-{aujourdhui - timedelta(days=n)}.jsonl"
            for n in range(arguments.jours)
        ]

    existants = [f for f in fichiers if f.is_file()]
    if not existants:
        print(f"Aucun journal trouvé dans {REPERTOIRE_JOURNAL}. "
              "Le service n'a pas encore tourné, ou le monitorage n'est pas branché.",
              file=sys.stderr)
        return 1

    rapport = resumer(lire(existants))
    rapport["fichiers"] = [str(f) for f in existants]

    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
    else:
        afficher(rapport)
        print(f"  Journaux lus : {', '.join(f.name for f in existants)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
