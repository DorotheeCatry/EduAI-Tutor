"""
Contrôles du socle d'extraction.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C1 (épreuve E1) — automatisation de l'extraction
Compétence visée : C21 (épreuve E5) — non-régression sur incidents

Ces contrôles reprennent des vérifications faites à la main pendant le
développement. Elles étaient écrites en commandes jetables ; elles sont ici
rejouables, et deux d'entre elles gardent un incident réel de revenir.
"""

from __future__ import annotations

import json

from data_pipeline.extract.base_extractor import Enregistrement, ExtracteurBase


class ExtracteurFactice(ExtracteurBase):
    """
    Extracteur d'essai, dont on pilote la production.

    Compétence visée : C18 (épreuve E4)

    Choix : une sous-classe réelle plutôt qu'un objet simulé. Motivation : c'est
    le comportement du socle qu'on éprouve — statut, sauvegarde, bilan. Le
    simuler reviendrait à tester la simulation.
    """

    nom = "essai_factice"
    type_source = "api_rest"
    code_source = "s1"

    def __init__(self, repertoire, enregistrements=(), zero_valide=False):
        type(self).zero_est_valide = zero_valide
        super().__init__(repertoire)
        self._enregistrements = list(enregistrements)

    def initialiser(self) -> None:
        return None

    def extraire(self):
        yield from self._enregistrements


def _enregistrement(identifiant: str) -> Enregistrement:
    return Enregistrement(
        identifiant=identifiant,
        titre=f"Titre {identifiant}",
        contenu=f"Contenu de {identifiant}",
        source_nom="Source d'essai",
        source_type="api_rest",
    )


def test_une_extraction_productive_est_un_succes(repertoire_temporaire):
    """
    Une extraction qui produit des enregistrements rend « succes ».

    Compétence visée : C1 (épreuve E1)
    """
    extracteur = ExtracteurFactice(repertoire_temporaire, [_enregistrement("a")])
    bilan = extracteur.executer()

    assert bilan["statut"] == "succes"
    assert bilan["enregistrements"] == 1


def test_zero_enregistrement_est_un_echec_par_defaut(repertoire_temporaire):
    """
    Une source qui ne produit rien échoue, elle ne réussit pas.

    Compétence visée : C21 (épreuve E5) — non-régression, incident S1 du 26/08

    L'extracteur S1 avait rendu « succes, 0 enregistrement » : un filtre d'API
    inadapté ne ramenait rien, aucune étape n'échouait, et le programme
    concluait à la réussite. Il rendait compte de son intention, pas de son
    effet.
    """
    extracteur = ExtracteurFactice(repertoire_temporaire, [])
    bilan = extracteur.executer()

    assert bilan["statut"] == "echec", (
        "une extraction stérile ne doit jamais être rapportée comme un succès"
    )
    assert bilan["enregistrements"] == 0


def test_zero_est_valide_pour_les_sources_qui_le_declarent(repertoire_temporaire):
    """
    Une source déclarant le vide légitime rend « vide », ni succès ni échec.

    Compétence visée : C1 (épreuve E1)

    La base applicative peut légitimement ne contenir aucune production
    d'apprenant : c'est l'état normal d'une base neuve, pas une panne. Les deux
    cas ne doivent pas se confondre — d'où trois statuts et non deux.
    """
    extracteur = ExtracteurFactice(repertoire_temporaire, [], zero_valide=True)
    bilan = extracteur.executer()

    assert bilan["statut"] == "vide"
    assert bilan["enregistrements"] == 0


def test_une_extraction_sterile_n_ecrase_pas_la_sortie_precedente(repertoire_temporaire):
    """
    Une extraction qui ne produit rien préserve le fichier existant.

    Compétence visée : C21 (épreuve E5) — non-régression

    Le renommage atomique protège d'une écriture interrompue, pas d'une
    exécution qui se termine normalement sans rien produire. Sans cette
    protection, une panne d'API remplacerait un corpus valide par un fichier
    vide — et la perte serait invisible, le fichier existant toujours.
    """
    sortie = repertoire_temporaire / "essai_factice.jsonl"
    sortie.write_text('{"contenu":"precieux"}\n', encoding="utf-8")

    extracteur = ExtracteurFactice(repertoire_temporaire, [])
    extracteur.executer()

    assert "precieux" in sortie.read_text(encoding="utf-8"), (
        "la sortie précédente doit être conservée quand l'extraction ne produit rien"
    )


def test_le_vide_legitime_peut_vider_la_sortie(repertoire_temporaire):
    """
    La protection ne s'applique pas aux sources dont le vide est normal.

    Compétence visée : C1 (épreuve E1)

    Pour S4, une base dont toutes les productions ont dépassé la fenêtre de
    conservation doit bel et bien produire une sortie vide. Figer l'ancienne
    serait un autre mensonge.
    """
    sortie = repertoire_temporaire / "essai_factice.jsonl"
    sortie.write_text('{"contenu":"ancien"}\n', encoding="utf-8")

    extracteur = ExtracteurFactice(repertoire_temporaire, [], zero_valide=True)
    extracteur.executer()

    assert sortie.read_text(encoding="utf-8") == ""


def test_le_bilan_est_persiste_avec_le_code_de_source(repertoire_temporaire):
    """
    Le bilan est écrit sur disque, avec de quoi le rattacher à sa source.

    Compétence visée : C4 (épreuve E1) — alimentation de la table extraction

    Le chargeur ne peut pas reconstituer une campagne depuis le corpus : il en
    verrait le nombre de documents, mais ni la durée, ni les erreurs, ni les
    enregistrements écartés. Les inventer serait fabriquer une mesure.
    """
    extracteur = ExtracteurFactice(repertoire_temporaire, [_enregistrement("a")])
    extracteur.executer()

    bilan = json.loads(
        (repertoire_temporaire / "essai_factice.bilan.json").read_text(encoding="utf-8")
    )
    assert bilan["code_source"] == "s1"
    assert bilan["statut"] == "succes"
    assert bilan["enregistrements"] == 1


def test_les_separateurs_unicode_sont_neutralises(repertoire_temporaire):
    """
    Une ligne JSONL reste une ligne, quels que soient les caractères du contenu.

    Compétence visée : C1 (épreuve E1)

    U+2028, U+2029 et U+0085 sont des séparateurs de ligne Unicode que
    `json.dumps` laisse tels quels. `str.splitlines()` coupe dessus : un
    enregistrement deviendrait deux fragments illisibles. Le cas n'est pas
    théorique — l'extraction des PDF du corpus a produit 331 occurrences
    d'U+2028 pour 380 enregistrements.
    """
    contenu = "avant milieu finsuite"
    enregistrement = _enregistrement("u")
    enregistrement.contenu = contenu

    extracteur = ExtracteurFactice(repertoire_temporaire, [enregistrement])
    extracteur.executer()

    brut = (repertoire_temporaire / "essai_factice.jsonl").read_text(encoding="utf-8")
    assert len(brut.splitlines()) == 1, (
        "le fichier doit compter une ligne, quelle que soit la définition du lecteur"
    )
    assert json.loads(brut)["contenu"] == contenu, (
        "le contenu doit être restitué à l'identique après relecture"
    )
