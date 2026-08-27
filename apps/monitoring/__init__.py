"""
Monitorage du service IA.

Compétence visée : C20 (épreuve E5) — monitorage du service en production
Compétence visée : C21 (épreuve E5) — détection et résolution d'incident

Trois modules, trois responsabilités :

    journal.py   écriture JSON Lines, hors base de données
    sondes.py    instrumentation des appels LLM et des recherches RAG
    alertes.py   seuils de taux d'erreur et de latence
    couts.py     estimation monétaire à partir des jetons réellement facturés
    analyse.py   lecture hors ligne du journal et rapport de période

Branchement, une seule ligne au démarrage de l'application :

    from apps.monitoring.sondes import installer
    installer()

Le paquet n'est PAS une application Django : il ne déclare aucun modèle et
n'écrit dans aucune base. C'est délibéré — le monitorage doit survivre à la
panne qu'il observe.
"""
