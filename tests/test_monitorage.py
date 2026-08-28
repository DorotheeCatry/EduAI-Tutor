"""
Contrôles du monitorage du service IA.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C20 (épreuve E5) — monitorage
Compétence visée : C21 (épreuve E5) — non-régression sur incidents

Le test le plus important de ce fichier est
`test_la_sonde_est_visible_depuis_un_autre_fil`. Il garde l'incident 003 de
revenir : la sonde s'annonçait branchée et ne traçait rien depuis un serveur,
pendant vingt-deux heures, parce qu'elle avait été posée par `ContextVar.set()`
dans le contexte du démarrage.

Ce défaut avait échappé à trois vérifications manuelles — toutes menées depuis
des scripts, où le contexte est celui de l'import. **On avait vérifié que la
sonde fonctionne, jamais qu'elle fonctionne là où le service tourne.** C'est
exactement la condition que ce test reproduit.
"""

from __future__ import annotations

import asyncio
import json
import threading

import pytest

from apps.monitoring.alertes import SurveillanceSeuils
from apps.monitoring.journal import JournalMonitorage, tronquer_trace


# --- Le journal mesure ce qu'il écrit, pas ce qu'il annonce ---------------

def test_le_journal_ecrit_une_ligne_par_evenement(repertoire_temporaire):
    """
    Chaque événement produit une ligne analysable.

    Compétence visée : C20 (épreuve E5)
    """
    journal = JournalMonitorage(repertoire_temporaire)
    for numero in range(5):
        assert journal.ecrire({"type": "essai", "numero": numero}) is True

    verification = journal.verifier()
    assert verification["evenements_emis"] == 5
    assert verification["lignes_valides_sur_disque"] == 5
    assert verification["lignes_illisibles"] == 0
    assert verification["ecart_emis_moins_ecrits"] == 0


def test_la_verification_relit_le_fichier_et_non_ses_compteurs(repertoire_temporaire):
    """
    `verifier` constate ce qui est sur le disque, pas ce que le journal croit.

    Compétence visée : C21 (épreuve E5) — non-régression

    C'est la règle tirée des incidents du projet : un composant doit rapporter
    son effet, pas son intention. Ici, on écrit une ligne directement dans le
    fichier, sans passer par le journal : il ne l'a pas émise, et pourtant elle
    existe. La vérification doit la voir.
    """
    journal = JournalMonitorage(repertoire_temporaire)
    journal.ecrire({"type": "emis_par_le_journal"})

    with journal.fichier_du_jour().open("a", encoding="utf-8") as flux:
        flux.write(json.dumps({"type": "ecrit_par_un_tiers"}) + "\n")

    verification = journal.verifier()
    assert verification["evenements_emis"] == 1
    assert verification["lignes_valides_sur_disque"] == 2, (
        "la vérification doit compter les lignes du fichier, pas les appels reçus"
    )


def test_une_ligne_illisible_est_comptee_a_part(repertoire_temporaire):
    """
    Une ligne tronquée se distingue d'une ligne absente.

    Compétence visée : C20 (épreuve E5)

    Les deux ne signalent pas la même panne : la première une écriture
    entrelacée ou interrompue, la seconde une écriture qui n'a pas eu lieu.
    """
    journal = JournalMonitorage(repertoire_temporaire)
    journal.ecrire({"type": "valide"})
    with journal.fichier_du_jour().open("a", encoding="utf-8") as flux:
        flux.write('{"type": "tron\n')

    verification = journal.verifier()
    assert verification["lignes_valides_sur_disque"] == 1
    assert verification["lignes_illisibles"] == 1


def test_une_ecriture_impossible_ne_leve_pas_mais_se_compte(repertoire_temporaire):
    """
    Le monitorage n'a pas le droit de faire tomber ce qu'il observe.

    Compétence visée : C20 (épreuve E5)

    Mais l'échec est compté : avaler une erreur sans la compter reproduirait le
    motif que ce paquet existe pour détecter.
    """
    # Un fichier là où le journal attend un répertoire : l'écriture échouera.
    obstacle = repertoire_temporaire / "obstacle"
    obstacle.write_text("", encoding="utf-8")

    journal = JournalMonitorage(obstacle / "sous-repertoire")
    assert journal.ecrire({"type": "essai"}) is False
    assert journal.echecs_ecriture == 1


def test_la_trace_est_tronquee_par_le_debut(repertoire_temporaire):
    """
    Une trace trop longue conserve sa fin, où se trouve la cause.

    Compétence visée : C21 (épreuve E5)
    """
    trace = "\n".join(f"  ligne {n}" for n in range(2000)) + "\nErreurFinale: la cause"
    tronquee = tronquer_trace(trace)

    assert "ErreurFinale: la cause" in tronquee, (
        "la fin d'une trace Python porte l'exception : c'est elle qu'il faut garder"
    )
    assert "tronquée" in tronquee


# --- Les seuils d'alerte -------------------------------------------------

def test_aucune_alerte_sous_le_plancher_d_appels(repertoire_temporaire, monkeypatch):
    """
    Un taux calculé sur trop peu d'appels ne dit rien.

    Compétence visée : C20 (épreuve E5)

    Sans plancher, le premier appel raté de la journée produirait un taux
    d'erreur de cent pour cent et une alerte.
    """
    import apps.monitoring.alertes as module

    journal = JournalMonitorage(repertoire_temporaire)
    monkeypatch.setattr(module, "journal", journal)
    monkeypatch.setattr(module, "APPELS_MINIMUM", 5)
    monkeypatch.setattr(module, "SEUIL_TAUX_ERREUR", 0.2)

    surveillance = SurveillanceSeuils()
    for _ in range(4):
        surveillance.enregistrer(en_erreur=True, latence=None, contexte={})

    assert _alertes(journal) == []


def test_l_alerte_de_taux_se_declenche_au_plancher(repertoire_temporaire, monkeypatch):
    """
    Le plancher atteint, un taux au-dessus du seuil lève une alerte.

    Compétence visée : C20 (épreuve E5)
    """
    import apps.monitoring.alertes as module

    journal = JournalMonitorage(repertoire_temporaire)
    monkeypatch.setattr(module, "journal", journal)
    monkeypatch.setattr(module, "APPELS_MINIMUM", 3)
    monkeypatch.setattr(module, "SEUIL_TAUX_ERREUR", 0.2)

    surveillance = SurveillanceSeuils()
    for _ in range(3):
        surveillance.enregistrer(en_erreur=True, latence=None, contexte={})

    natures = [alerte["nature"] for alerte in _alertes(journal)]
    assert "taux_erreur" in natures


def test_le_silence_absorbe_les_alertes_redondantes(repertoire_temporaire, monkeypatch):
    """
    Une panne durable ne noie pas le journal sous des lignes identiques.

    Compétence visée : C20 (épreuve E5)

    Sans délai de silence, une indisponibilité du fournisseur produirait une
    alerte par appel — rendant illisible précisément ce qu'on cherche à
    observer.
    """
    import apps.monitoring.alertes as module

    journal = JournalMonitorage(repertoire_temporaire)
    monkeypatch.setattr(module, "journal", journal)
    monkeypatch.setattr(module, "SEUIL_LATENCE_SECONDES", 0.001)
    monkeypatch.setattr(module, "SILENCE_MINUTES", 10)

    surveillance = SurveillanceSeuils()
    for _ in range(11):
        surveillance.enregistrer(en_erreur=False, latence=5.0, contexte={})

    latences = [a for a in _alertes(journal) if a["nature"] == "latence"]
    assert len(latences) == 1, (
        f"onze appels lents doivent produire une seule alerte, pas {len(latences)}"
    )


def _alertes(journal: JournalMonitorage) -> list[dict]:
    chemin = journal.fichier_du_jour()
    if not chemin.is_file():
        return []
    return [
        evenement
        for evenement in (json.loads(l) for l in chemin.open(encoding="utf-8") if l.strip())
        if evenement.get("type") == "alerte"
    ]


# --- Non-régression de l'incident 003 ------------------------------------

def test_la_sonde_est_visible_depuis_un_autre_fil():
    """
    La sonde doit être vue depuis un fil qui n'a pas participé au démarrage.

    Compétence visée : C21 (épreuve E5) — non-régression, incident 003

    Sous WSGI, chaque requête est traitée dans un fil qui démarre avec un
    contexte vide. Une sonde posée par `ContextVar.set()` au démarrage y est
    invisible : LangChain trouve None et n'attache aucun rappel. Le serveur
    Django n'a rien tracé pendant vingt-deux heures en annonçant « sonde
    branchée ».
    """
    from apps.monitoring.sondes import _sonde_active, installer, sonde

    installer()
    vue = {}

    def dans_un_fil():
        vue["sonde"] = _sonde_active.get()

    fil = threading.Thread(target=dans_un_fil)
    fil.start()
    fil.join()

    assert vue["sonde"] is sonde, (
        "la sonde doit être la valeur PAR DÉFAUT de la variable de contexte, "
        "et non une valeur posée au démarrage : un fil neuf ne l'hériterait pas"
    )


def test_la_sonde_est_visible_depuis_une_tache_asyncio():
    """
    Même exigence sous FastAPI, où chaque requête est une tâche distincte.

    Compétence visée : C21 (épreuve E5) — non-régression, incident 003
    """
    from apps.monitoring.sondes import _sonde_active, installer, sonde

    installer()

    async def dans_une_tache():
        return await asyncio.create_task(_lire_la_sonde())

    async def _lire_la_sonde():
        return _sonde_active.get()

    assert asyncio.run(dans_une_tache()) is sonde


@pytest.mark.parametrize("valeur,attendu", [
    (1217844432, "2008-08-04T10:07:12+00:00"),
    ("2015-01-06T05:34:09.967000", "2015-01-06T05:34:09.967000+00:00"),
    ("2026-08-27T12:34:27Z", "2026-08-27T12:34:27+00:00"),
])
def test_les_horodatages_sont_ramenes_a_iso_utc(valeur, attendu):
    """
    Quatre formes de date, une seule sortie.

    Compétence visée : C3 (épreuve E1) — homogénéisation
    """
    from data_pipeline.transform.normalisation_dates import normaliser_horodatage

    assert normaliser_horodatage(valeur) == attendu
