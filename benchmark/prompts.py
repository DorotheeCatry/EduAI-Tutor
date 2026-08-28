"""
Jeu de prompts du benchmark de modèles.

Compétence visée : C7 (épreuve E2) — comparaison de services d'IA

Dix prompts, répartis sur les quatre agents du projet dans la proportion où
ceux-ci sont sollicités. Ils sont figés ici, versionnés, et passés au caractère
près à chaque modèle : deux mesures ne se comparent que si elles ont subi les
mêmes conditions.

Choix : des prompts tirés des usages réels du projet plutôt que d'un jeu
d'évaluation générique. Motivation : un classement obtenu sur des questions de
culture générale ne dit rien de ce que ces modèles feront ici. Le corpus porte
sur Python, l'analyse de données et le développement web, et les agents ont des
tâches précises — expliquer, corriger, classer.

Choix : le format attendu est énoncé dans chaque prompt. Motivation : le respect
du format est l'un des cinq axes de notation, et on ne peut pas le noter si on
ne l'a pas demandé.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """
    Une unité du protocole.

    Compétence visée : C7 (épreuve E2)
    """

    identifiant: str
    agent: str
    intitule: str
    texte: str


#: Plafond de jetons de sortie, identique pour tous les appels.
#:
#: Choix : un plafond commun plutôt que le défaut de chaque modèle. Motivation :
#: sans lui, un modèle bavard consommerait davantage de jetons et paraîtrait plus
#: coûteux pour une raison qui tient à son réglage par défaut, non à sa nature.
JETONS_SORTIE_MAX = 800

#: Température, identique pour tous les appels.
#:
#: Choix : 0,2 plutôt que 0. Motivation : à température nulle, certains
#: fournisseurs empruntent des chemins d'optimisation différents, ce qui rend la
#: dispersion de latence non représentative de l'usage réel. 0,2 reste assez bas
#: pour que les réponses soient stables d'une répétition à l'autre.
TEMPERATURE = 0.2


PROMPTS: tuple[Prompt, ...] = (
    # --- Pedagogue : trois prompts -------------------------------------
    Prompt(
        "p1", "pedagogue", "Génération de cours",
        "Rédige un cours court sur les décorateurs en Python, pour un apprenant "
        "de niveau intermédiaire en formation professionnelle.\n\n"
        "Format attendu : un titre, trois sections avec sous-titres, un exemple "
        "de code exécutable par section, et une phrase de synthèse. "
        "N'excède pas 400 mots.",
    ),
    Prompt(
        "p2", "pedagogue", "Réexplication adaptée",
        "Un apprenant débutant n'a pas compris la différence entre une liste et "
        "un tuple en Python après une première explication classique.\n\n"
        "Réexplique-la autrement : pars d'une situation concrète avant d'énoncer "
        "la règle, et termine par un cas où le choix compte vraiment. "
        "Format attendu : trois paragraphes, pas de liste à puces. 200 mots au plus.",
    ),
    Prompt(
        "p3", "pedagogue", "Reformulation pour débutant",
        "Reformule l'énoncé suivant pour un apprenant qui découvre la "
        "programmation, sans perdre en exactitude :\n\n"
        "« Une compréhension de liste est une expression syntaxique permettant "
        "de construire une liste par application d'une transformation et d'un "
        "prédicat de filtrage sur un itérable source. »\n\n"
        "Format attendu : deux phrases, puis un exemple de trois lignes.",
    ),

    # --- Researcher : deux prompts --------------------------------------
    Prompt(
        "p4", "researcher", "Synthèse à partir de fragments",
        "Voici trois extraits de documentation :\n\n"
        "[1] « itertools.chain(*iterables) enchaîne plusieurs itérables en un "
        "seul, sans construire de liste intermédiaire. »\n"
        "[2] « itertools.islice(iterable, stop) renvoie les premiers éléments "
        "d'un itérable, sans le matérialiser. »\n"
        "[3] « Les générateurs évaluent leurs éléments à la demande, ce qui "
        "borne l'occupation mémoire indépendamment du volume traité. »\n\n"
        "Synthétise ce que ces trois extraits, pris ensemble, permettent de faire "
        "sur un fichier de plusieurs gigaoctets. Cite les extraits par leur "
        "numéro. Format attendu : un paragraphe, 120 mots au plus.",
    ),
    Prompt(
        "p5", "researcher", "Question technique",
        "Pourquoi un appel à `xpath_string` répété treize fois sur la même ligne "
        "XML coûte-t-il beaucoup plus cher que treize expressions régulières "
        "ancrées ?\n\n"
        "Réponds sur le mécanisme, pas sur l'ordre de grandeur. "
        "Format attendu : trois phrases.",
    ),

    # --- Coach : trois prompts ------------------------------------------
    Prompt(
        "p6", "coach", "Retour sur du code fautif",
        "Un apprenant devait écrire une fonction qui renvoie la moyenne d'une "
        "liste de nombres. Il a soumis :\n\n"
        "```python\n"
        "def moyenne(nombres):\n"
        "    total = 0\n"
        "    for n in nombres:\n"
        "        total += n\n"
        "    return total / len(nombres)\n"
        "```\n\n"
        "Le test échoue sur `moyenne([])` avec `ZeroDivisionError`.\n\n"
        "Donne un retour bref et actionnable : ce qui va, ce qui ne va pas, la "
        "piste de correction. **Ne réécris pas le code entier** — l'apprenant "
        "doit le corriger lui-même. Format attendu : trois puces.",
    ),
    Prompt(
        "p7", "coach", "Génération d'exercice",
        "Crée un exercice de code sur les dictionnaires Python, niveau "
        "intermédiaire.\n\n"
        "Format attendu, strictement : un énoncé de deux phrases, un squelette "
        "de code avec des `# TODO`, et trois cas de test sous forme "
        "d'assertions. Rien d'autre.",
    ),
    Prompt(
        "p8", "coach", "Correction d'erreur",
        "Un apprenant obtient `TypeError: unhashable type: 'list'` en écrivant "
        "`d[[1, 2]] = 'valeur'`.\n\n"
        "Explique la cause en une phrase, puis donne la correction. "
        "Format attendu : deux phrases maximum, et une ligne de code.",
    ),

    # --- Watcher : deux prompts -----------------------------------------
    Prompt(
        "p9", "watcher", "Classification d'une méprise",
        "Un apprenant écrit `for i in range(len(liste)): print(liste[i])` alors "
        "qu'il pouvait écrire `for element in liste: print(element)`.\n\n"
        "Classe cette méprise dans exactement une catégorie parmi : "
        "erreur_de_syntaxe, meconnaissance_idiome, erreur_de_logique, "
        "probleme_de_performance, erreur_de_type.\n\n"
        "Format attendu, strictement : la catégorie seule, en un mot, sans "
        "phrase ni ponctuation.",
    ),
    Prompt(
        "p10", "watcher", "Détection de type d'erreur",
        "Voici un message d'erreur :\n\n"
        "`AttributeError: 'NoneType' object has no attribute 'strip'`\n\n"
        "Indique en un mot la cause la plus probable parmi : "
        "variable_non_initialisee, retour_de_fonction_ignore, "
        "faute_de_frappe, mauvais_type_en_entree.\n\n"
        "Format attendu, strictement : le mot seul.",
    ),
)


#: Modèles comparés, dans l'ordre du protocole.
#:
#: Le champ `fournisseur` décide du client utilisé et de l'existence d'un coût :
#: un modèle servi localement ne facture rien.
MODELES: tuple[dict[str, str], ...] = (
    {"nom": "openai/gpt-oss-120b", "fournisseur": "groq"},
    {"nom": "openai/gpt-oss-20b", "fournisseur": "groq"},
    {"nom": "qwen/qwen3.6-27b", "fournisseur": "groq"},
    {"nom": "qwen3:4b", "fournisseur": "ollama"},
)

#: Nombre de répétitions par couple (modèle, prompt).
#:
#: Trois, pour mesurer la DISPERSION de la latence — pas pour moyenner la
#: qualité, qui ne varie pas d'une répétition à l'autre à cette température.
#: Même raisonnement que pour les mesures de conversion Spark, où deux
#: exécutions au repos tenaient dans 2 % d'écart et une troisième, sous
#: contention disque, s'en écartait de 17 %.
REPETITIONS = 3
