"""
Contrôles de l'outillage du benchmark de modèles.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C7 (épreuve E2) — comparaison de services d'IA

Ce fichier n'éprouve pas les modèles — ils changent, et une suite de tests qui
en dépend échouerait pour de mauvaises raisons. Il éprouve les décisions de
méthode qui rendent les mesures valides : écarter une latence contaminée par un
quota, ne pas mélanger les appels en erreur aux appels aboutis, compter la
troncature avec le plafond réellement appliqué.

Chacune de ces trois règles a été écrite en réaction à une observation de la
campagne du 28 août. Sans test, la prochaine campagne les perdrait en silence.
"""

from __future__ import annotations

import pytest

from benchmark.analyser import statistiques, synthese_par_modele
from benchmark.executer import est_un_refus_de_quota


class RefusHttp(Exception):
    """Exception minimale portant un code de statut, comme celles des clients."""

    def __init__(self, code: int) -> None:
        super().__init__(f"refus {code}")
        self.status_code = code


# --- Reconnaissance d'un refus pour quota ---------------------------------

def test_un_refus_429_est_reconnu_par_son_code():
    """
    Le code de statut prime sur le texte du message.

    Compétence visée : C7 (épreuve E2)

    Le texte change d'un fournisseur et d'une version à l'autre ; le code, non.
    """
    assert est_un_refus_de_quota(RefusHttp(429)) is True


def test_une_erreur_ordinaire_n_est_pas_prise_pour_un_quota():
    """
    Un refus 400 ne doit pas déclencher une attente d'une minute.

    Compétence visée : C7 (épreuve E2)

    Confondre les deux ferait rejouer trois fois un appel voué à échouer, en
    patientant plus de trois minutes pour rien.
    """
    assert est_un_refus_de_quota(RefusHttp(400)) is False
    assert est_un_refus_de_quota(ValueError("modèle inconnu")) is False


def test_le_message_sert_de_recours_quand_aucun_code_n_est_expose():
    """
    Certains clients n'exposent pas de code : le message est alors la seule piste.

    Compétence visée : C7 (épreuve E2)
    """
    assert est_un_refus_de_quota(RuntimeError("Rate limit reached for model")) is True


# --- Les statistiques de latence ------------------------------------------

def test_le_neuvieme_decile_est_une_valeur_observee():
    """
    Le 9ᵉ décile est pris sur la série triée, jamais interpolé.

    Compétence visée : C7 (épreuve E2)

    Sur trente points, une interpolation produirait un chiffre qui ne
    correspond à aucun appel réellement passé.
    """
    valeurs = [float(n) for n in range(1, 11)]
    resultat = statistiques(valeurs)
    assert resultat["p90"] in valeurs
    assert resultat["mediane"] == 5.5
    assert resultat["minimum"] == 1.0
    assert resultat["maximum"] == 10.0


def test_une_serie_vide_ne_leve_pas():
    """
    Un modèle non mesuré ne doit pas faire tomber l'analyse des autres.

    Compétence visée : C7 (épreuve E2)
    """
    assert statistiques([])["n"] == 0


# --- Ce qui entre dans les statistiques, et ce qui n'y entre pas ----------

def test_un_appel_en_erreur_n_entre_pas_dans_la_latence():
    """
    La durée d'un refus n'est pas la latence d'un modèle.

    Compétence visée : C7 (épreuve E2)

    Sans cette exclusion, le modèle qui échoue le plus vite afficherait la
    meilleure latence médiane — un classement exactement inversé.
    """
    mesures = [
        {"modele": "openai/gpt-oss-20b", "issue": "succes",
         "trace_sonde": "presente", "latence_secondes": 2.0, "agent": "coach"},
        {"modele": "openai/gpt-oss-20b", "issue": "erreur",
         "trace_sonde": "presente", "latence_secondes": 0.01, "agent": "coach"},
    ]
    synthese = synthese_par_modele(mesures)["openai/gpt-oss-20b"]

    assert synthese["latence"]["n"] == 1
    assert synthese["latence"]["mediane"] == 2.0
    assert synthese["erreurs"] == 1


def test_un_appel_sans_trace_de_sonde_est_compte_a_part():
    """
    Un appel que la sonde n'a pas tracé est signalé, pas ignoré.

    Compétence visée : C21 (épreuve E5) — non-régression, incident 003

    C'est le contrôle hérité de la sonde qui s'annonçait branchée sans rien
    écrire. Un appel sans trace n'a pas de mesure de jetons : le compter comme
    les autres donnerait une moyenne calculée sur moins d'appels qu'annoncé.
    """
    mesures = [
        {"modele": "openai/gpt-oss-20b", "issue": "succes",
         "trace_sonde": "absente", "latence_secondes": None, "agent": "coach"},
    ]
    synthese = synthese_par_modele(mesures)["openai/gpt-oss-20b"]

    assert synthese["traces_absentes"] == 1
    assert synthese["latence"]["n"] == 0, (
        "un appel sans trace ne fournit aucune latence mesurée par la sonde"
    )


def test_les_tentatives_ecartees_sont_comptees():
    """
    Le nombre d'appels rejoués après un quota est conservé.

    Compétence visée : C7 (épreuve E2)

    Leur latence est jetée — elle contiendrait une attente de quota — mais le
    fait qu'il a fallu rejouer reste une information sur la disponibilité du
    service, et il est consigné plutôt que perdu.
    """
    mesures = [
        {"modele": "openai/gpt-oss-20b", "issue": "succes", "tentatives": 3,
         "trace_sonde": "presente", "latence_secondes": 1.0, "agent": "coach"},
    ]
    synthese = synthese_par_modele(mesures)["openai/gpt-oss-20b"]
    assert synthese["tentatives_ecartees"] == 2


@pytest.mark.parametrize("nom", ["qwen3:4b"])
def test_un_modele_absent_des_mesures_est_declare_non_mesure(nom):
    """
    L'absence de mesure est un résultat, pas une case vide.

    Compétence visée : C7 (épreuve E2)

    Une case vide se lit comme un oubli ; une mention « non mesuré » se lit
    comme un fait, et le rapport doit porter le second.
    """
    assert synthese_par_modele([])[nom]["non_mesure"] is True
