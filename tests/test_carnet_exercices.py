"""
Le carnet : plusieurs exercices à la suite, et son export Jupyter.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — sécurité ; C10 (E3)

Deux formes d'exercice coexistent désormais, et c'est délibéré : l'exercice
seul corrige par des tests et enregistre une soumission — il **mesure** ; le
carnet enchaîne les énoncés pour une séance et s'emporte en `.ipynb` — il
**accompagne**. Ces tests défendent ce qui distingue le second : la continuité,
l'export fidèle, et le fait qu'il ne transmet jamais la solution.
"""

import json

import pytest
from django.urls import reverse


@pytest.fixture
def exercices(django_user_model, db):
    """Deux exercices actifs, dont l'énoncé porte du Markdown."""
    from apps.exercises.models import Exercise

    auteur = django_user_model.objects.create_user(
        username="auteur_carnet", email="auteur.carnet@exemple.test",
        password="mot-de-passe-de-test-1")
    premier = Exercise.objects.create(
        title="Additionner", description="## Énoncé\n\nÉcrire `somme(a, b)`.",
        topic="fonctions", starter_code="def somme(a, b):\n    pass\n",
        solution="def somme(a, b):\n    return a + b\n",
        tests=[], created_by=auteur,
    )
    second = Exercise.objects.create(
        title="Compter", description="Compter les éléments d'une liste.",
        topic="listes", starter_code="# à vous\n",
        solution="len(ma_liste)", tests=[], created_by=auteur,
    )
    return premier, second


@pytest.fixture
def apprenant(client, django_user_model, db):
    utilisateur = django_user_model.objects.create_user(
        username="apprenant_carnet", email="apprenant.carnet@exemple.test",
        password="mot-de-passe-de-test-1")
    client.force_login(utilisateur)
    return utilisateur


def test_le_carnet_enchaine_les_exercices_choisis(client, apprenant, exercices):
    """
    Compétence visée : C17 (épreuve E4)
    """
    premier, second = exercices

    page = client.get(reverse("exercises:carnet"),
                      {"exercice": [premier.id, second.id]},
                      secure=True).content.decode()

    assert "Additionner" in page and "Compter" in page
    assert f'name="code-{premier.id}"' in page, "chaque énoncé a sa cellule"
    assert f'name="code-{second.id}"' in page


def test_l_enonce_est_mis_en_forme(client, apprenant, exercices):
    """
    Les énoncés sont du Markdown, comme les cours.

    Compétence visée : C17 (épreuve E4)

    Ils portent des titres, des listes et des blocs de code. Rendus par
    `linebreaks`, ils s'affichaient avec leurs dièses et leurs accents graves.
    """
    premier, _ = exercices

    page = client.get(reverse("exercises:carnet"), {"exercice": premier.id},
                      secure=True).content.decode()

    assert "<h2>Énoncé</h2>" in page, "les titres doivent être des titres"
    assert "## Énoncé" not in page, "le Markdown brut ne doit plus s'afficher"
    assert "cours-rendu" in page, "la feuille des cours s'applique"


def test_la_solution_n_est_jamais_transmise(client, apprenant, exercices):
    """
    Un carnet qui contiendrait la réponse cesse d'être un exercice.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3)

    C'est la règle de la décision 029, et elle vaut pour cette page comme pour
    l'exercice seul.
    """
    premier, second = exercices

    page = client.get(reverse("exercises:carnet"),
                      {"exercice": [premier.id, second.id]},
                      secure=True).content.decode()

    assert "return a + b" not in page
    assert "len(ma_liste)" not in page


def test_un_identifiant_inconnu_est_ignore_sans_faire_echouer(client, apprenant, exercices):
    """
    La liste peut avoir changé entre l'affichage et l'envoi.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    Un exercice retiré ne doit pas faire échouer la séance entière : il en
    sort.
    """
    premier, _ = exercices

    page = client.get(reverse("exercises:carnet"),
                      {"exercice": [premier.id, 999999, "abc"]},
                      secure=True)

    assert page.status_code == 200
    assert "Additionner" in page.content.decode()


def test_le_telechargement_rend_un_carnet_jupyter_valide(client, apprenant, exercices):
    """
    Le fichier s'ouvre dans Jupyter, et porte ce que l'apprenant a écrit.

    Compétence visée : C17 (épreuve E4)

    Choix : une requête POST portant le code saisi, et non un lien qui
    régénérerait le carnet depuis la base. Un lien rendrait toujours le code de
    départ, et le fichier ne vaudrait rien comme trace de travail.
    """
    premier, second = exercices

    reponse = client.post(reverse("exercises:carnet_ipynb"), {
        f"code-{premier.id}": "def somme(a, b):\n    return a + b\n",
        f"code-{second.id}": "print(len([1, 2, 3]))\n",
    }, secure=True)

    assert reponse.status_code == 200
    assert reponse["Content-Type"].startswith("application/x-ipynb+json")
    assert "attachment" in reponse["Content-Disposition"]
    assert ".ipynb" in reponse["Content-Disposition"]

    carnet = json.loads(reponse.content.decode())
    assert carnet["nbformat"] == 4 and carnet["nbformat_minor"] == 5
    assert carnet["metadata"]["kernelspec"]["name"] == "python3"

    types = [cellule["cell_type"] for cellule in carnet["cells"]]
    # Un titre, puis un couple énoncé/code par exercice.
    assert types == ["markdown", "markdown", "code", "markdown", "code"]
    assert all(cellule["id"] for cellule in carnet["cells"]), "nbformat 4.5 exige un id"

    code = "".join(carnet["cells"][2]["source"])
    assert code == "def somme(a, b):\n    return a + b\n", (
        "le carnet porte ce qui a été écrit, pas le code de départ"
    )


def test_le_carnet_part_sans_sortie_d_execution(client, apprenant, exercices):
    """
    Les cellules sont vierges de résultats.

    Compétence visée : C17 (épreuve E4)

    Un carnet exporté avec des sorties ferait croire à une exécution qui n'a
    pas eu lieu dans Jupyter — et le premier `Run` de l'apprenant les
    remplacerait sans qu'il comprenne d'où venaient les premières.
    """
    premier, _ = exercices

    reponse = client.post(reverse("exercises:carnet_ipynb"),
                          {f"code-{premier.id}": "print('bonjour')"}, secure=True)
    carnet = json.loads(reponse.content.decode())

    for cellule in carnet["cells"]:
        if cellule["cell_type"] == "code":
            assert cellule["outputs"] == []
            assert cellule["execution_count"] is None


def test_la_cellule_du_carnet_s_execute_sans_rien_enregistrer(client, apprenant, exercices):
    """
    Le carnet essaie ; il ne corrige pas et n'enregistre pas.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — sécurité

    Il emprunte l'exécuteur restreint commun : aucun second chemin d'exécution
    n'est ouvert, et aucune soumission n'est créée — la correction par les
    tests reste le fait de l'exercice seul.
    """
    from apps.exercises.models import ExerciseSubmission

    corps = client.post(reverse("exercises:carnet_executer"),
                        {"code": "print(sum([1, 2, 3]))"}, secure=True).json()

    assert corps["succes"] is True, corps["erreur"]
    assert corps["sortie"].strip() == "6"
    assert ExerciseSubmission.objects.count() == 0


# --- Engendrer une série d'énoncés ----------------------------------------

REPONSE_DU_MODELE = """Voici les exercices :
```json
[
 {"titre": "Somme d'une liste", "enonce": "Écrire `somme(nombres)`.",
  "code": "def somme(nombres):\\n    pass\\n"},
 {"titre": "Compter les mots", "enonce": "## Consigne\\n\\nCompter les mots.",
  "code": "def compter(texte):\\n    pass\\n"}
]
```"""


def test_la_serie_est_demandee_en_un_seul_appel(monkeypatch, django_user_model, db):
    """
    Cinq à vingt énoncés coûtent UNE génération, pas vingt.

    Compétence visée : C13 (épreuve E3) — quotas
    Compétence concernée : C10 (E3)

    Un appel par exercice épuiserait le quota d'une journée pour un seul
    carnet : quinze générations par défaut, vingt énoncés demandés. La série
    est donc produite d'un coup, et décomptée une fois.
    """
    from apps.exercises import generation_carnet

    appels = []

    class OrchestrateurFactice:
        def answer_question(self, invite):
            appels.append(invite)
            return {"answer": REPONSE_DU_MODELE}

    monkeypatch.setattr("apps.agents.agent_orchestrator.get_orchestrator",
                        lambda utilisateur: OrchestrateurFactice())

    utilisateur = django_user_model.objects.create_user(
        username="apprenant_serie", email="serie@exemple.test",
        password="mot-de-passe-de-test-1")

    exercices = generation_carnet.engendrer(utilisateur, "les listes", 8)

    assert len(appels) == 1, "une seule génération pour toute la série"
    assert "les listes" in appels[0] and "8" in appels[0]
    assert [e["titre"] for e in exercices] == ["Somme d'une liste", "Compter les mots"]
    assert exercices[0]["code"].startswith("def somme")


def test_le_nombre_demande_est_borne(monkeypatch, django_user_model, db):
    """
    En deçà de cinq, l'exercice seul fait mieux ; au-delà de vingt, la réponse
    se tronque.

    Compétence visée : C10 (épreuve E3)
    """
    from apps.exercises import generation_carnet

    demandes = []

    class OrchestrateurFactice:
        def answer_question(self, invite):
            demandes.append(invite)
            return {"answer": "[]"}

    monkeypatch.setattr("apps.agents.agent_orchestrator.get_orchestrator",
                        lambda utilisateur: OrchestrateurFactice())
    utilisateur = django_user_model.objects.create_user(
        username="apprenant_bornes", email="bornes@exemple.test",
        password="mot-de-passe-de-test-1")

    generation_carnet.engendrer(utilisateur, "les boucles", 200)
    generation_carnet.engendrer(utilisateur, "les boucles", 1)

    assert f"Nombre d'exercices : {generation_carnet.MAXIMUM}" in demandes[0]
    assert f"Nombre d'exercices : {generation_carnet.MINIMUM}" in demandes[1]


def test_une_reponse_illisible_donne_un_carnet_vide(monkeypatch, django_user_model, db):
    """
    Mieux vaut un carnet vide qu'un carnet inventé.

    Compétence visée : C10 (épreuve E3)
    Compétence concernée : C21 (E5)

    Ce qui n'est pas analysable est écarté : un carnet vide se voit, des
    énoncés fabriqués pour combler le silence, non.
    """
    from apps.exercises import generation_carnet

    class OrchestrateurFactice:
        def answer_question(self, invite):
            return {"answer": "Je ne peux pas répondre pour le moment."}

    monkeypatch.setattr("apps.agents.agent_orchestrator.get_orchestrator",
                        lambda utilisateur: OrchestrateurFactice())
    utilisateur = django_user_model.objects.create_user(
        username="apprenant_illisible", email="illisible@exemple.test",
        password="mot-de-passe-de-test-1")

    assert generation_carnet.engendrer(utilisateur, "les tuples", 5) == []


def test_le_carnet_melange_l_existant_et_l_engendre(monkeypatch, client, apprenant, exercices):
    """
    Les deux façons de composer se cumulent.

    Compétence visée : C17 (épreuve E4)
    """
    from apps.exercises import generation_carnet

    class OrchestrateurFactice:
        def answer_question(self, invite):
            return {"answer": REPONSE_DU_MODELE}

    monkeypatch.setattr("apps.agents.agent_orchestrator.get_orchestrator",
                        lambda utilisateur: OrchestrateurFactice())
    premier, _ = exercices

    page = client.get(reverse("exercises:carnet"), {
        "exercice": premier.id, "sujet": "les listes", "nombre": 5,
    }, secure=True).content.decode()

    assert "Additionner" in page, "l'exercice coché reste"
    # L'apostrophe du titre est échappée par le gabarit : on cherche la forme
    # rendue, pas la chaîne d'origine.
    assert "Somme d&#x27;une liste" in page or "Somme d'une liste" in page, (
        "les énoncés engendrés s'ajoutent"
    )
    assert "engendré pour cette séance" in page, "leur origine est dite"


def test_les_enonces_engendres_partent_dans_le_fichier(monkeypatch, client, apprenant, exercices):
    """
    Le `.ipynb` porte aussi ce qui n'est pas en base.

    Compétence visée : C17 (épreuve E4)

    Les énoncés engendrés vivent dans la session, pas dans le catalogue : leur
    texte vient de là, et seul leur code arrive du formulaire.
    """
    from apps.exercises import generation_carnet

    class OrchestrateurFactice:
        def answer_question(self, invite):
            return {"answer": REPONSE_DU_MODELE}

    monkeypatch.setattr("apps.agents.agent_orchestrator.get_orchestrator",
                        lambda utilisateur: OrchestrateurFactice())

    client.get(reverse("exercises:carnet"),
               {"sujet": "les listes", "nombre": 5}, secure=True)

    reponse = client.post(reverse("exercises:carnet_ipynb"),
                          {"code-g0": "def somme(nombres):\n    return sum(nombres)\n"},
                          secure=True)
    carnet = json.loads(reponse.content.decode())

    textes = "".join("".join(c["source"]) for c in carnet["cells"])
    assert "Somme d'une liste" in textes
    assert "return sum(nombres)" in textes, "le code écrit par l'apprenant est emporté"
