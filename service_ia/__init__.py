"""
API REST du service IA (C9, Bloc 2).

Compétence visée : C9 (épreuve E2) — API REST exposant le service d'IA

Service FastAPI distinct de l'API du jeu de données (C5), écrite en Django REST
Framework. Le référentiel évalue les deux séparément ; deux frameworks et deux
processus rendent le périmètre de chacune lisible sans explication.

Ce paquet n'écrit pas d'agent : il expose ceux qui existent déjà dans
`apps/agents/`. Un service qui réimplémenterait la logique des agents créerait
deux comportements à maintenir, et le jour où ils divergeraient, l'application
web et l'API ne répondraient plus la même chose à la même question.
"""
