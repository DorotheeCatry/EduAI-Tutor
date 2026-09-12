"""
Koda répond à la question posée, et à la mesure de ce qui est demandé.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétences concernées : C13 (E3) — quotas ; C17 (E4) ; C4 (E1) — attribution

Dans la partie cours, Koda répondait à côté : un développement sur le sujet
général plutôt qu'une réponse à la demande. Trois causes, toutes couvertes ici.

1. **La chaîne RAG était construite sans invite**, donc `RetrievalQA` retombait
   sur le gabarit intégré de LangChain — en anglais, muet sur la longueur, et
   ordonnant de s'appuyer sur le contexte trouvé quel qu'il soit. Les consignes
   que les appelants ajoutaient à leur demande arrivaient dans le champ
   `question`, sous un gabarit qui disait déjà autre chose.

2. **L'enrichissement cherchait deux fois.** Il interrogeait le corpus
   documentaire, collait les fragments dans une invite, et passait cette invite
   entière à l'orchestrateur — qui s'en servait comme REQUÊTE de recherche dans
   une AUTRE collection. La réponse ne s'appuyait donc pas sur les sources
   affichées à l'apprenant.

Le troisième défaut du même signalement — le raccourci des politesses absent du
panneau flottant — est couvert par `tests/test_echange_courant.py`, avec le
reste de la reconnaissance des échanges courants.
"""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.courses.models import AjoutDeFiche
from apps.referentiel.models import Competence

FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def competence():
    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer",
                 stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante", email="apprenante@exemple.test",
        password="mot-de-passe-d-essai-2026")


# --- Le gabarit d'invite ---------------------------------------------------


def test_le_gabarit_du_chercheur_porte_les_consignes():
    """
    L'invite dit la langue, le périmètre et la longueur.

    Compétence visée : C10 (épreuve E3)

    Le gabarit par défaut de LangChain ne dit aucune des trois. Ce test tient
    sur le contenu du fichier, pas sur une formulation exacte : il vérifie que
    les trois consignes y sont, pas les mots qui les portent.
    """
    from apps.agents.agent_researcher import gabarit_de_reponse

    gabarit = gabarit_de_reponse()

    assert set(gabarit.input_variables) == {"context", "question"}
    modele = gabarit.template.lower()
    assert "français" in modele, "la langue de réponse est imposée"
    assert "proportionnée" in modele, "la règle de longueur est dans l'invite"
    assert "cette question" in modele, "le périmètre de la réponse est borné"
    assert "don't know" not in modele, (
        "le gabarit anglais par défaut ne doit plus servir"
    )


def test_la_chaine_rag_est_construite_avec_ce_gabarit():
    """
    Le gabarit est bien posé sur `RetrievalQA`, pas seulement écrit.

    Compétence visée : C10 (épreuve E3)

    Constaté : `from_chain_type` appelé sans `prompt` retombe silencieusement
    sur le gabarit intégré de la bibliothèque. Rien ne le signale — ni erreur,
    ni journal — et la seule trace visible est une réponse en anglais ou hors
    sujet. Ce test est le seul endroit qui le dirait.
    """
    from apps.agents import agent_researcher

    with patch.object(agent_researcher, "Chroma"), \
         patch.object(agent_researcher, "load_embedding_function"), \
         patch.object(agent_researcher, "get_llm"), \
         patch.object(agent_researcher, "RetrievalQA") as chaine:
        agent_researcher.get_researcher_chain()

    arguments = chaine.from_chain_type.call_args.kwargs
    assert "chain_type_kwargs" in arguments, (
        "sans cet argument, LangChain pose son gabarit anglais par défaut"
    )
    gabarit = arguments["chain_type_kwargs"]["prompt"]
    assert "proportionnée" in gabarit.template.lower()


# --- Une seule recherche, dans la bonne collection -------------------------


@pytest.mark.django_db
def test_l_enrichissement_ne_cherche_qu_une_fois(competence, apprenante):
    """
    La question part nue ; les extraits partent à part.

    Compétence visée : C10 (épreuve E3), C4 (E1)

    Constaté : l'invite complète — cadre, quatre fragments, consignes — partait
    comme `question`, et `RetrievalQA` l'employait comme requête d'embedding.
    On cherchait des documents avec un texte qui en contenait déjà quatre, et
    les fragments ainsi ramenés venaient de `eduai_knowledge_base` quand les
    sources affichées venaient de `eduai_corpus_documentaire`.

    Ce test tient les deux bouts : la question transmise est celle de
    l'apprenante, et les extraits sont passés par `extraits`, ce qui coupe la
    seconde recherche.
    """
    from apps.courses.services import enrichir

    fragment = MagicMock()
    fragment.page_content = "Une liste est une séquence modifiable."
    fragment.metadata = {"url_source": "https://exemple.test/listes",
                         "titre": "Listes", "code_licence": "CC-BY-4.0",
                         "attribution_requise": True}

    orchestrateur = MagicMock()
    orchestrateur.answer_question.return_value = {"answer": "Une réponse."}

    with patch("apps.courses.services._chercher_dans_le_corpus",
               return_value=[fragment]) as recherche, \
         patch("apps.agents.agent_orchestrator.get_orchestrator",
               return_value=orchestrateur):
        enrichir(apprenante, competence, "une liste c'est quoi ?",
                 origine=AjoutDeFiche.A_LA_DEMANDE)

    assert recherche.call_count == 1, "une seule interrogation du corpus"

    appel = orchestrateur.answer_question.call_args
    assert appel.args[0] == "une liste c'est quoi ?", (
        "le modèle reçoit les mots de l'apprenante, pas une invite composée"
    )
    extraits = appel.kwargs["extraits"]
    assert fragment.page_content in extraits, "les extraits servent de contexte"
    assert competence.intitule in extraits, (
        "la compétence travaillée est du contexte, pas de la question"
    )
