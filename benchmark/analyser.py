"""
Lecture des mesures du benchmark et production des tableaux.

Compétence visée : C7 (épreuve E2) — comparaison de services d'IA

Ce module ne mesure rien : il relit `mesures.jsonl` produit par
`benchmark.executer` et en tire les tableaux du § 7 de
docs/benchmark_modeles.md, plus le tableau de notation en aveugle du § 5.

Choix : séparer la mesure de son analyse en deux modules. Motivation : les
tableaux peuvent être régénérés autant de fois qu'on veut sans repasser cent
vingt appels, et surtout la campagne de mesure ne peut pas être influencée par
la manière dont on comptait la lire.

Choix : médiane ET neuvième décile, jamais la moyenne seule. Motivation : sur
trois répétitions dont l'une tombe pendant une pointe de charge du fournisseur,
la moyenne se déplace beaucoup et ne décrit plus aucun appel réel. La médiane
dit le cas courant, le neuvième décile dit ce qu'un utilisateur subit dans le
pire des cas ordinaires, et l'écart entre les deux dit si le service est
régulier.

--- Point de lancement ---
    uv run python -m benchmark.analyser
"""

from __future__ import annotations

import json
import logging
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from benchmark.prompts import JETONS_SORTIE_MAX, MODELES, PROMPTS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("benchmark.analyser")

# --- 1. Initialisation ----------------------------------------------------

REPERTOIRE_MESURES = Path("data_pipeline/data/benchmark")
REPERTOIRE_PIECES = Path("docs/benchmark")

#: Mesures passées sous d'autres paramètres que ceux du protocole.
#:
#: Choix : un répertoire distinct, et une section distincte du rapport.
#: Motivation : la campagne a montré qu'un modèle épuisait le plafond de jetons
#: en raisonnement visible. Relever le plafond pour lui seul et verser le
#: résultat dans le tableau principal aurait rompu la règle du protocole — mêmes
#: paramètres pour tous — tout en le laissant croire respecté. La mesure est
#: donc refaite à part, étiquetée, et jamais mélangée.
REPERTOIRE_COMPLEMENTAIRE = Path("data_pipeline/data/benchmark-complementaire")

#: Décalage appliqué aux étiquettes A, B, C, D d'un prompt à l'autre.
#:
#: Choix : un décalage déterministe plutôt qu'un tirage aléatoire. Motivation :
#: les tableaux doivent être reproductibles à l'identique — un jury qui relance
#: l'analyse doit retrouver le même document. Un tirage aléatoire produirait un
#: fichier différent à chaque exécution, donc invérifiable.
#:
#: Réserve honnête : la notatrice est aussi l'autrice du code. L'aveugle est une
#: discipline de procédure — la correspondance vit dans un fichier distinct, à
#: n'ouvrir qu'après notation — non une garantie technique. Le dire vaut mieux
#: que revendiquer une rigueur que le dispositif n'a pas.
def decalage(identifiant_prompt: str) -> int:
    """Décalage stable d'un prompt, tiré de son identifiant."""
    return sum(ord(caractere) for caractere in identifiant_prompt)


# --- 2. Règles logiques de traitement -------------------------------------

def charger(chemin: Path) -> list[dict]:
    """
    Relit un fichier de lignes JSON en signalant celles qui sont illisibles.

    Compétence visée : C7 (épreuve E2)
    """
    if not chemin.is_file():
        raise FileNotFoundError(f"{chemin} est absent : lancer benchmark.executer d'abord")

    enregistrements, illisibles = [], 0
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            enregistrements.append(json.loads(ligne))
        except json.JSONDecodeError:
            illisibles += 1
    if illisibles:
        logger.warning("%d ligne(s) illisible(s) dans %s", illisibles, chemin)
    return enregistrements


def statistiques(valeurs: list[float]) -> dict:
    """
    Résume une série de latences.

    Compétence visée : C7 (épreuve E2)

    Le neuvième décile est calculé par position sur la série triée plutôt que
    par interpolation : sur trente points, une interpolation donnerait un chiffre
    qui ne correspond à aucun appel observé.
    """
    if not valeurs:
        return {"n": 0}
    triees = sorted(valeurs)
    rang_p90 = min(len(triees) - 1, int(round(0.9 * (len(triees) - 1))))
    return {
        "n": len(triees),
        "mediane": statistics.median(triees),
        "p90": triees[rang_p90],
        "minimum": triees[0],
        "maximum": triees[-1],
        "ecart_type": statistics.pstdev(triees) if len(triees) > 1 else 0.0,
    }


def nombre(valeur, decimales=2, absent="—") -> str:
    """Met en forme un nombre, ou rend un tiret cadratin s'il est absent."""
    if valeur is None:
        return absent
    return f"{valeur:.{decimales}f}".replace(".", ",")


def synthese_par_modele(mesures: list[dict]) -> dict[str, dict]:
    """
    Agrège les mesures modèle par modèle.

    Compétence visée : C7 (épreuve E2)

    Choix : seuls les appels dont l'issue est `succes` ET dont la sonde a
    produit une trace alimentent les statistiques. Motivation : un appel en
    erreur a une durée, mais cette durée n'est pas la latence du modèle — c'est
    le temps qu'a mis un refus. Les mélanger produirait une latence médiane plus
    basse pour le modèle qui échoue le plus, ce qui serait absurde.
    """
    par_modele: dict[str, dict] = {}
    for modele in MODELES:
        nom = modele["nom"]
        lignes = [m for m in mesures if m.get("modele") == nom]
        retenues = [m for m in lignes
                    if m.get("issue") == "succes" and m.get("trace_sonde") == "presente"]

        entrees = [m["jetons_entree"] for m in retenues if m.get("jetons_entree")]
        sorties = [m["jetons_sortie"] for m in retenues if m.get("jetons_sortie")]
        couts = [m["cout_estime"] for m in retenues if m.get("cout_estime") is not None]

        par_modele[nom] = {
            "fournisseur": modele["fournisseur"],
            "appels": len(lignes),
            "succes": sum(1 for m in lignes if m.get("issue") == "succes"),
            "erreurs": sum(1 for m in lignes if m.get("issue") == "erreur"),
            "non_mesure": any(m.get("issue") == "non_mesure" for m in lignes) or not lignes,
            "tentatives_ecartees": sum(max(0, m.get("tentatives", 1) - 1) for m in lignes),
            "traces_absentes": sum(1 for m in lignes if m.get("trace_sonde") == "absente"),
            "latence": statistiques([m["latence_secondes"] for m in retenues
                                     if m.get("latence_secondes") is not None]),
            "jetons_entree_moyen": statistics.mean(entrees) if entrees else None,
            "jetons_sortie_moyen": statistics.mean(sorties) if sorties else None,
            "cout_mille_requetes": (statistics.mean(couts) * 1000) if couts else None,
            "tarif_a_verifier": any(m.get("tarif_a_verifier") for m in retenues),
        }
    return par_modele


def latences_par_agent(mesures: list[dict]) -> dict[tuple[str, str], dict]:
    """
    Latence médiane croisée modèle × agent.

    Compétence visée : C7 (épreuve E2)

    Choix : croiser par agent et non par prompt. Motivation : la décision porte
    sur l'affectation d'un modèle à un agent. Un tableau à quarante lignes de
    prompts ne se lit pas ; un tableau à quatre colonnes d'agents répond
    directement à la question posée.
    """
    groupes = defaultdict(list)
    for mesure in mesures:
        if mesure.get("issue") != "succes" or mesure.get("latence_secondes") is None:
            continue
        groupes[(mesure["modele"], mesure["agent"])].append(mesure["latence_secondes"])
    return {cle: statistiques(valeurs) for cle, valeurs in groupes.items()}


# --- 3. Gestion des erreurs et exceptions ---------------------------------
# Les deux cas d'échec de ce module — fichier de mesures absent, fichier
# illisible — sont traités dans `charger` : le premier lève avec le remède, le
# second compte les lignes perdues plutôt que de les ignorer. Un tableau
# construit sur un fichier tronqué sans le dire reproduirait le motif que ce
# projet documente dans ses dossiers d'incident.


# --- 4. Sauvegarde des résultats ------------------------------------------

def rediger_mesures(par_modele, croisement, mesures) -> str:
    """
    Compose la section des mesures, en markdown.

    Compétence visée : C7 (épreuve E2)
    """
    agents = ["pedagogue", "researcher", "coach", "watcher"]
    presents = [nom for nom, s in par_modele.items() if not s["non_mesure"]]
    absents = [nom for nom, s in par_modele.items() if s["non_mesure"]]

    lignes = [
        "### 7.1 Latence, en secondes",
        "",
        "Mesures relevées par la sonde de monitorage du projet, sur les appels "
        "aboutis. Les appels en erreur en sont exclus : la durée d'un refus "
        "n'est pas la latence d'un modèle.",
        "",
        "| Modèle | Appels retenus | Médiane | 9ᵉ décile | Minimum | Maximum | Écart-type |",
        "|---|---|---|---|---|---|---|",
    ]
    for nom in presents:
        latence = par_modele[nom]["latence"]
        lignes.append(
            f"| `{nom}` | {latence.get('n', 0)} | **{nombre(latence.get('mediane'))}** | "
            f"{nombre(latence.get('p90'))} | {nombre(latence.get('minimum'))} | "
            f"{nombre(latence.get('maximum'))} | {nombre(latence.get('ecart_type'))} |"
        )
    for nom in absents:
        lignes.append(f"| `{nom}` | 0 | **non mesuré** | — | — | — | — |")

    lignes += [
        "",
        "### 7.2 Latence médiane par agent",
        "",
        "| Modèle | " + " | ".join(a.capitalize() for a in agents) + " |",
        "|---|" + "---|" * len(agents),
    ]
    for nom in presents:
        cellules = []
        for agent in agents:
            stat = croisement.get((nom, agent), {})
            cellules.append(nombre(stat.get("mediane")))
        lignes.append(f"| `{nom}` | " + " | ".join(cellules) + " |")
    for nom in absents:
        lignes.append(f"| `{nom}` | " + " | ".join(["non mesuré"] * len(agents)) + " |")

    lignes += [
        "",
        "### 7.3 Jetons et coût",
        "",
        "Jetons **rapportés par le fournisseur**, jamais estimés depuis une "
        "longueur de texte.",
        "",
        "| Modèle | Jetons d'entrée (moy.) | Jetons de sortie (moy.) | Coût / 1000 requêtes |",
        "|---|---|---|---|",
    ]
    for nom in presents:
        synthese = par_modele[nom]
        if synthese["cout_mille_requetes"] is None:
            cout = "0 — modèle local" if synthese["fournisseur"] == "ollama" else "—"
        else:
            cout = f"{nombre(synthese['cout_mille_requetes'], 3)} $"
            if synthese["tarif_a_verifier"]:
                cout += " ⚠"
        lignes.append(
            f"| `{nom}` | {nombre(synthese['jetons_entree_moyen'], 0)} | "
            f"{nombre(synthese['jetons_sortie_moyen'], 0)} | {cout} |"
        )
    for nom in absents:
        lignes.append(f"| `{nom}` | non mesuré | non mesuré | non mesuré |")

    lignes += [
        "",
        "⚠ **Le tarif n'a pas été confronté à la grille du fournisseur.** Ces "
        "montants sont un ordre de grandeur, pas une facture. Voir § 6.",
        "",
        "### 7.4 Fiabilité de la campagne",
        "",
        "| Modèle | Appels | Succès | Erreurs | Tentatives écartées (quota) | Appels sans trace |",
        "|---|---|---|---|---|---|",
    ]
    for nom, synthese in par_modele.items():
        if synthese["non_mesure"]:
            lignes.append(f"| `{nom}` | 0 | 0 | 0 | 0 | — |")
            continue
        lignes.append(
            f"| `{nom}` | {synthese['appels']} | {synthese['succes']} | "
            f"{synthese['erreurs']} | {synthese['tentatives_ecartees']} | "
            f"{synthese['traces_absentes']} |"
        )

    total_sans_trace = sum(s["traces_absentes"] for s in par_modele.values())
    lignes += [
        "",
        "La colonne « appels sans trace » est le contrôle hérité de l'incident "
        "003 : elle compte les appels pour lesquels la sonde n'a rien écrit sur "
        "le disque. "
        + ("Elle est à zéro — chaque appel mesuré a laissé une trace vérifiée."
           if total_sans_trace == 0
           else f"**Elle vaut {total_sans_trace} : ces appels n'ont pas de mesure de jetons.**"),
        "",
        "La colonne « tentatives écartées » compte les appels rejoués après un "
        "refus pour quota. Leur latence a été jetée, jamais moyennée : une "
        "attente de quota mesure le palier tarifaire du compte, pas le modèle.",
    ]
    return "\n".join(lignes)


def rediger_troncature(mesures, reponses) -> str:
    """
    Compose la section sur la troncature et les blocs de raisonnement.

    Compétence visée : C7 (épreuve E2)

    Choix : mesurer combien de réponses touchent le plafond de jetons, et
    combien ouvrent un bloc de raisonnement sans le refermer. Motivation : cette
    section n'était pas prévue au protocole. Elle a été ajoutée parce que la
    campagne a révélé un fait que les tableaux de latence et de jetons ne
    montraient pas — une réponse tronquée y ressemble à une réponse courte.
    Ajouter une mesure après coup est légitime quand elle DÉCRIT les données ;
    ce qui ne l'aurait pas été, c'est de modifier un critère de décision.
    """
    tot = defaultdict(int)
    plafond = defaultdict(int)
    plafonds_vus = defaultdict(set)
    for mesure in mesures:
        if mesure.get("issue") != "succes":
            continue
        nom = mesure["modele"]
        tot[nom] += 1
        # Le champ `jetons_max` a été ajouté à l'exécuteur APRÈS la campagne
        # principale : ses lignes ne le portent pas. Le défaut du protocole est
        # alors la bonne valeur — c'est celle sous laquelle elles ont été
        # passées. Sans ce repli, la troncature se comptait à zéro et le fait le
        # plus important de la campagne disparaissait du tableau.
        limite = mesure.get("jetons_max") or JETONS_SORTIE_MAX
        plafonds_vus[nom].add(limite)
        if mesure.get("jetons_sortie") == limite:
            plafond[nom] += 1

    ouvert = defaultdict(int)
    ferme = defaultdict(int)
    for reponse in reponses:
        texte = reponse.get("reponse") or ""
        if "<think>" in texte:
            ouvert[reponse["modele"]] += 1
        if "</think>" in texte:
            ferme[reponse["modele"]] += 1

    lignes = [
        "### 7.5 Troncature et raisonnement visible",
        "",
        "Cette section n'était pas au protocole. Elle a été ajoutée parce que la "
        "campagne a mis au jour un fait que les tableaux précédents masquent : "
        "**une réponse tronquée y ressemble à une réponse courte.**",
        "",
        "| Modèle | Réponses au plafond de jetons | Bloc `<think>` ouvert | …refermé |",
        "|---|---|---|---|",
    ]
    for nom in sorted(tot):
        total = tot[nom]
        lignes.append(
            f"| `{nom}` | {plafond[nom]}/{total} | {ouvert[nom]}/{total} | "
            f"{ferme[nom]}/{total} |"
        )
    return "\n".join(lignes)


def rediger_complement(par_modele, reponses_protocole) -> str:
    """
    Compose la section de la mesure complémentaire, si elle existe.

    Compétence visée : C7 (épreuve E2)
    """
    chemin = REPERTOIRE_COMPLEMENTAIRE / "mesures.jsonl"
    if not chemin.is_file():
        return ""

    mesures = [m for m in charger(chemin) if m.get("issue") == "succes"]
    reponses = charger(REPERTOIRE_COMPLEMENTAIRE / "reponses.jsonl")
    if not mesures:
        return ""

    plafond = mesures[0].get("jetons_max")
    modele = mesures[0].get("modele")
    latences = [m["latence_secondes"] for m in mesures if m.get("latence_secondes")]
    sorties = [m["jetons_sortie"] for m in mesures if m.get("jetons_sortie")]
    couts = [m["cout_estime"] for m in mesures if m.get("cout_estime") is not None]
    refermes = sum(1 for r in reponses if "</think>" in (r.get("reponse") or ""))

    reference = par_modele.get(modele, {})
    refermes_protocole = sum(
        1 for r in reponses_protocole
        if r.get("modele") == modele and "</think>" in (r.get("reponse") or "")
    )
    total_protocole = sum(1 for r in reponses_protocole if r.get("modele") == modele)

    return "\n".join([
        "### 7.6 Mesure complémentaire — hors protocole",
        "",
        f"La campagne principale imposait un plafond de {JETONS_SORTIE_MAX} jetons "
        f"à tous les modèles. Sous ce plafond, `{modele}` rendait des réponses "
        "tronquées : la question se posait de savoir si l'on mesurait le modèle "
        "ou la contrainte.",
        "",
        f"Une mesure a donc été refaite pour ce seul modèle, à {plafond} jetons, "
        f"sur les dix prompts, une répétition. **Elle ne figure pas dans les "
        "tableaux précédents et ne s'y compare pas** : ses paramètres diffèrent. "
        "Elle répond à une question distincte — le modèle est-il handicapé par le "
        "plafond, ou par lui-même ?",
        "",
        f"| Grandeur | Protocole ({JETONS_SORTIE_MAX} jetons) | Complément ({plafond} jetons) |",
        "|---|---|---|",
        f"| Latence médiane | {nombre(reference.get('latence', {}).get('mediane'))} s "
        f"| {nombre(statistics.median(latences))} s |",
        f"| Jetons de sortie (moy.) | {nombre(reference.get('jetons_sortie_moyen'), 0)} "
        f"| {nombre(statistics.mean(sorties), 0)} |",
        f"| Coût / 1000 requêtes | {nombre(reference.get('cout_mille_requetes'), 3)} $ ⚠ "
        f"| {nombre(statistics.mean(couts) * 1000, 3)} $ ⚠ |",
        f"| Bloc de raisonnement refermé | {refermes_protocole}/{total_protocole} "
        f"| {refermes}/{len(reponses)} |",
        "",
        "**Réponse : par lui-même.** Le plafond relevé, le modèle répond "
        "correctement aux dix prompts, classification comprise. Mais il consomme "
        "alors en moyenne "
        f"{statistics.mean(sorties):.0f} jetons de sortie là où les deux autres "
        f"en consomment moins de {max(s2['jetons_sortie_moyen'] for n, s2 in par_modele.items() if n != modele and s2.get('jetons_sortie_moyen')):.0f}, "
        "pour des réponses de longueur comparable : "
        "l'écart est du raisonnement visible, pas du contenu rendu à "
        "l'utilisateur. Le surcoût et la latence supplémentaire sont donc une "
        "propriété du modèle, non un artefact du protocole.",
        "",
        "C'est le point qui rend la comparaison défendable. Sans cette mesure, "
        "on aurait écarté un modèle sur un plafond qu'on lui avait soi-même "
        "imposé — un raisonnement circulaire qu'un jury aurait relevé.",
    ])


def rediger_grille(reponses) -> tuple[str, str]:
    """
    Compose le tableau de notation en aveugle et sa clé, séparément.

    Compétence visée : C7 (épreuve E2)

    Choix : deux fichiers distincts. Motivation : une clé placée en bas du même
    document serait lue avant la notation — pas par malhonnêteté, mais parce
    qu'on voit ce qui est sous les yeux.
    """
    par_prompt = defaultdict(dict)
    for reponse in reponses:
        # Seule la première répétition est présentée : à température 0,2 les
        # trois se ressemblent, et noter trois fois la même chose n'apporte rien.
        if reponse.get("repetition") == 1:
            par_prompt[reponse["prompt"]][reponse["modele"]] = reponse["reponse"]

    etiquettes = "ABCD"
    document = [
        "# Notation en aveugle des réponses",
        "",
        "**Compétence visée :** C7 (épreuve E2) — critère « qualité pédagogique »",
        "",
        "Les réponses sont présentées sans le nom du modèle qui les a produites. "
        "La correspondance est dans `cle-notation.md`, **à n'ouvrir qu'une fois "
        "les notes posées**.",
        "",
        "Grille : cinq axes notés de 0 à 3 — exactitude technique, adaptation au "
        "niveau, utilité de l'exemple, concision, respect du format. Barème "
        "détaillé au § 5 de `../benchmark_modeles.md`.",
        "",
        "Seule la première des trois répétitions est reproduite : à température "
        "0,2 les trois se ressemblent, et les noter séparément n'apporterait rien. "
        "Les trois sont conservées dans `reponses.jsonl`.",
        "",
        "**Limite de l'aveugle, à dire plutôt qu'à masquer.** Un des trois "
        "modèles émet un bloc `<think>` visible : ses réponses se reconnaissent "
        "au premier coup d'œil. L'aveugle ne tient donc pas pour lui — mais il "
        "est déjà écarté sur les critères mesurés (§ 8), et sa note ne décide de "
        "rien. Il tient en revanche pour les deux modèles entre lesquels la "
        "notation doit trancher, dont les réponses ne portent aucune marque "
        "distinctive. La question à laquelle cette grille sert à répondre reste "
        "donc posée en aveugle.",
        "",
        "---",
        "",
    ]
    cle = [
        "# Clé de la notation en aveugle",
        "",
        "**Compétence visée :** C7 (épreuve E2)",
        "",
        "À n'ouvrir qu'après avoir renseigné les notes de `notation-aveugle.md`.",
        "",
        "| Prompt | " + " | ".join(etiquettes) + " |",
        "|---|" + "---|" * len(etiquettes),
    ]

    for prompt in PROMPTS:
        disponibles = par_prompt.get(prompt.identifiant, {})
        if not disponibles:
            continue
        noms = sorted(disponibles)
        rotation = decalage(prompt.identifiant) % len(noms)
        ordonnes = noms[rotation:] + noms[:rotation]

        document += [
            f"## {prompt.identifiant} — {prompt.intitule} ({prompt.agent})",
            "",
            "<details><summary>Énoncé soumis</summary>",
            "",
            "```",
            prompt.texte,
            "```",
            "",
            "</details>",
            "",
        ]
        for index, nom_modele in enumerate(ordonnes):
            document += [
                f"### Réponse {etiquettes[index]}",
                "",
                disponibles[nom_modele].strip(),
                "",
                "| Exactitude | Adaptation | Exemple | Concision | Format | Total |",
                "|---|---|---|---|---|---|",
                "|  |  |  |  |  | /15 |",
                "",
            ]
        document += ["---", ""]

        cle.append(
            f"| {prompt.identifiant} | "
            + " | ".join(f"`{n}`" for n in ordonnes)
            + " |" + " — |" * (len(etiquettes) - len(ordonnes))
        )

    cle += [
        "",
        "Le décalage des étiquettes est déterministe, tiré de l'identifiant du "
        "prompt : deux exécutions de l'analyse produisent le même document, ce "
        "qu'un tirage aléatoire ne permettrait pas.",
        "",
        "**Réserve.** La notatrice est aussi l'autrice du code. L'aveugle est "
        "ici une discipline de procédure — la clé vit dans un fichier séparé — "
        "et non une garantie technique. Le dire vaut mieux que revendiquer une "
        "rigueur que le dispositif n'a pas.",
    ]
    return "\n".join(document), "\n".join(cle)


def main() -> int:
    """
    Point de lancement de l'analyse.

    Compétence visée : C7 (épreuve E2)
    """
    mesures = charger(REPERTOIRE_MESURES / "mesures.jsonl")
    reponses = charger(REPERTOIRE_MESURES / "reponses.jsonl")
    logger.info("%d mesures et %d réponses relues", len(mesures), len(reponses))

    par_modele = synthese_par_modele(mesures)
    croisement = latences_par_agent(mesures)

    REPERTOIRE_PIECES.mkdir(parents=True, exist_ok=True)

    complement = rediger_complement(par_modele, reponses)
    complement = ("\n\n" + complement) if complement else ""

    (REPERTOIRE_PIECES / "mesures-section-7.md").write_text(
        rediger_mesures(par_modele, croisement, mesures)
        + "\n\n" + rediger_troncature(mesures, reponses)
        + complement
        + "\n",
        encoding="utf-8")

    document, cle = rediger_grille(reponses)
    (REPERTOIRE_PIECES / "notation-aveugle.md").write_text(document + "\n", encoding="utf-8")
    (REPERTOIRE_PIECES / "cle-notation.md").write_text(cle + "\n", encoding="utf-8")

    # Les mesures brutes deviennent une pièce du dossier : le jury doit pouvoir
    # recalculer les tableaux, pas seulement les lire. `data_pipeline/data/` est
    # exclu du dépôt — et cette exclusion ne sera pas assouplie, elle protège le
    # corpus brut — donc la copie est déposée à côté du rapport.
    for fichier in ("mesures.jsonl", "reponses.jsonl"):
        shutil.copy2(REPERTOIRE_MESURES / fichier, REPERTOIRE_PIECES / fichier)

    for nom, synthese in par_modele.items():
        if synthese["non_mesure"]:
            logger.warning("%-24s NON MESURÉ", nom)
        else:
            logger.info("%-24s médiane %.2f s, %d succès / %d appels", nom,
                        synthese["latence"].get("mediane", 0),
                        synthese["succes"], synthese["appels"])

    logger.info("pièces écrites dans %s", REPERTOIRE_PIECES)
    return 0


# --- 5. Point de lancement ------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
