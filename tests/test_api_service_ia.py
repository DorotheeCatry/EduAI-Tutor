"""
Contrôles de l'API du service IA.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA
Compétence visée : C13 (épreuve E3) — sécurité

Aucun test de ce fichier n'appelle le fournisseur de modèles. Ce n'est pas une
limite mais un choix : les points de terminaison de génération déclenchent des
appels facturés, et une suite de tests qui coûte de l'argent à chaque exécution
finit par n'être plus exécutée. Ce qui est éprouvé ici — authentification,
validation, forme des erreurs, documentation — se vérifie sans dépenser un
jeton, et couvre ce qui casse le plus souvent.
"""

from __future__ import annotations

import os

import pytest

CLE_ESSAI = "cle-de-test-uniquement-locale"


@pytest.fixture(scope="module")
def client(request):
    """
    Client d'essai du service FastAPI.

    Compétence visée : C18 (épreuve E4)

    Choix : une clé de service propre au test, injectée dans l'environnement.
    Motivation : la suite ne doit dépendre d'aucune clé réelle. Le service lit
    `SERVICE_IA_CLES` à chaque requête, ce qui rend l'injection possible sans
    redémarrage.
    """
    ancienne = os.environ.get("SERVICE_IA_CLES")
    os.environ["SERVICE_IA_CLES"] = CLE_ESSAI

    try:
        from fastapi.testclient import TestClient

        from service_ia.main import application
    except Exception as exception:  # noqa: BLE001 — dépendance absente
        pytest.skip(f"service IA non chargeable : {type(exception).__name__}: {exception}")

    with TestClient(application) as essai:
        yield essai

    if ancienne is None:
        os.environ.pop("SERVICE_IA_CLES", None)
    else:
        os.environ["SERVICE_IA_CLES"] = ancienne


# --- Authentification ----------------------------------------------------

@pytest.mark.parametrize("chemin,corps", [
    ("/ai/cours", {"sujet": "les décorateurs"}),
    ("/ai/explication", {"notion": "les listes"}),
    ("/ai/exercice", {"sujet": "les boucles"}),
    ("/ai/feedback", {"enonce": "somme", "code_soumis": "x = 1"}),
    ("/ai/recherche", {"requete": "python"}),
])
def test_sans_cle_tout_est_refuse(client, chemin, corps):
    """
    Les cinq points de terminaison exigent une clé de service.

    Compétence visée : C9 (épreuve E2) — OWASP API2
    """
    assert client.post(chemin, json=corps).status_code == 401


def test_une_cle_invalide_est_refusee_comme_une_cle_absente(client):
    """
    Le service ne dit pas à l'appelant si l'en-tête est le bon.

    Compétence visée : C13 (épreuve E3)

    Distinguer « clé absente » de « clé fausse » renseignerait un attaquant sur
    le nom de l'en-tête attendu, ce qui est déjà un renseignement.
    """
    sans = client.post("/ai/cours", json={"sujet": "python"})
    fausse = client.post(
        "/ai/cours", json={"sujet": "python"},
        # Valeur en ASCII pur : les en-têtes HTTP ne transportent pas
        # d'accents, et un client qui en enverrait échouerait avant même
        # d'atteindre le service.
        headers={"X-Cle-Service": "cle-inventee"},
    )

    assert sans.status_code == fausse.status_code == 401
    assert sans.json()["detail"] == fausse.json()["detail"]


def test_la_sonde_de_sante_reste_ouverte(client):
    """
    `/ai/sante` répond sans clé, délibérément.

    Compétence visée : C9 (épreuve E2)

    Une sonde de santé est interrogée par un orchestrateur ou un superviseur,
    auxquels on ne confie pas un secret d'appel. Elle ne divulgue que des noms
    de modèles et des décomptes.
    """
    reponse = client.get("/ai/sante")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] in {"operationnel", "degrade", "indisponible"}
    assert set(corps["agents_disponibles"]) == {
        "researcher", "pedagogue", "coach", "watcher",
    }


def test_la_sonde_de_sante_n_appelle_pas_le_fournisseur(client):
    """
    L'état du fournisseur est déclaratif, et le contrat le dit.

    Compétence visée : C9 (épreuve E2) — non-régression de principe

    Un appel réel serait facturé, et une sonde interrogée toutes les quinze
    secondes coûterait plus que le service. Le champ dit si le fournisseur est
    *configuré*, pas s'il *répond* — prétendre le contraire reproduirait le
    motif des incidents du projet.
    """
    corps = client.get("/ai/sante").json()

    for fournisseur in corps["disponibilite_fournisseur"]:
        assert set(fournisseur) == {"nom", "configure", "detail"}
        assert isinstance(fournisseur["configure"], bool)


# --- Validation des entrées ----------------------------------------------

@pytest.mark.parametrize("chemin,corps,raison", [
    ("/ai/cours", {"sujet": ""}, "sujet vide"),
    ("/ai/cours", {"sujet": "   "}, "sujet composé d'espaces"),
    ("/ai/cours", {"sujet": "python", "difficulte": "expert"}, "difficulté hors énumération"),
    ("/ai/exercice", {"sujet": "python", "nombre_questions": 99}, "au-delà du plafond"),
    ("/ai/exercice", {"sujet": "python", "nombre_questions": 0}, "en deçà du plancher"),
    ("/ai/recherche", {"requete": "python", "nombre_fragments": 500}, "fragments hors bornes"),
    ("/ai/feedback", {"enonce": "somme"}, "code manquant"),
    ("/ai/explication", {}, "notion manquante"),
])
def test_les_entrees_invalides_sont_refusees(client, chemin, corps, raison):
    """
    Pydantic refuse ce qui n'entre pas dans le contrat.

    Compétence visée : C9 (épreuve E2) — validation des entrées

    Le cas du sujet composé d'espaces mérite d'être retenu : `min_length` compte
    les caractères, espaces compris. « ␣␣␣ » franchit la contrainte de longueur
    et produit un prompt vide — d'où un validateur explicite sur la chaîne
    nettoyée.
    """
    reponse = client.post(
        chemin, json=corps, headers={"X-Cle-Service": CLE_ESSAI},
    )
    assert reponse.status_code == 422, f"{raison} devrait être refusé"


def test_le_message_d_erreur_nomme_le_champ_fautif(client):
    """
    Un refus doit être exploitable par l'appelant.

    Compétence visée : C9 (épreuve E2)
    """
    reponse = client.post(
        "/ai/cours", json={"sujet": "  "},
        headers={"X-Cle-Service": CLE_ESSAI},
    )
    detail = reponse.json()["detail"]

    assert any("sujet" in str(erreur.get("loc", "")) for erreur in detail)


# --- Documentation --------------------------------------------------------

def test_le_schema_declare_l_authentification(client):
    """
    La documentation dit qu'une clé est exigée, et laquelle.

    Compétence visée : C9 (épreuve E2) — OWASP API9

    Le point avait été manqué : les routes étaient protégées et le schéma n'en
    disait rien. Un consommateur lisant la documentation aurait découvert
    l'exigence par un 401 sans explication.
    """
    schema = client.get("/ai/openapi.json").json()

    schemas = schema["components"]["securitySchemes"]
    assert any(
        definition.get("name") == "X-Cle-Service"
        for definition in schemas.values()
    ), "le schéma OpenAPI doit nommer l'en-tête d'authentification"


def test_les_routes_de_generation_sont_marquees_protegees(client):
    """
    Le schéma distingue les routes protégées de la sonde ouverte.

    Compétence visée : C9 (épreuve E2)
    """
    chemins = client.get("/ai/openapi.json").json()["paths"]

    for chemin in ("/ai/cours", "/ai/explication", "/ai/exercice",
                   "/ai/feedback", "/ai/recherche"):
        assert chemins[chemin]["post"].get("security"), f"{chemin} devrait être protégé"

    assert not chemins["/ai/sante"]["get"].get("security")


def test_aucune_route_d_ecriture_n_est_exposee(client):
    """
    Le service ne persiste rien : il n'expose ni PUT, ni PATCH, ni DELETE.

    Compétence visée : C9 (épreuve E2) — OWASP API5
    """
    chemins = client.get("/ai/openapi.json").json()["paths"]
    methodes = {m for operations in chemins.values() for m in operations}

    assert methodes <= {"get", "post"}, f"méthodes inattendues : {methodes - {'get', 'post'}}"
