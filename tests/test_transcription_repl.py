"""
Exécuter les blocs de code des cours, écrits comme des sessions au prompt.

Compétence visée : C17 (épreuve E4) — application web
Compétence concernée : C21 (E5) — incidents

Les supports du corpus sont des transcriptions de sessions interactives :

    >>> furniture = ['table', 'chair']
    >>> furniture[0]
    # 'table'

Ce format se lit bien et **ne s'exécute pas** : rendu tel quel à Python, il
échoue dès la première ligne. Le bouton « Run » posé sur ces blocs échouait
donc systématiquement, alors que la même cellule exécutait sans peine le code
tapé à la main — deux comportements pour un seul geste, sans que rien ne dise
pourquoi.

Ce que ces tests défendent : **une session se convertit, un script ne se
touche pas**.
"""

import pytest
from django.urls import reverse

from apps.courses.transcription import ressemble_a_une_session, transcrire


def test_un_script_ordinaire_ressort_intact():
    """
    La conversion ne s'applique qu'aux sessions, jamais au code écrit à la main.

    Compétence visée : C17 (épreuve E4)

    C'est la garantie qui compte : la même cellule sert aux deux, et convertir
    à tort un script valide le casserait.
    """
    script = "x = 1\nfor i in range(3):\n    print(i, x)\n"

    assert not ressemble_a_une_session(script)
    assert transcrire(script) == script


def test_une_session_devient_un_script_qui_affiche():
    """
    Les amorces partent, les résultats recopiés aussi, les valeurs s'affichent.

    Compétence visée : C17 (épreuve E4)

    Au prompt, écrire `furniture[0]` montre la valeur ; dans un script, cela ne
    montre rien. Une conversion qui se contenterait de retirer les `>>>`
    produirait un code qui s'exécute sans rien afficher : réparé en apparence,
    inutile à lire.
    """
    session = (
        ">>> furniture = ['table', 'chair']\n"
        ">>> furniture[0]\n"
        "# 'table'\n"
        ">>> furniture[1]\n"
        "# 'chair'\n"
    )

    obtenu = transcrire(session)

    assert ">>>" not in obtenu
    assert "furniture = ['table', 'chair']" in obtenu
    assert "print(furniture[0])" in obtenu
    assert "print(furniture[1])" in obtenu


def test_les_lignes_de_continuation_sont_reprises():
    """
    Un bloc écrit sur plusieurs lignes garde sa structure.

    Compétence visée : C17 (épreuve E4)

    Les `...` du prompt portent le corps des boucles et des conditions.
    Les écarter réduirait un `for` à son en-tête, donc à une erreur.
    """
    session = (
        ">>> for meuble in ['table', 'chair']:\n"
        "...     print(meuble)\n"
        "table\n"
        "chair\n"
    )

    obtenu = transcrire(session)

    assert obtenu.splitlines()[0] == "for meuble in ['table', 'chair']:"
    assert obtenu.splitlines()[1] == "    print(meuble)"
    # Les deux lignes de résultat recopiées sous le prompt sont écartées :
    # gardées, elles seraient du texte libre au milieu du script.
    assert "\ntable" not in obtenu


def test_un_print_deja_ecrit_n_est_pas_enveloppe_deux_fois():
    """
    `print(x)` reste `print(x)`.

    Compétence visée : C17 (épreuve E4)
    """
    assert transcrire(">>> print('bonjour')\nbonjour\n").strip() == "print('bonjour')"


def test_une_session_incomplete_est_rendue_telle_quelle():
    """
    Un extrait qui ne se compile pas n'est pas deviné.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    L'exécuteur signale l'erreur avec sa ligne ; deviner ici masquerait ce
    message par un autre, moins juste.
    """
    obtenu = transcrire(">>> for x in [1, 2:\n")

    assert "for x in [1, 2:" in obtenu


@pytest.mark.django_db
def test_le_bloc_de_cours_s_execute_depuis_la_page(client, django_user_model):
    """
    Le bouton « Run » d'un bloc de cours rend bien une sortie.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — sécurité

    Le chemin complet, celui que l'apprenant emprunte : la vue reçoit la
    transcription telle qu'elle est affichée, et rend ce que Python affiche.
    """
    from apps.referentiel.models import Competence, Module, Referentiel

    referentiel = Referentiel.objects.create(code="essai", intitule="Essai",
                                             version="1", est_actif=True)
    module = Module.objects.create(referentiel=referentiel, code="m1",
                                   intitule="Module", ordre=1)
    competence = Competence.objects.create(module=module, code="c1",
                                           intitule="Compétence", ordre=1)

    utilisateur = django_user_model.objects.create_user(
        username="apprenant_run", password="mot-de-passe-de-test-1")
    client.force_login(utilisateur)

    reponse = client.post(
        reverse("courses:executer", args=[competence.code]),
        {"code": ">>> mots = ['a', 'b']\n>>> mots[1]\n# 'b'"},
        secure=True,
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["succes"] is True, corps["erreur"]
    assert corps["sortie"].strip() == "b"
