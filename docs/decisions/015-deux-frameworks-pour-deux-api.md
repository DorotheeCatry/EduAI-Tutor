# 015 — Deux frameworks pour deux API : DRF pour les données, FastAPI pour le service IA

**Date :** 28/08/2026
**Statut :** adoptée
**Compétences concernées :** C5 (E1), C9 (E2), C13 (E3), C20 (E5)

## Contexte

Le référentiel évalue séparément deux API : celle qui expose le **jeu de
données** (C5, Bloc 1) et celle qui expose le **service IA** (C9, Bloc 2).
L'application Django existait déjà et servait la première en Django REST
Framework. Restait à décider où vivrait la seconde.

## Options

1. **Une seconde application DRF** dans le même projet Django, sous un préfixe
   distinct. Aucune dépendance nouvelle, un seul processus à exploiter.
2. **Un service FastAPI distinct**, dans son propre processus et son propre
   conteneur.

## Décision

Option 2, pour trois raisons dont une seule est décisive.

### La raison technique, qui est la vraie

Un appel au fournisseur de modèles dure **entre deux et dix secondes**, et ce
temps est passé à **attendre le réseau** — le processus ne calcule rien.

Sous DRF en WSGI, chaque appel mobilise un travailleur pendant toute cette
attente. Huit travailleurs, huit générations simultanées, et la neuvième
requête attend qu'un travailleur se libère — y compris s'il ne s'agit que de
lire `/ai/sante`.

Sous FastAPI, chaque attente rend la main à la boucle d'événements. C'est
visible dans le code, à deux endroits distincts :

- `await recuperateur.ainvoke(...)` dans `/ai/recherche` — LangChain expose ici
  une variante réellement asynchrone, l'attente ne mobilise **ni fil ni
  travailleur** ;
- `await asyncio.to_thread(...)` pour les agents synchrones, qui partent dans
  un fil pendant que la boucle continue de servir les autres requêtes.

Le second n'est pas le premier : un fil reste mobilisé. Mais il libère la
boucle, ce qui suffit à servir la santé et la recherche pendant qu'une
génération longue est en cours.

**Sans ce besoin, l'option 1 aurait été préférable** — une dépendance de moins,
un processus de moins. C'est la nature I/O de l'appel LLM qui décide, pas le
goût du framework.

### La raison d'évaluation

Le référentiel évalue les deux API séparément. Deux frameworks, deux processus,
deux préfixes d'URL : le périmètre de chacune se lit sans explication. Un jury
qui ouvre `/api/dataset/` et `/ai/` voit deux API, pas deux dossiers.

### La raison d'exploitation

La panne de l'une ne fait pas tomber l'autre. Le corpus reste consultable quand
le fournisseur de modèles est indisponible — et c'est justement le moment où
l'on veut pouvoir consulter le corpus.

## Ce que le service NE fait pas

**Il ne réécrit aucun agent.** Il expose ceux de `apps/agents/`. Un service qui
réimplémenterait leur logique créerait deux comportements à maintenir, et le
jour où ils divergeraient, l'application web et l'API ne répondraient plus la
même chose à la même question.

Conséquence assumée : le processus FastAPI **amorce Django** (`django.setup()`),
parce que les agents touchent l'ORM — le Watcher enregistre les méprises dans
`eduai_app`. L'alternative aurait été un appel HTTP vers l'application Django,
qui ajouterait un saut réseau, une sérialisation, une authentification et un
mode de panne supplémentaires pour atteindre du code Python du même dépôt.

## Un défaut trouvé en vérifiant, et qui touchait aussi Django

Le monitorage devait couvrir les appels passant par cette API. Vérification
faite : **il ne les couvrait pas.**

`installer()` posait la sonde dans une variable de contexte par `set()`. Or une
variable de contexte posée par `set()` n'est visible que dans le contexte qui
l'a posée et ceux qui en dérivent — et chaque requête HTTP s'exécute dans sa
propre tâche asyncio sous FastAPI, dans son propre fil sous WSGI. Aucune
n'héritait du contexte du démarrage.

**La sonde s'annonçait branchée dans les journaux et ne traçait aucun appel de
requête.** C'est exactement le motif que le paquet de monitorage existe pour
détecter : un composant qui se déclare opérationnel sans produire d'effet.

Le défaut ne touchait pas que FastAPI : le serveur Django était dans le même
cas, et les vérifications précédentes n'y avaient rien vu parce qu'elles
tournaient dans des scripts, où le contexte est celui de l'import.

Correction : la sonde est désormais la **valeur par défaut** de la variable de
contexte, lue par tout fil et toute tâche, plutôt qu'une valeur posée au
démarrage. Vérifié après correction : un appel à `/ai/recherche` produit bien
un événement `recherche_rag` au journal, depuis le processus FastAPI.

## Conséquences

- Deux dépendances ajoutées : `fastapi` et `slowapi` — cette dernière pour la
  limitation de débit, que FastAPI ne fournit pas en propre.
- Un conteneur de plus dans `docker-compose.yml`, sur le réseau de l'hôte comme
  le collecteur et Grafana.
- **Un seul travailleur uvicorn**, et c'est documenté : les compteurs
  Prometheus vivent en mémoire du processus. Plusieurs travailleurs feraient
  collecter une fraction du trafic par le superviseur, tant que l'agrégation
  multi-processus n'est pas activée.
- Deux documents OWASP distincts, `docs/securite_api_donnees.md` et
  `docs/securite_api_service_ia.md`. Ils ne sont pas redondants : l'API données
  **lit** un corpus, celle-ci **dépense**. Le risque principal de la seconde
  n'est ni la fuite ni l'altération, mais l'épuisement du quota — par un tiers,
  ou par un client légitime en boucle.

## Vérifications

| Contrôle | Résultat |
|---|---|
| Routes exposées | 6, plus la documentation |
| Santé sans clé | **200** — volontairement ouverte, un orchestrateur n'a pas à porter de secret |
| Génération sans clé | **401** |
| Génération avec clé fausse | **401**, message identique |
| Six entrées invalides | **422**, champ fautif et raison |
| Sujet composé d'espaces | **422** — `min_length` compte les espaces, un validateur explicite était nécessaire |
| Erreur de dépendance | **503** avec identifiant de corrélation, trace au journal seulement |
| Schéma OpenAPI | `APIKeyHeader` déclaré, 5 routes protégées, 1 ouverte |
| Monitorage depuis FastAPI | événement `recherche_rag` tracé, agent, latence, classe d'erreur |
