# Note — pourquoi deux API, et pourquoi deux frameworks

Note personnelle de préparation à l'oral. Résume l'argumentation à tenir sur le
choix d'architecture le plus discutable du projet, et les questions auxquelles
il faut savoir répondre.

**Compétences concernées :** C5 (épreuve E1), C9 (épreuve E3), C15 (épreuve E4)

---

## 1. Le point de départ : le référentiel exige deux API

Ce n'est pas un choix esthétique. Deux compétences distinctes, dans deux blocs
distincts, évaluées lors de deux épreuves distinctes :

| | API du jeu de données | API du service IA |
|---|---|---|
| Compétence | **C5** | **C9** |
| Bloc | 1 | 2 |
| Épreuve | E1 | E3 |
| Framework retenu | Django REST Framework | FastAPI |
| Préfixe | `/api/dataset/` | `/ai/` |

Si les deux périmètres partagent le même code, le même préfixe et le même
processus, le jury ne peut pas cocher séparément. La séparation par framework
rend le découpage lisible sans avoir à l'expliquer.

---

## 2. La vraie justification : deux modèles de menace

C'est l'argument principal, et le seul qui tienne si on creuse.

**L'API du jeu de données lit.** Elle sert un corpus déjà collecté, stocké dans
PostgreSQL. Une requête coûte une lecture disque. Un abus fait de la charge.

**L'API du service IA dépense.** Chaque appel déclenche une requête facturée au
fournisseur de modèles. Un abus fait une facture. Le quota n'y est pas un
confort d'exploitation, c'est une protection budgétaire.

D'où des réglages différents qui ne se justifieraient pas dans un service
unique : la génération est plafonnée plus bas que la recherche, parce que la
première appelle le fournisseur et que la seconde n'interroge que le vector
store local.

> **Formule à retenir :** « celle-ci ne lit pas un corpus, elle dépense ».

---

## 3. Pourquoi DRF pour les données

- L'API est adossée à l'ORM Django et aux modèles existants. Réécrire l'accès
  aux données sous FastAPI aurait dupliqué ce que Django fournit déjà.
- Le routeur de base de données Django permet d'exposer `eduai_data` en lecture
  seule depuis une application qui vit sur `eduai_app`. C'est une fonctionnalité
  native, pas un contournement.
- La pagination, le filtrage et les permissions de DRF couvrent exactement le
  besoin sans code supplémentaire.

## 4. Pourquoi FastAPI pour le service IA

- **L'asynchrone.** Une génération dure plusieurs secondes. Sous DRF en WSGI,
  elle bloquerait un travailleur entier pendant toute l'attente — y compris
  pour servir la route de santé. Sous FastAPI, l'attente ne mobilise pas le
  processus.
- **La validation Pydantic** des entrées et des sorties est native, et le
  schéma OpenAPI en découle automatiquement plutôt que d'être maintenu à part.
- **Le découplage.** Le service IA tourne dans son propre conteneur. Il peut
  tomber sans emporter l'API de données, et inversement.

**Nuance à connaître, parce qu'un jury technique peut la demander :** toutes les
routes ne sont pas asynchrones de la même façon. La recherche RAG utilise une
variante réellement asynchrone (`ainvoke`) — l'attente ne mobilise ni fil ni
travailleur. Les agents synchrones passent par un transfert vers un fil séparé
(`asyncio.to_thread`), ce qui libère la boucle d'événements mais pas le fil.
Ce n'est pas la même chose, et le code le distingue explicitement.

---

## 5. Les questions probables, et les réponses

**« Pourquoi ne pas avoir tout fait en DRF ? »**
Parce qu'une génération de plusieurs secondes bloque un travailleur WSGI, et
parce que les deux périmètres n'ont pas le même modèle de menace. Un service qui
dépense de l'argent à chaque appel ne se protège pas comme un service qui lit.

**« Pourquoi ne pas avoir tout fait en FastAPI ? »**
Parce que l'API de données est adossée à l'ORM Django. La réécrire aurait
dupliqué la couche d'accès aux données pour un gain nul.

**« Maintenir deux frameworks, n'est-ce pas un coût ? »**
Oui, et il est assumé. Le coût réel est faible : les deux services partagent le
même environnement de dépendances et le même journal de monitorage. Le service
IA amorce Django pour réutiliser les agents plutôt que de les réécrire.

**« Comment garantissez-vous que l'API de données ne peut pas écrire ? »**
Trois niveaux, dont un seul suffirait mais dont deux vivent dans le code :
routeur Django en lecture seule, vues en lecture seule, et un rôle PostgreSQL
ne disposant que du `SELECT`. Le troisième a déjà servi : une commande de
migration a été refusée par le moteur avant même que le routeur soit consulté.

**« Comment le jury vérifie-t-il la séparation ? »**
Deux préfixes, deux processus, deux conteneurs, deux fichiers de documentation
de sécurité. La description en tête de la documentation OpenAPI du service IA
nomme explicitement l'autre API et la compétence visée.

---

## 6. Ce qu'il ne faut pas dire

- « J'ai utilisé FastAPI parce que c'est plus moderne. » Ce n'est pas un
  argument, et ça invite à demander pourquoi tout n'y est pas.
- « Les deux API sont séparées parce que le référentiel le demande. » Vrai mais
  faible : cela présente une contrainte administrative là où il existe une
  raison technique.
- Prétendre que tout est asynchrone. La distinction `ainvoke` /
  `asyncio.to_thread` est vérifiable dans le code.

---

## 7. Limites assumées, à énoncer avant qu'on les trouve

- Les jetons d'authentification DRF n'expirent pas.
- Le compteur de quota vit dans la mémoire du processus : derrière plusieurs
  travailleurs, il ne serait plus global.
- DRF évalue les permissions avant la limitation de débit : un client anonyme
  reçoit un 401 et jamais un 429. Sans conséquence ici puisque toutes les
  routes exigent un jeton, mais c'est mesuré et documenté.
