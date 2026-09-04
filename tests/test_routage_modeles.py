"""
Le routage des modèles par agent, et son ordre de résolution.

Compétence visée : C21 (épreuve E5) — contrôle de non-régression d'un incident
Compétences concernées : C10 (E3) — intégration du modèle ; C7 (E2) ; C18 (E4)

Le 25 août 2026, l'identifiant `meta-llama/llama-4-scout-17b-16e-instruct`
était écrit en dur dans trois fichiers d'agents. Groq l'a retiré de son
catalogue, et toute la couche d'intelligence artificielle est tombée d'un coup
(incident 020, décision 001).

La résolution n'a pas consisté à remplacer l'identifiant — elle a consisté à
faire en sorte qu'aucun identifiant ne soit plus écrit dans le code. Ces tests
gardent les trois propriétés qui rendent cette résolution effective : l'ordre de
résolution est respecté, un agent inconnu échoue bruyamment, et la bascule vers
le repli local est un choix explicite.

Sans eux, la seule preuve que le routage fonctionne serait de rejouer la panne.
"""

import pytest

from apps.agents.tools.model_config import (
    AGENTS_CONNUS,
    MODELE_QUALITE,
    MODELE_RAPIDE,
    ROUTAGE_PAR_DEFAUT,
    get_model_for,
    use_local_llm,
)


@pytest.fixture(autouse=True)
def environnement_vierge(monkeypatch):
    """
    Aucune variable de modèle n'est héritée de la machine qui exécute la suite.

    Compétence visée : C18 (épreuve E4)

    Un `.env` local qui porterait `GROQ_MODEL` ferait passer ou échouer ces
    tests selon le poste. Le troisième niveau de résolution — le routage par
    défaut — ne serait alors jamais réellement éprouvé.
    """
    for agent in AGENTS_CONNUS:
        monkeypatch.delenv(f"GROQ_MODEL_{agent.upper()}", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("USE_LOCAL_LLM", raising=False)


# --- L'ordre de résolution, niveau par niveau ---


@pytest.mark.parametrize("agent", AGENTS_CONNUS)
def test_sans_aucune_variable_le_routage_par_defaut_s_applique(agent):
    """
    Troisième niveau : le routage par défaut du module.

    Compétence visée : C10 (épreuve E3)

    C'est le comportement hors configuration, celui qui doit rester juste
    quand personne n'a rien posé dans l'environnement.
    """
    assert get_model_for(agent) == ROUTAGE_PAR_DEFAUT[agent]


def test_le_routage_par_defaut_distingue_le_raisonnement_de_la_latence():
    """
    Les quatre agents ne reçoivent pas tous le même modèle, et c'est le sujet.

    Compétence visée : C7 (épreuve E2), C10 (E3)

    Researcher et Pedagogue produisent des réponses qui demandent du
    raisonnement ; Coach et Watcher sont soumis à une latence perçue
    directement. Le benchmark C7 a confirmé ce partage sur des mesures. Un
    routage qui rendrait le même modèle pour les quatre viderait cette
    décision de son contenu sans qu'aucun test n'échoue.
    """
    assert get_model_for("researcher") == MODELE_QUALITE
    assert get_model_for("pedagogue") == MODELE_QUALITE
    assert get_model_for("coach") == MODELE_RAPIDE
    assert get_model_for("watcher") == MODELE_RAPIDE


def test_la_variable_globale_prime_sur_le_routage_par_defaut(monkeypatch):
    """
    Deuxième niveau : `GROQ_MODEL` couvre tous les agents.

    Compétence visée : C10 (épreuve E3), C21 (E5)

    C'est le levier qui répare une panne comme celle du 25 août sans toucher
    au code : le fournisseur retire un modèle, on en désigne un autre par
    l'environnement, et le service repart.
    """
    monkeypatch.setenv("GROQ_MODEL", "un/modele-de-remplacement")

    for agent in AGENTS_CONNUS:
        assert get_model_for(agent) == "un/modele-de-remplacement"


def test_la_variable_d_un_agent_prime_sur_la_variable_globale(monkeypatch):
    """
    Premier niveau : un seul agent bascule, les autres ne bougent pas.

    Compétence visée : C10 (épreuve E3)

    C'est l'exigence pratique de la soutenance — montrer un agent sur un autre
    modèle sans redéployer, et sans emporter les trois autres avec lui.
    """
    monkeypatch.setenv("GROQ_MODEL", "un/modele-global")
    monkeypatch.setenv("GROQ_MODEL_COACH", "un/modele-pour-le-coach")

    assert get_model_for("coach") == "un/modele-pour-le-coach"
    assert get_model_for("watcher") == "un/modele-global"
    assert get_model_for("researcher") == "un/modele-global"


# --- L'échec explicite ---


@pytest.mark.parametrize("inconnu", ["", "coatch", "Researcher ", "pedagog", "tuteur"])
def test_un_agent_inconnu_leve_une_erreur_au_lieu_de_choisir_pour_nous(inconnu):
    """
    Une faute de frappe dans un nom d'agent est visible immédiatement.

    Compétence visée : C21 (épreuve E5), C10 (E3)

    Le repli silencieux sur un modèle par défaut est le comportement à
    proscrire : l'agent recevrait un modèle qui n'est pas le sien, la réponse
    serait plausible, et rien ne signalerait l'écart. C'est le motif de la
    famille A du registre d'incidents — un rapport qui ne correspond pas à
    l'effet.

    Note : `Researcher ` avec une majuscule et une espace **est** un agent
    connu, la fonction normalisant la casse et les espaces. Ce cas est ici
    pour fixer cette normalisation, non pour lever une erreur.
    """
    if inconnu.lower().strip() in ROUTAGE_PAR_DEFAUT:
        assert get_model_for(inconnu) == ROUTAGE_PAR_DEFAUT[inconnu.lower().strip()]
        return

    with pytest.raises(ValueError) as erreur:
        get_model_for(inconnu)

    # Le message nomme les agents attendus : il doit servir à qui le lit.
    assert "Agent inconnu" in str(erreur.value)
    for agent in AGENTS_CONNUS:
        assert agent in str(erreur.value)


def test_aucun_identifiant_de_modele_n_est_ecrit_en_dur_dans_les_agents():
    """
    Le défaut qui a causé l'incident ne peut pas revenir par la porte de service.

    Compétence visée : C21 (épreuve E5)

    C'est le contrôle qui garde la résolution elle-même. Externaliser la
    configuration ne sert à rien si un agent écrit à nouveau un identifiant
    dans son propre fichier — ce que rien n'empêche, et que personne ne
    remarquerait avant le prochain retrait de modèle.
    """
    from pathlib import Path

    agents = sorted(Path("apps/agents").glob("agent_*.py"))
    assert agents, "aucun fichier d'agent trouvé : le contrôle ne porte sur rien"

    fautifs = []
    for fichier in agents:
        contenu = fichier.read_text(encoding="utf-8")
        for marqueur in ("openai/gpt-oss", "meta-llama/", "qwen/qwen"):
            if marqueur in contenu:
                fautifs.append(f"{fichier} contient {marqueur!r}")

    assert not fautifs, (
        "Un identifiant de modèle est écrit en dur dans un agent. Il doit venir "
        "de model_config.get_model_for() :\n  - " + "\n  - ".join(fautifs)
    )


# --- Le repli local ---


@pytest.mark.parametrize("valeur", ["1", "true", "TRUE", "yes", "Yes"])
def test_le_repli_local_s_active_par_un_drapeau_explicite(monkeypatch, valeur):
    """
    La bascule vers Ollama est une décision, pas une détection automatique.

    Compétence visée : C10 (épreuve E3), C21 (E5)
    """
    monkeypatch.setenv("USE_LOCAL_LLM", valeur)
    assert use_local_llm() is True


@pytest.mark.parametrize("valeur", ["", "0", "false", "non", "peut-être"])
def test_toute_valeur_non_reconnue_laisse_le_service_sur_le_cloud(monkeypatch, valeur):
    """
    Le défaut est asymétrique : une valeur douteuse ne bascule pas le service.

    Compétence visée : C10 (épreuve E3)

    Le repli local est deux ordres de grandeur plus lent — 92,8 s de médiane
    contre 0,75 (benchmark C7). Y basculer par accident, sur une variable mal
    orthographiée, rendrait le service inutilisable sans qu'aucune erreur
    n'apparaisse.
    """
    monkeypatch.setenv("USE_LOCAL_LLM", valeur)
    assert use_local_llm() is False


def test_sans_drapeau_le_service_reste_sur_le_fournisseur_distant():
    """
    Compétence visée : C10 (épreuve E3)
    """
    assert use_local_llm() is False
