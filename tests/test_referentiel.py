"""
Tests du référentiel de compétences et de son import.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) ; C4 (E1) — chargement de données

Ces tests partent de la **commande réelle**, sur le **fichier réellement
livré**, et vérifient ce que la base contient après coup. C'est la parade à la
troisième famille d'incidents du projet : une couverture qui appellerait les
modèles directement, avec des données fabriquées, ne dirait rien de l'import
tel qu'il sera lancé.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.referentiel.models import Competence, Module, Referentiel

FICHIER_LIVRE = "apps/referentiel/donnees/eduai-2026.json"


def _importer(chemin, *options):
    sortie = StringIO()
    call_command("importer_referentiel", chemin, *options, stdout=sortie)
    return sortie.getvalue()


@pytest.fixture
def fichier_minimal(tmp_path):
    """Un référentiel réduit, écrit sur disque comme le serait celui d'un tiers."""
    def ecrire(donnees):
        chemin = tmp_path / "referentiel.json"
        chemin.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
        return str(chemin)

    return ecrire


@pytest.fixture
def donnees_minimales():
    return {
        "code": "organisme-tiers",
        "intitule": "Référentiel d'un autre organisme",
        "niveaux": ["Découvrir", "Pratiquer", "Maîtriser"],
        "modules": [
            {
                "code": "bases",
                "intitule": "Les bases",
                "competences": [
                    {"code": "lire", "intitule": "Lire du code"},
                    {"code": "ecrire", "intitule": "Écrire du code"},
                ],
            }
        ],
    }


@pytest.mark.django_db
def test_le_referentiel_livre_s_importe(tmp_path):
    """
    Le fichier livré avec le projet se charge, et la base porte son contenu.

    Compétence visée : C17 (épreuve E4)

    Le compte est relu EN BASE, non repris du fichier : compter ce qu'on a
    envoyé plutôt que ce qui est arrivé est le premier incident de ce projet.
    """
    sortie = _importer(FICHIER_LIVRE)

    referentiel = Referentiel.objects.get(code="eduai-2026")
    assert referentiel.modules.count() == 4
    assert Competence.objects.filter(module__referentiel=referentiel).count() == 21
    assert "en base : 4 modules, 21 compétences" in sortie


@pytest.mark.django_db
def test_l_import_est_rejouable_sans_dupliquer(tmp_path):
    """
    Relancer le même import ne duplique rien.

    Compétence visée : C4 (épreuve E1) — idempotence

    L'identité est le `code`, jamais la clé primaire : un référentiel se
    corrige et se recharge, comme le pipeline de données du bloc 1.
    """
    _importer(FICHIER_LIVRE)
    _importer(FICHIER_LIVRE)

    assert Referentiel.objects.filter(code="eduai-2026").count() == 1
    assert Module.objects.count() == 4
    assert Competence.objects.count() == 21


@pytest.mark.django_db
def test_une_competence_retiree_du_fichier_disparait_de_la_base(
        fichier_minimal, donnees_minimales):
    """
    Le fichier fait autorité : ce qu'il ne contient plus est retiré.

    Compétence visée : C17 (épreuve E4)

    Conserver les compétences retirées ferait cohabiter ce que l'organisme
    maintient et ce qu'il a abandonné, sans qu'on puisse les distinguer.
    """
    _importer(fichier_minimal(donnees_minimales))
    assert Competence.objects.count() == 2

    donnees_minimales["modules"][0]["competences"].pop()
    sortie = _importer(fichier_minimal(donnees_minimales))

    assert Competence.objects.count() == 1
    assert Competence.objects.get().code == "lire"
    assert "retirés car absents du fichier" in sortie


@pytest.mark.django_db
def test_le_controle_ne_touche_pas_la_base(fichier_minimal, donnees_minimales):
    """
    `--controler` valide le fichier sans rien écrire.

    Compétence visée : C17 (épreuve E4)
    """
    sortie = _importer(fichier_minimal(donnees_minimales), "--controler")

    assert "rien écrit" in sortie
    assert Referentiel.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("modification,fragment_attendu", [
    (lambda d: d.pop("code"), "code"),
    (lambda d: d.pop("modules"), "modules"),
    (lambda d: d.update(modules=[]), "liste non vide"),
    (lambda d: d.update(niveaux=["Un", "Deux"]), "exactement 3 niveaux"),
    (lambda d: d["modules"][0]["competences"].append(
        {"code": "lire", "intitule": "Doublon"}), "double"),
    (lambda d: d["modules"][0]["competences"].append({"code": "sans-intitule"}),
     "intitule"),
])
def test_un_fichier_invalide_est_refuse_sans_rien_ecrire(
        fichier_minimal, donnees_minimales, modification, fragment_attendu):
    """
    Toute validation échoue AVANT la première écriture.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Un import qui échoue au milieu laisse un référentiel amputé, dont personne
    ne sait qu'il l'est — le motif de l'incident 001.
    """
    modification(donnees_minimales)

    with pytest.raises(CommandError) as echec:
        _importer(fichier_minimal(donnees_minimales))

    assert fragment_attendu in str(echec.value)
    assert Referentiel.objects.count() == 0
    assert Competence.objects.count() == 0


@pytest.mark.django_db
def test_un_seul_referentiel_reste_actif(fichier_minimal, donnees_minimales):
    """
    Activer un référentiel désactive le précédent.

    Compétence visée : C17 (épreuve E4)

    L'unicité est garantie par une contrainte de base et non par une
    convention : une convention se contourne par l'administration ou un shell.
    """
    _importer(FICHIER_LIVRE, "--activer")
    _importer(fichier_minimal(donnees_minimales), "--activer")

    actifs = Referentiel.objects.filter(est_actif=True)
    assert actifs.count() == 1
    assert actifs.get().code == "organisme-tiers"


@pytest.mark.django_db
def test_un_import_sans_activer_n_affiche_rien(fichier_minimal, donnees_minimales):
    """
    Un référentiel importé sans `--activer` reste inactif, et la commande le dit.

    Compétence visée : C17 (épreuve E4)

    Un référentiel chargé mais inactif est exactement le genre de donnée
    présente et sans effet que ce projet documente. La commande l'annonce
    plutôt que de laisser croire au chargement.
    """
    sortie = _importer(fichier_minimal(donnees_minimales))

    assert Referentiel.objects.get().est_actif is False
    assert "inactif" in sortie
    assert "--activer" in sortie


@pytest.mark.django_db
def test_les_libelles_de_niveaux_viennent_du_fichier(
        fichier_minimal, donnees_minimales):
    """
    Un organisme renomme les trois paliers sans toucher au code.

    Compétence visée : C17 (épreuve E4), C13 (E3) — accessibilité

    Le libellé est ce qui permet de ne pas distinguer les niveaux par la seule
    couleur.
    """
    _importer(fichier_minimal(donnees_minimales))

    referentiel = Referentiel.objects.get()
    assert referentiel.niveaux == ["Découvrir", "Pratiquer", "Maîtriser"]
    assert referentiel.libelle_de_niveau(1) == "Découvrir"
    assert referentiel.libelle_de_niveau(3) == "Maîtriser"


@pytest.mark.django_db
def test_les_niveaux_par_defaut_servent_si_le_fichier_n_en_donne_pas(
        fichier_minimal, donnees_minimales):
    """
    Sans `niveaux` dans le fichier, l'échelle du projet s'applique.

    Compétence visée : C17 (épreuve E4)
    """
    donnees_minimales.pop("niveaux")
    _importer(fichier_minimal(donnees_minimales))

    assert Referentiel.objects.get().niveaux == ["Imiter", "Adapter", "Transposer"]


@pytest.mark.django_db
def test_aucun_libelle_de_competence_n_est_ecrit_en_dur_dans_le_code():
    """
    Les intitulés de compétences n'existent que dans les fichiers de données.

    Compétence visée : C17 (épreuve E4)

    C'est la condition de l'argument de généricité : un organisme qui charge
    son référentiel ne doit toucher ni gabarit, ni constante, ni migration. Ce
    test échoue si un intitulé du référentiel livré apparaît dans du code
    Python ou dans un gabarit.
    """
    import re
    from pathlib import Path

    donnees = json.loads(Path(FICHIER_LIVRE).read_text(encoding="utf-8"))
    intitules = [c["intitule"]
                 for m in donnees["modules"]
                 for c in m["competences"]]

    fichiers = [p for p in Path("apps").rglob("*.py")] \
        + [p for p in Path("apps").rglob("*.html")] \
        + [p for p in Path("templates").rglob("*.html")]

    fautifs = []
    for chemin in fichiers:
        if "donnees" in chemin.parts or "migrations" in chemin.parts:
            continue
        contenu = chemin.read_text(encoding="utf-8", errors="replace")
        for intitule in intitules:
            if re.search(re.escape(intitule), contenu):
                fautifs.append(f"{chemin} :: {intitule}")

    assert not fautifs, "intitulés de compétences écrits en dur : " + "; ".join(fautifs)
