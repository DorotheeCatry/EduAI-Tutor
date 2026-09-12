"""
Les agents ne fabriquent pas de contenu quand la génération échoue.

Compétence visée : C10 (épreuve E3) — agents et interactions
Compétences concernées : C21 (E5) — traitement des anomalies ; C17 (E4)

Le Coach rendait, en cas d'échec, un quiz d'exemple : « Question d'exemple sur
X », quatre options « Option A » à « Option D », et `correct_answer: 0`.
L'application l'affichait comme un vrai quiz. Il était répondable, notable, et
sa bonne réponse était l'option A, choisie arbitrairement. L'apprenant qui
répondait autre chose enregistrait un `UserMistake`, qui alimente
`notions_a_revoir`, que Koda cite dans sa salutation : une erreur inventée
devenait une notion à revoir.

Ces tests défendent trois règles :
**un échec se dit**, **rien ne s'invente**, et **la trace se journalise**.
"""

import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.agents.agent_coach import GenerationImpossible, generate_quiz

REPERTOIRE_AGENTS = Path("apps/agents")


# --- Le Coach lève au lieu d'inventer --------------------------------------


def test_un_modele_injoignable_leve_au_lieu_de_rendre_un_quiz():
    """
    Compétence visée : C10 (épreuve E3), C21 (E5)

    L'appel au fournisseur échoue : aucun quiz ne peut être produit, et c'est
    cela qu'il faut dire. Rendre un quiz d'exemple reviendrait à répondre à la
    question « le modèle a-t-il répondu ? » par « oui ».
    """
    with patch("apps.agents.agent_coach.get_coach_chain") as chaine:
        chaine.return_value.invoke.side_effect = ConnectionError("réseau coupé")

        with pytest.raises(GenerationImpossible) as echec:
            generate_quiz("les listes", 5, "fr")

    assert "n'a pas répondu" in str(echec.value)
    # La cause d'origine est conservée : sans elle, le journal dirait qu'un
    # quiz a échoué sans dire pourquoi.
    assert isinstance(echec.value.__cause__, ConnectionError)


def test_une_reponse_hors_format_leve_au_lieu_de_rendre_un_quiz():
    """
    Compétence visée : C10 (épreuve E3), C21 (E5)

    Le modèle a répondu, mais pas au format attendu : `parse_text_quiz` n'en
    tire aucune question. C'est l'échec le plus fréquent des deux, et le plus
    facile à masquer — il ressemble à un succès.
    """
    with patch("apps.agents.agent_coach.get_coach_chain") as chaine:
        chaine.return_value.invoke.return_value = {
            "text": "Bien sûr ! Voici un quiz sur les listes."
        }

        with pytest.raises(GenerationImpossible) as echec:
            generate_quiz("les listes", 5, "fr")

    assert "aucune question" in str(echec.value)


def test_un_quiz_analysable_est_rendu_tel_quel():
    """
    Le chemin nominal reste intact.

    Compétence visée : C10 (épreuve E3)

    Un test qui ne vérifierait que les échecs laisserait passer une correction
    qui casse le succès.
    """
    reponse = (
        "Q1. Quelle est la sortie de print([1, 2][::-1]) ?\n"
        "A. [2, 1]\nB. [1, 2]\nC. Erreur\nD. None\n"
        "Réponse: A\nExplication: Le slice inverse la liste.\n"
    )
    with patch("apps.agents.agent_coach.get_coach_chain") as chaine:
        chaine.return_value.invoke.return_value = {"text": reponse}
        quiz = generate_quiz("les listes", 1, "fr")

    assert len(quiz["questions"]) == 1
    assert quiz["questions"][0]["correct_answer"] == 0


def test_la_generation_d_exercice_du_coach_a_ete_retiree():
    """
    Une seule implémentation de la génération d'exercices, et c'est la vivante.

    Compétence visée : C10 (épreuve E3), C18 (E4)

    `generate_code_exercise` portait le même repli fabriqué — solution attendue
    `print('Hello World')`, test `{"input": "test", "expected": "result"}` — et
    n'avait aucun appelant. La génération d'exercices de l'application passe par
    `apps/exercises/views.py`, qui compose sa propre invite et appelle
    `answer_question`.

    Elle a donc été supprimée plutôt que corrigée. Une seconde implémentation
    que personne n'exécute est du code que personne ne corrige — c'est
    exactement ce qui lui était arrivé. Ce test empêche qu'elle revienne.
    """
    import apps.agents.agent_coach as coach

    assert not hasattr(coach, "generate_code_exercise")
    assert not hasattr(coach, "get_code_exercise_chain")


def test_le_coach_ne_contient_plus_aucun_contenu_fabrique():
    """
    Le contenu d'exemple a disparu du fichier, pas seulement du chemin d'appel.

    Compétence visée : C10 (épreuve E3), C18 (E4)

    Une valeur de repli laissée dans le module y serait recâblée à la première
    correction pressée. Ce test tient sur la source.
    """
    module = ast.parse(
        REPERTOIRE_AGENTS.joinpath("agent_coach.py").read_text(encoding="utf-8"))

    # Les docstrings sont écartées : elles CITENT le contenu fabriqué pour
    # expliquer ce qui a été retiré et pourquoi, ce qui est précisément la
    # trace qu'on veut garder. Ce qui est proscrit, c'est une chaîne que le
    # module peut produire — donc une chaîne du code.
    docstrings = set()
    for noeud in ast.walk(module):
        if isinstance(noeud, (ast.Module, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef)):
            texte = ast.get_docstring(noeud, clean=False)
            if texte is not None:
                docstrings.add(texte)

    litteraux = [
        noeud.value for noeud in ast.walk(module)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
        and noeud.value not in docstrings
    ]

    for fabrique in ("Question d'exemple", "Example question", "Option A",
                     "Hello World", '"expected": "result"'):
        coupables = [texte for texte in litteraux if fabrique in texte]
        assert not coupables, (
            f"{fabrique!r} est un contenu fabriqué, il ne doit plus être produit"
        )


# --- L'orchestrateur rend l'échec lisible ----------------------------------


def test_l_orchestrateur_rend_le_motif_et_aucune_question(caplog):
    """
    `create_quiz` transforme l'exception en réponse lisible par la vue.

    Compétence visée : C10 (épreuve E3), C17 (E4), C21 (E5)

    Les deux vues de quiz vérifient déjà la liste de questions avant d'en faire
    quoi que ce soit : une liste vide y produit un message d'erreur, jamais une
    partie lancée sur du vide. Le motif les accompagne pour être affiché.

    Le test appelle la méthode sur un objet minimal plutôt que sur un
    orchestrateur complet, comme le fait déjà `tests/test_quotas.py` :
    construire ce dernier chargerait les chaînes RAG et le corpus vectoriel
    sans rien ajouter à ce qui est éprouvé ici.
    """
    from apps.agents.agent_orchestrator import AIOrchestrator

    orchestrateur = SimpleNamespace(
        user=None, pour_service_ia=False, watcher=MagicMock(),
        _decompter=lambda: None,
    )

    with patch("apps.agents.agent_orchestrator.generate_quiz",
               side_effect=GenerationImpossible("le modèle n'a pas répondu")), \
         caplog.at_level(logging.WARNING, logger="apps.agents.agent_orchestrator"):
        resultat = AIOrchestrator.create_quiz(orchestrateur, "les listes", 5)

    assert resultat["questions"] == [], "aucune question inventée"
    assert "n'a pas répondu" in resultat["error"], "le motif est transmis"
    assert resultat["topic"] == "les listes"
    assert any("non engendre" in trace.message for trace in caplog.records), (
        "l'échec laisse une trace journalisée, pas seulement une réponse vide"
    )


# --- La journalisation ------------------------------------------------------


def test_la_couche_agents_journalise_au_lieu_d_afficher():
    """
    Plus aucun `print` dans la couche agents.

    Compétence visée : C18 (épreuve E4), C20 (E5)

    `agent_orchestrator.py` déclarait un `logger` puis faisait treize `print`,
    émojis compris. Sur l'hébergeur, une trace écrite sur la sortie standard
    n'a ni niveau ni horodatage : elle ne peut être ni filtrée, ni rattachée à
    la requête qui l'a produite. Le cahier des charges impose le logging
    structuré ; ce test le rend vérifiable.
    """
    fautifs = []
    for module in sorted(REPERTOIRE_AGENTS.rglob("*.py")):
        if "migrations" in module.parts:
            continue
        for numero, ligne in enumerate(
                module.read_text(encoding="utf-8").splitlines(), start=1):
            nu = ligne.strip()
            if nu.startswith("print(") or " print(" in nu and not nu.startswith("#"):
                fautifs.append(f"{module}:{numero}")

    assert not fautifs, "à journaliser plutôt qu'à afficher : " + ", ".join(fautifs)
