"""
Journal de monitorage : écriture JSON Lines, hors de toute base de données.

Compétence visée : C20 (épreuve E5) — monitorage du service en production
Compétence visée : C21 (épreuve E5) — détection d'incident

Choix : un fichier JSON Lines et non une table PostgreSQL. Motivation : le
monitorage doit survivre à la panne qu'il est censé observer. Écrire les traces
dans la base, c'est perdre la trace de l'incident précisément quand la base
tombe — et c'est ce mode de défaillance qu'on cherche à documenter. Un fichier
ouvert en ajout ne dépend que du système de fichiers.

Choix : une ligne JSON par événement, jamais un tableau JSON global.
Motivation : un tableau doit être refermé pour être valide. Un processus tué
laisserait un fichier inexploitable, c'est-à-dire perdrait toutes les traces
antérieures à l'incident — encore une fois, exactement celles qui comptent.
JSON Lines se lit ligne à ligne, et une dernière ligne tronquée ne coûte que
cette ligne.

Choix : ouverture en mode ajout à chaque écriture, avec `O_APPEND`.
Motivation : le noyau garantit alors l'atomicité du positionnement pour des
écritures inférieures à la taille d'un tampon de tuyau. Deux processus qui
écrivent simultanément n'entrelacent pas leurs lignes.

CE QUE CE MODULE MESURE
Le projet a connu quatre incidents en deux jours partageant le même motif : un
rapport de succès qui ne correspondait à rien. Une extraction « réussie » à
zéro enregistrement, un chargement annonçant 6 836 documents sur une base vide,
un rapport de mesure écrasé par une exécution partielle, un décompte d'API qui
dépassait le corpus réel.

Ce module en tire une règle : **il compte ce qui a été écrit, pas ce qu'il a
tenté d'écrire.** `verifier()` relit le fichier et compare les lignes réellement
analysables au nombre d'événements émis. L'écart est le seul chiffre digne de
confiance.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Répertoire des journaux de monitorage. Hors du dépôt : ces fichiers
#: grossissent, et ils contiennent l'exploitation, pas le code.
REPERTOIRE_JOURNAL = Path(
    os.environ.get("MONITORAGE_REPERTOIRE", "data_pipeline/data/monitorage")
)

#: Nombre maximal d'octets d'une trace d'exception conservée. Une trace
#: complète peut peser plusieurs kilooctets ; au-delà de cette borne, le
#: contexte utile est passé et le journal devient illisible.
TAILLE_TRACE_MAX = 4000

#: Séparateurs de ligne Unicode que `json.dumps` laisse passer et qui coupent
#: une ligne JSONL en deux pour certains lecteurs. Même neutralisation que dans
#: le socle d'extraction, pour la même raison.
SEPARATEURS_UNICODE = (" ", " ", "")


class JournalMonitorage:
    """
    Écrivain de journal, sûr entre fils d'exécution et jamais bloquant.

    Compétence visée : C20 (épreuve E5)

    Choix : une défaillance d'écriture du journal ne remonte jamais à
    l'appelant. Motivation : le monitorage observe le service, il ne doit pas
    pouvoir le faire tomber. Un disque plein rendrait autrement l'application
    entière indisponible — la sonde deviendrait la panne.

    Choix : mais elle est **comptée**. Motivation : avaler une erreur sans la
    compter reproduirait le motif que ce module existe pour détecter. Le
    compteur `echecs_ecriture` est exposé, et `verifier()` le confronte au
    fichier réel.
    """

    def __init__(self, repertoire: Path | None = None) -> None:
        self.repertoire = Path(repertoire or REPERTOIRE_JOURNAL)
        self._verrou = threading.Lock()

        #: Événements dont l'écriture a été demandée.
        self.evenements_emis = 0
        #: Événements dont l'écriture a échoué.
        self.echecs_ecriture = 0

    def fichier_du_jour(self, moment: datetime | None = None) -> Path:
        """
        Renvoie le fichier de journal correspondant à une date.

        Compétence visée : C20 (épreuve E5)

        Choix : un fichier par jour, nommé par la date UTC. Motivation : une
        rotation par taille couperait au milieu d'une journée et rendrait toute
        comparaison jour à jour laborieuse. La date dans le nom permet de
        retrouver une période sans lire le contenu, et de purger par ancienneté
        sans analyser quoi que ce soit.
        """
        moment = moment or datetime.now(timezone.utc)
        return self.repertoire / f"monitorage-{moment:%Y-%m-%d}.jsonl"

    def ecrire(self, evenement: dict[str, Any]) -> bool:
        """
        Ajoute un événement au journal du jour.

        Compétence visée : C20 (épreuve E5)

        Returns:
            True si la ligne a été écrite, False si l'écriture a échoué. Le
            retour est ignoré par les sondes — il sert aux tests et au
            diagnostic.
        """
        self.evenements_emis += 1
        moment = datetime.now(timezone.utc)
        evenement = {"horodatage": moment.isoformat(), **evenement}

        try:
            ligne = json.dumps(evenement, ensure_ascii=False, default=str)
            for separateur in SEPARATEURS_UNICODE:
                ligne = ligne.replace(separateur, f"\\u{ord(separateur):04x}")

            chemin = self.fichier_du_jour(moment)
            with self._verrou:
                chemin.parent.mkdir(parents=True, exist_ok=True)
                # O_APPEND : le noyau positionne et écrit en une opération, ce
                # qui empêche deux processus d'entrelacer leurs lignes.
                descripteur = os.open(
                    chemin, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644,
                )
                try:
                    os.write(descripteur, (ligne + "\n").encode("utf-8"))
                finally:
                    os.close(descripteur)
            return True

        except Exception as exception:  # noqa: BLE001 — la sonde ne casse rien
            self.echecs_ecriture += 1
            # Dernier recours : la sortie d'erreur. Elle est reprise par les
            # journaux du serveur, et ne dépend d'aucun de nos composants.
            print(
                f"[monitorage] écriture impossible ({type(exception).__name__}"
                f" : {exception}) — {self.echecs_ecriture} échec(s) cumulé(s)",
                file=sys.stderr,
            )
            return False

    def verifier(self, moment: datetime | None = None) -> dict[str, Any]:
        """
        Relit le journal et compare l'écrit au déclaré.

        Compétence visée : C20 (épreuve E5)
        Compétence visée : C21 (épreuve E5)

        C'est la méthode qui applique la leçon des quatre incidents du projet :
        elle ne rapporte pas ce que le journal croit avoir écrit, elle rouvre le
        fichier et compte ce qui s'y trouve réellement.

        Une ligne illisible est comptée séparément d'une ligne absente : la
        première signale une écriture entrelacée ou tronquée, la seconde une
        écriture qui n'a pas eu lieu. Ce ne sont pas les mêmes pannes.
        """
        chemin = self.fichier_du_jour(moment)
        lignes_valides = 0
        lignes_illisibles = 0
        octets = 0

        if chemin.is_file():
            octets = chemin.stat().st_size
            with chemin.open(encoding="utf-8") as flux:
                for ligne in flux:
                    if not ligne.strip():
                        continue
                    try:
                        json.loads(ligne)
                        lignes_valides += 1
                    except json.JSONDecodeError:
                        lignes_illisibles += 1

        return {
            "fichier": str(chemin),
            "existe": chemin.is_file(),
            "octets": octets,
            "evenements_emis": self.evenements_emis,
            "echecs_ecriture_signales": self.echecs_ecriture,
            "lignes_valides_sur_disque": lignes_valides,
            "lignes_illisibles": lignes_illisibles,
            # L'écart n'est significatif que dans un processus qui a écrit tout
            # le fichier. Un fichier hérité d'une exécution précédente contient
            # légitimement plus de lignes que ce processus n'en a émis.
            "ecart_emis_moins_ecrits": self.evenements_emis - lignes_valides,
        }


def tronquer_trace(trace: str | None) -> str | None:
    """
    Borne la taille d'une trace d'exception conservée au journal.

    Compétence visée : C20 (épreuve E5)

    Choix : conserver la fin et couper le début. Motivation : dans une trace
    Python, l'exception et le cadre où elle survient sont en dernier. Couper la
    fin garderait la pile d'appels et perdrait la cause — c'est-à-dire le seul
    élément pour lequel on conserve une trace.
    """
    if not trace:
        return None
    if len(trace) <= TAILLE_TRACE_MAX:
        return trace
    conserve = trace[-TAILLE_TRACE_MAX:]
    return f"[…trace tronquée, {len(trace) - TAILLE_TRACE_MAX} caractères omis…]\n{conserve}"


#: Journal partagé par les sondes du processus.
journal = JournalMonitorage()
