"""
Seuils d'alerte du service IA, évalués en continu.

Compétence visée : C20 (épreuve E5) — surveillance et seuils d'alerte
Compétence visée : C21 (épreuve E5) — détection d'incident

Choix : l'alerte s'écrit dans le journal, et nulle part ailleurs. Motivation :
un service externe de notification est un composant de plus qui peut tomber, et
qui tombe souvent en même temps que ce qu'il surveille — réseau, quota,
authentification. Une ligne dans le fichier ne dépend que du disque, comme le
reste du monitorage.

Choix : une fenêtre glissante en mémoire plutôt qu'une relecture du fichier.
Motivation : relire le journal à chaque appel pour recalculer un taux ferait
croître le coût du monitorage avec la taille de ses propres traces. La fenêtre
en mémoire est bornée par le temps, pas par le volume.

Limite assumée : la fenêtre est propre au processus. Avec plusieurs processus
serveur, chacun surveille sa part du trafic. Le seuil se déclenche donc plus
tard qu'avec un compteur partagé — mais il se déclenche, et sans dépendre d'un
service tiers. L'analyse hors ligne (`analyse.py`) travaille, elle, sur le
fichier complet et voit tout le trafic.
"""

from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from .journal import journal

#: Durée de la fenêtre d'observation du taux d'erreur.
FENETRE_MINUTES = int(os.environ.get("MONITORAGE_FENETRE_MINUTES", "15"))

#: Nombre minimal d'appels dans la fenêtre avant d'évaluer un taux.
#:
#: Sans ce plancher, le premier appel raté de la journée produirait un taux
#: d'erreur de 100 pour cent et une alerte. Un taux calculé sur deux appels ne
#: dit rien.
APPELS_MINIMUM = int(os.environ.get("MONITORAGE_APPELS_MINIMUM", "5"))

#: Taux d'erreur au-delà duquel une alerte est levée, entre 0 et 1.
SEUIL_TAUX_ERREUR = float(os.environ.get("MONITORAGE_SEUIL_ERREUR", "0.20"))

#: Latence d'un appel au-delà de laquelle une alerte est levée, en secondes.
#:
#: **Ce seuil se règle par environnement, et les deux valeurs ne répondent pas
#: à la même question.** La valeur par défaut est celle du poste ; celle de
#: l'hébergeur est posée par la variable d'environnement.
#:
#: **Dix secondes en local, et c'est un seuil d'expérience.** Au-delà,
#: l'apprenant qui attend une correction dans l'éditeur considère le service
#: comme bloqué. La recherche y répond en 3 secondes : le seuil marque bien un
#: écart au fonctionnement normal.
#:
#: **Soixante-quinze secondes chez l'hébergeur, et c'est un seuil d'anomalie.**
#: Sans GPU et sur des cœurs mutualisés, la même recherche y demande 14 à 59
#: secondes, médiane 28 (réserve 7). Garder 10 s ferait lever une alerte à
#: chaque appel : une alerte permanente n'est plus une alerte, on cesse de la
#: lire — c'est le motif de l'incident 009, et il ne s'agit pas de le répéter
#: ici sous prétexte de confort.
#:
#: La valeur n'est donc pas choisie pour faire taire l'alarme, elle est
#: **dérivée de la dispersion mesurée**, par deux règles qui convergent :
#:
#:   moyenne + 2,5 écarts-types = 76,4 s      (moyenne 32,6 ; écart-type 17,5)
#:   maximum observé + 30 %     = 76,6 s      (maximum 58,9)
#:
#: Ce qui reste au-dessus de 75 s est ce qu'on veut précisément voir : le
#: premier appel après un déploiement (90 à 92 s, modèle à charger) et les
#: recherches concurrentes (102 et 128 s, sérialisées par
#: `OLLAMA_NUM_PARALLEL=1`). Ce sont des événements réels, pas le régime normal.
#:
#: **Ce que ce réglage ne dit pas** : que l'indicateur était faux. Il était
#: juste, et le contexte a changé — le service est passé d'une machine avec GPU
#: à un hébergeur qui n'en a pas. Un indicateur se règle sur ce qu'il observe ;
#: il ne se supprime pas parce qu'il dérange.
SEUIL_LATENCE_SECONDES = float(os.environ.get("MONITORAGE_SEUIL_LATENCE", "10"))

#: Délai minimal entre deux alertes de même nature.
#:
#: Sans lui, une panne du fournisseur produirait une alerte par appel et
#: noierait le journal sous des milliers de lignes identiques — rendant
#: illisible précisément ce qu'on cherche à observer.
SILENCE_MINUTES = int(os.environ.get("MONITORAGE_SILENCE_MINUTES", "10"))


class SurveillanceSeuils:
    """
    Fenêtre glissante des appels récents, et évaluation des seuils.

    Compétence visée : C20 (épreuve E5)
    """

    def __init__(self) -> None:
        #: (instant, en_erreur) des appels de la fenêtre.
        self._appels: deque[tuple[datetime, bool]] = deque()
        self._verrou = threading.Lock()
        #: Dernière émission par nature d'alerte, pour le silence.
        self._derniere_alerte: dict[str, datetime] = {}

    def enregistrer(self, en_erreur: bool, latence: float | None,
                    contexte: dict[str, Any]) -> None:
        """
        Enregistre un appel et évalue les seuils.

        Compétence visée : C20 (épreuve E5)

        Choix : l'évaluation a lieu à chaque appel, pas sur une minuterie.
        Motivation : une minuterie est un fil d'exécution de plus, qui doit
        être démarré, arrêté et surveillé. Évaluer en ligne coûte le parcours
        d'une file bornée et ne rajoute aucun composant.
        """
        maintenant = datetime.now(timezone.utc)
        limite = maintenant - timedelta(minutes=FENETRE_MINUTES)

        with self._verrou:
            self._appels.append((maintenant, en_erreur))
            while self._appels and self._appels[0][0] < limite:
                self._appels.popleft()
            total = len(self._appels)
            erreurs = sum(1 for _, faute in self._appels if faute)

        if latence is not None and latence > SEUIL_LATENCE_SECONDES:
            self._lever(
                nature="latence",
                # Format « g » et non « .0f » : un seuil abaissé pour un
                # essai — 0,001 s — s'afficherait sinon « 0 s », et le message
                # d'alerte deviendrait incompréhensible.
                message=(
                    f"Appel de {latence:.1f} s, au-delà du seuil de "
                    f"{SEUIL_LATENCE_SECONDES:g} s"
                ),
                mesures={"latence_secondes": round(latence, 3),
                         "seuil_secondes": SEUIL_LATENCE_SECONDES},
                contexte=contexte,
            )

        if total >= APPELS_MINIMUM:
            taux = erreurs / total
            if taux > SEUIL_TAUX_ERREUR:
                self._lever(
                    nature="taux_erreur",
                    message=(
                        f"{erreurs} erreur(s) sur {total} appel(s) en "
                        f"{FENETRE_MINUTES} min, soit un taux de "
                        f"{taux:.0%} au-delà du seuil de {SEUIL_TAUX_ERREUR:.0%}"
                    ),
                    mesures={
                        "appels_fenetre": total,
                        "erreurs_fenetre": erreurs,
                        "taux": round(taux, 3),
                        "seuil": SEUIL_TAUX_ERREUR,
                        "fenetre_minutes": FENETRE_MINUTES,
                    },
                    contexte=contexte,
                )

    def _lever(self, nature: str, message: str, mesures: dict[str, Any],
               contexte: dict[str, Any]) -> None:
        """
        Écrit une alerte dans le journal, en respectant le délai de silence.

        Compétence visée : C20 (épreuve E5)

        Choix : le silence est appliqué par nature d'alerte et non globalement.
        Motivation : une panne de latence ne doit pas masquer une montée du taux
        d'erreur pendant dix minutes. Ce sont deux symptômes différents, souvent
        de deux causes différentes.
        """
        maintenant = datetime.now(timezone.utc)
        precedente = self._derniere_alerte.get(nature)
        if precedente and maintenant - precedente < timedelta(minutes=SILENCE_MINUTES):
            return
        self._derniere_alerte[nature] = maintenant

        journal.ecrire({
            "type": "alerte",
            "nature": nature,
            "message": message,
            "mesures": mesures,
            **contexte,
        })
        try:
            from .metriques import alertes_levees

            alertes_levees.labels(nature=nature).inc()
        except Exception:  # noqa: BLE001 — l'alerte prime sur sa métrique
            pass


#: Surveillance partagée par les sondes du processus.
surveillance = SurveillanceSeuils()
