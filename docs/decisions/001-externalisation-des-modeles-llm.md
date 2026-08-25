# 001 — Externalisation et routage des modèles LLM

**Date :** 25/08/2026
**Statut :** adoptée
**Compétences concernées :** C7 (E2), C10 (E3), C20 et C21 (E5)

## Contexte

La couche IA de l'application était totalement inopérante. Trois causes
indépendantes, identifiées lors de l'état des lieux :

1. Le modèle `meta-llama/llama-4-scout-17b-16e-instruct` renvoyait
   `404 model_not_found` : Groq l'a retiré de son catalogue. Il était écrit en
   dur dans trois fichiers (`agent_researcher.py`, `agent_pedagogue.py`,
   `agent_coach.py`), sans constante ni configuration.
2. L'ensemble des modèles du catalogue renvoyait
   `403 model_permission_blocked_project` : aucun modèle n'était autorisé au
   niveau du projet Groq. La clé API était pourtant valide, le listing des
   modèles répondant en 200.
3. Ollama était absent de la machine, empêchant le calcul des embeddings du
   RAG et forçant les agents sur un repli LLM lui-même bloqué.

## Options envisagées

**A — Remplacer l'identifiant de modèle dans les trois fichiers.**
Corrige la panne immédiate. Ne prévient pas sa répétition : le prochain retrait
de modèle par le fournisseur reproduira exactement le même incident.

**B — Centraliser l'identifiant dans une constante unique.**
Réduit la duplication mais impose une modification du code et un redéploiement
à chaque changement de modèle. Inutilisable pour basculer pendant une
démonstration.

**C — Externaliser en variables d'environnement, avec routage par agent.**
Retenue.

## Décision

Option C. Un module `model_config.py` centralise le catalogue et expose
`get_model_for(agent)`. La résolution suit un ordre explicite : variable
spécifique à l'agent, puis variable globale, puis routage par défaut.

Le routage par défaut distingue les besoins : modèle de qualité
(`gpt-oss-120b`) pour Researcher et Pedagogue, modèle rapide (`gpt-oss-20b`)
pour Coach et Watcher.

Trois modèles ont été débloqués dans la console Groq : les deux ci-dessus, plus
`qwen/qwen3.6-27b`, retenu pour appartenir à une autre famille et rendre le
benchmark C7 plus significatif qu'une comparaison interne à un seul fournisseur.

Un drapeau `USE_LOCAL_LLM` permet la bascule vers Ollama.

## Conséquences

**Positives.** Le changement de modèle ne demande plus de modification de code.
Un agent peut être basculé isolément pendant la soutenance. Le repli local
répond à deux besoins distincts : continuité de service en cas
d'indisponibilité du fournisseur, et traitement local de données d'apprenants
potentiellement mineurs sans transfert à un tiers.

**Négatives.** Le comportement dépend désormais de l'environnement d'exécution,
ce qui rend une erreur de configuration plus difficile à diagnostiquer. Atténué
par un `ValueError` explicite sur agent inconnu et par la journalisation du
modèle résolu à chaque appel.

**Suivi.** Cet incident constitue le cas documenté de l'épreuve E5 (C21). Le
monitorage mis en place doit permettre de détecter une panne équivalente —
taux d'erreur par code HTTP sur les appels au fournisseur.
