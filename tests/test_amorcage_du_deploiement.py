"""
Amorçage d'un déploiement neuf : ce que le conteneur fait au démarrage.

Compétence visée : C13 (épreuve E3) — livraison et exécution
Compétences concernées : C17 (E4) — application web ; C18 (E3) — tests

Les migrations créent les tables ; elles ne les remplissent pas. Sur une base
vierge, l'onglet Référentiel et le catalogue de cours seraient donc vides
alors que les fichiers source voyagent dans l'image. `docker/entree-web.sh`
comble cet écart en amorçant les deux jeux de référence lorsqu'ils manquent.

Ces tests portent sur ce que le script appelle, exécuté ici sur la base de
test — qui est vierge, exactement comme celle d'un déploiement neuf. Ce qu'ils
défendent : **un déploiement à froid sert des données, pas des pages vides**,
et **un redémarrage ne republie rien**.
"""

import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.courses.models import CoursDeReference, PartieDeCours
from apps.referentiel.models import Competence, Referentiel

#: Le script de démarrage. Les tests lisent ses commandes plutôt que de les
#: recopier : une divergence entre le script livré et ce qui est testé ici
#: serait précisément le défaut que ces tests existent pour empêcher.
ENTREE = Path("docker/entree-web.sh")

FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


def test_le_script_de_demarrage_amorce_les_deux_jeux_de_reference():
    """
    Le script livré appelle bien les deux imports, sur les bons fichiers.

    Compétence visée : C13 (épreuve E3)

    Choix : lire le script plutôt que de le supposer. Motivation : le reste du
    fichier vérifie que les commandes fonctionnent ; ce test-ci vérifie
    qu'elles sont effectivement appelées au démarrage. Sans lui, les deux
    imports pourraient être retirés du script sans qu'aucun test ne bronche.
    """
    script = ENTREE.read_text(encoding="utf-8")

    assert "manage.py importer_referentiel" in script
    assert FICHIER_REFERENTIEL in script
    assert "manage.py importer_cours" in script

    # Les migrations d'abord : un import sur un schéma absent échouerait.
    assert script.index("manage.py migrate") < script.index("manage.py importer_referentiel")


def test_les_imports_sont_gardes_par_un_test_de_presence():
    """
    L'amorçage n'a lieu que si la base est vide.

    Compétence visée : C13 (épreuve E3)

    Ce que ce test défend est mesuré : `importer_cours` met de côté les cours
    actifs et en publie de nouveaux à chaque exécution. L'hébergeur redémarrant
    le conteneur à chaque déploiement et à chaque réveil, un import
    inconditionnel accumulerait des générations identiques de cours. La garde
    rend l'amorçage idempotent par construction, et ce test empêche qu'on la
    retire par simplification.
    """
    script = ENTREE.read_text(encoding="utf-8")

    for commande in ("importer_referentiel", "importer_cours"):
        # L'appel réel, pas la mention en commentaire : le script documente la
        # relance manuelle de `importer_cours`, et la chercher sans le chemin
        # de l'interpréteur tomberait sur ce commentaire.
        position = script.index(f"/app/.venv/bin/python manage.py {commande}")
        avant = script[:position]
        # Le `if` le plus proche au-dessus de l'appel doit être une garde de
        # présence, pas autre chose.
        derniere_garde = avant.rindex("if [ ")
        garde = avant[derniere_garde:]
        assert '= "False" ]' in garde, f"{commande} n'est pas gardée par un test de présence"


@pytest.mark.django_db
def test_une_base_vierge_recoit_le_referentiel_et_les_cours():
    """
    Sur une base vide, les deux imports produisent des données consultables.

    Compétence visée : C13 (épreuve E3)
    Compétence concernée : C17 (E4)

    C'est la vérification qui manquait : jusqu'ici les imports n'avaient été
    exécutés que sur la base de développement, déjà peuplée. Le motif d'échec
    le plus fréquent du projet est celui-là — vérifié dans un contexte,
    employé dans un autre.
    """
    assert not Referentiel.objects.exists()
    assert not CoursDeReference.objects.exists()

    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer", stdout=StringIO())

    assert Referentiel.objects.filter(est_actif=True).count() == 1, (
        "l'interface n'affiche que le référentiel actif : il en faut un, et un seul"
    )
    assert Competence.objects.count() == 21, "le référentiel porte 21 compétences"

    call_command("importer_cours", stdout=StringIO())

    actifs = CoursDeReference.objects.filter(remplace_le__isnull=True)
    assert actifs.count() == 7, "sept compétences du module Python portent un cours"
    assert all(cours.statut == CoursDeReference.PUBLIE for cours in actifs)

    parties = PartieDeCours.objects.filter(cours__in=actifs)
    assert parties.count() > 30, "chaque cours rassemble plusieurs fichiers"
    assert all(partie.contenu.strip() for partie in parties), "aucune partie vide"
    assert all(partie.fichier_source for partie in parties), "chaque partie cite sa source"


@pytest.mark.django_db
def test_le_referentiel_amorce_deux_fois_ne_se_duplique_pas():
    """
    Relancer l'import du référentiel ne crée pas de seconde copie.

    Compétence visée : C13 (épreuve E3)

    La garde du script évite ce cas, mais l'import reste appelable à la main.
    Il doit rester sûr.
    """
    for _ in range(2):
        call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer", stdout=StringIO())

    assert Referentiel.objects.filter(est_actif=True).count() == 1
    assert Competence.objects.count() == 21
