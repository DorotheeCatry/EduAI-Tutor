"""
Métriques Prometheus du service IA.

Compétence visée : C20 (épreuve E5) — monitorage du service en production

Deux sorties, deux usages, et c'est délibéré :

    Prometheus  agrège — taux, quantiles, tendances sur des semaines
    JSON Lines  détaille — la trace exacte d'un appel précis, pour un diagnostic

Prometheus ne conserve pas le détail d'un appel : il ne sait pas dire quelle
requête a échoué à 14 h 32, avec quel message et quelle trace. Le fichier ne
sait pas dire, lui, quel est le quantile de latence sur sept jours sans tout
relire. Les deux sont nécessaires, aucun ne remplace l'autre.

Le fichier de traces ne dépend d'aucun service tiers. Si Prometheus tombe, le
détail continue de s'écrire — et c'est précisément la panne qu'on veut pouvoir
observer.

CE QUE CES MÉTRIQUES COMPTENT
Les cinq incidents du projet partagent le même motif : un rapport de succès qui
ne correspond à rien. Deux compteurs en tirent la conséquence directe :

    eduai_journal_evenements_emis_total    ce qu'on a voulu écrire
    eduai_journal_lignes_ecrites_total     ce qui a réellement été écrit

L'écart entre les deux est un signal de panne, et il est visible dans le
tableau de bord. Un monitorage qui ne compterait que les événements émis
annoncerait un journal complet sur un disque plein.

LIMITE CONNUE : UN REGISTRE PAR PROCESSUS
Les compteurs vivent en mémoire du processus qui les incrémente. Avec le
serveur de développement, qui est mono-processus, `/metrics` décrit donc la
totalité du trafic. Avec plusieurs travailleurs — gunicorn, uvicorn —, le
collecteur interrogerait un travailleur au hasard et n'en verrait qu'une
fraction.

La réponse existe et est prévue : `prometheus_client` sait agréger entre
processus via un répertoire partagé, déclaré par `PROMETHEUS_MULTIPROC_DIR`.
Elle n'est pas mise en place ici parce que le service ne tourne pas encore
derrière plusieurs travailleurs, et qu'un mécanisme d'agrégation non éprouvé
donnerait des chiffres faux plutôt qu'absents.

Les traces JSON Lines, elles, n'ont pas cette limite : tous les processus
écrivent dans le même fichier en `O_APPEND`, et `analyse.py` les lit toutes.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

#: Registre propre au projet plutôt que le registre global.
#:
#: Choix : un registre dédié. Motivation : le registre global de
#: `prometheus_client` collecte aussi les métriques de la machine virtuelle
#: Python et du processus. Elles ne sont pas inutiles, mais elles noient les
#: nôtres et rendent le point de terminaison illisible à l'œil. Un registre
#: dédié garde `/metrics` lisible sans outil.
REGISTRE = CollectorRegistry()

#: Bornes de l'histogramme de latence des appels au fournisseur, en secondes.
#:
#: Choix : des bornes resserrées entre 0,5 et 10 s, et deux bornes au-delà.
#: Motivation : un appel de modèle sous 500 ms n'existe pas en pratique, et
#: au-delà de 30 s l'appel a de toute façon échoué du point de vue de
#: l'apprenant. La précision doit être là où la décision se joue — autour du
#: seuil d'alerte de 10 s.
BORNES_LATENCE_LLM = (0.5, 1, 2, 3, 5, 8, 10, 15, 30, 60)

#: Bornes pour les recherches dans le vector store.
#:
#: Une recherche vectorielle se compte en dizaines de millisecondes quand tout
#: va bien ; les bornes commencent donc bien plus bas que pour un appel LLM.
BORNES_LATENCE_RAG = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)

#: Bornes du nombre de fragments rendus par une recherche.
#:
#: La borne à 0 est la plus importante du lot : elle isole les recherches qui
#: aboutissent sans rien rendre. C'est un succès vide, exactement le genre de
#: résultat que ce projet a appris à ne pas croire sur parole.
BORNES_FRAGMENTS = (0, 1, 2, 3, 5, 8, 10, 20)


# --- Appels au fournisseur de modèles ---

appels_llm = Counter(
    "eduai_appels_llm_total",
    "Appels au fournisseur de modèles, par agent, modèle et issue.",
    ["agent", "modele", "fournisseur", "issue"],
    registry=REGISTRE,
)

erreurs_llm = Counter(
    "eduai_erreurs_llm_total",
    "Erreurs d'appel au fournisseur, par code de retour et classe d'exception.",
    # Le code de retour distingue un quota atteint (429) d'un modèle retiré du
    # catalogue (404) et d'une indisponibilité (503). Trois pannes, trois
    # réactions — le projet a déjà connu la deuxième.
    ["agent", "modele", "code_retour", "classe"],
    registry=REGISTRE,
)

latence_llm = Histogram(
    "eduai_latence_llm_secondes",
    "Latence des appels au fournisseur de modèles.",
    ["agent", "modele"],
    buckets=BORNES_LATENCE_LLM,
    registry=REGISTRE,
)

jetons = Counter(
    "eduai_jetons_total",
    "Jetons facturés par le fournisseur, par sens.",
    # « sens » vaut entree ou sortie : les deux ne coûtent pas le même prix, et
    # les agréger masquerait qu'un prompt trop long coûte plus qu'une réponse
    # longue.
    ["agent", "modele", "sens"],
    registry=REGISTRE,
)

cout_estime = Counter(
    "eduai_cout_estime_total",
    "Coût cumulé estimé des appels, dans la devise du tarif.",
    # « tarif_verifie » vaut « oui » ou « non ». Un coût reposant sur un tarif
    # non confronté à la grille du fournisseur ne doit pas se confondre avec un
    # coût établi : le tableau de bord affiche la distinction.
    ["modele", "devise", "tarif_verifie"],
    registry=REGISTRE,
)


# --- Recherches dans le vector store ---

recherches_rag = Counter(
    "eduai_recherches_rag_total",
    "Recherches dans le vector store, par agent et issue.",
    ["agent", "issue"],
    registry=REGISTRE,
)

latence_rag = Histogram(
    "eduai_latence_rag_secondes",
    "Latence des recherches dans le vector store.",
    ["agent"],
    buckets=BORNES_LATENCE_RAG,
    registry=REGISTRE,
)

fragments_rendus = Histogram(
    "eduai_fragments_rendus",
    "Nombre de fragments RENDUS par une recherche — non le nombre demandé.",
    ["agent"],
    buckets=BORNES_FRAGMENTS,
    registry=REGISTRE,
)


# --- Santé du monitorage lui-même ---

evenements_emis = Counter(
    "eduai_journal_evenements_emis_total",
    "Événements dont l'écriture au journal a été DEMANDÉE.",
    registry=REGISTRE,
)

lignes_ecrites = Counter(
    "eduai_journal_lignes_ecrites_total",
    "Lignes RÉELLEMENT écrites au journal — l'écart avec les événements émis "
    "signale un disque plein, des droits manquants ou un chemin invalide.",
    registry=REGISTRE,
)

echecs_ecriture = Counter(
    "eduai_journal_echecs_ecriture_total",
    "Écritures au journal ayant échoué.",
    registry=REGISTRE,
)

echecs_sonde = Counter(
    "eduai_sonde_echecs_total",
    "Exceptions rattrapées dans la sonde elle-même. Une sonde qui échoue en "
    "silence ne se voit pas ; celle-ci se compte.",
    ["methode"],
    registry=REGISTRE,
)

alertes_levees = Counter(
    "eduai_alertes_total",
    "Alertes de seuil écrites au journal, par nature.",
    ["nature"],
    registry=REGISTRE,
)

taille_journal = Gauge(
    "eduai_journal_octets",
    "Taille du journal du jour, en octets. Mesuré sur le disque à chaque "
    "collecte, et non déduit du nombre d'événements.",
    registry=REGISTRE,
)


def rafraichir_taille_journal() -> None:
    """
    Relit la taille du fichier de journal sur le disque.

    Compétence visée : C20 (épreuve E5)

    Choix : un `stat` du fichier plutôt qu'une estimation déduite du nombre
    d'événements multiplié par une taille moyenne. Motivation : c'est la seule
    mesure qui constate un effet. Un journal dont le nombre d'événements
    augmente pendant que la taille du fichier stagne est un journal qui n'écrit
    plus — et c'est invisible pour qui ne regarde que les compteurs.

    Choix : `stat` et non un comptage de lignes. Motivation : compter les
    lignes exige de lire tout le fichier, à chaque collecte, toutes les quinze
    secondes. La taille suffit à détecter la stagnation ; le comptage exact des
    lignes est le travail de `analyse.py`, lancé à la demande.
    """
    from .journal import journal

    try:
        chemin = journal.fichier_du_jour()
        taille_journal.set(chemin.stat().st_size if chemin.is_file() else 0)
    except Exception:  # noqa: BLE001 — la métrique ne doit rien casser
        pass
