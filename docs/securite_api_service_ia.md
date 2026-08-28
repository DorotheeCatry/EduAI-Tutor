# Sécurité de l'API du service IA — OWASP API Security Top 10

**Date :** 28 août 2026
**Portée :** `/ai/*`, paquet `service_ia/`, service FastAPI
**Compétence visée :** C9 (épreuve E2) — API REST exposant le service d'IA
**Compétences concernées :** C13 (E3) — sécurité ; C4 (E1) — minimisation

Ce document traite l'API du **service IA** (C9, Bloc 2). Celle du **jeu de
données** (C5, Bloc 1) a le sien, `docs/securite_api_donnees.md`. Les deux ne
sont pas redondants : ils décrivent deux périmètres dont les modèles de menace
diffèrent, et c'est cette différence qui justifie deux documents.

---

## Ce qui distingue cette API de l'autre

| | API jeu de données (C5) | API service IA (C9) |
|---|---|---|
| Framework | Django REST Framework | FastAPI |
| Nature | **lit** un corpus | **dépense** |
| Risque principal | redistribution hors licence | épuisement du quota fournisseur |
| Coût d'un appel | une requête SQL | un appel facturé au fournisseur |
| Écriture | impossible à trois niveaux | sans objet, rien n'est stocké |

**Le risque principal ici n'est ni la fuite ni l'altération : c'est la
dépense.** Un tiers qui obtient une clé ne vole pas de données — il consomme un
budget. Un client légitime en boucle produit le même effet sans intention
malveillante. Tout ce qui suit découle de ce constat.

---

## Les dix points

### API1 — Broken Object Level Authorization

**Traitement.** **Sans objet au sens strict** : cette API n'expose aucun objet
persistant. Elle ne lit ni ne rend d'entité identifiée par un identifiant
devinable — chaque appel produit une réponse à partir des seules données du
corps de la requête.

Le seul objet atteignable est le corpus, par `/ai/recherche`, et il est le même
pour tout appelant authentifié.

### API2 — Broken Authentication

**Traitement.** Clé de service dans l'en-tête `X-Cle-Service`, exigée sur les
cinq routes de génération et de recherche.

- **Plusieurs clés acceptées**, séparées par des virgules : une clé par
  consommateur. Révoquer celle qui fuit n'interrompt pas les autres — et une
  révocation qu'on n'ose pas faire n'est pas une révocation.
- **Comparaison à temps constant** (`hmac.compare_digest`). La comparaison de
  chaînes de Python s'arrête au premier caractère différent, ce qui rend sa
  durée dépendante du préfixe commun : un attaquant patient déduit la clé
  caractère par caractère.
- **Aucune valeur de repli.** Une clé par défaut dans le code est une clé
  publique. Si `SERVICE_IA_CLES` manque, le service répond 503 à tout appel
  plutôt que d'ouvrir l'accès.
- **Même réponse pour une clé absente et une clé fausse.** Distinguer les deux
  dirait à l'appelant si le nom de l'en-tête est correct.

**Vérifié.** Sans en-tête : **401**. Avec une clé fausse : **401**, message
identique.

**`/ai/sante` est volontairement ouverte.** Une sonde de santé est interrogée
par un orchestrateur ou un superviseur, auxquels on ne confie pas un secret
d'appel. Elle ne divulgue que des noms de modèles et des décomptes.

### API3 — Broken Object Property Level Authorization

**Traitement.** Validation Pydantic **en entrée et en sortie**.

Valider l'entrée protège le service ; valider la sortie protège le client. Un
agent appelle un modèle de langage, dont la réponse n'est pas garantie — JSON
tronqué, champ absent, texte vide. Sans contrat de sortie, ces cas traversent
l'API et deviennent l'erreur du consommateur, loin de leur cause.

Le contrat de sortie porte un champ `tronquee`, positionné quand la réponse
semble coupée : accolades non refermées, absence de ponctuation finale. Une
réponse tronquée par une limite de jetons n'est pas une erreur du service —
elle aboutit, elle est incomplète. La renvoyer sans le dire ferait porter au
client la charge de s'en apercevoir.

**Vérifié.** Six entrées invalides sur quatre points de terminaison : toutes
refusées en **422**, avec le champ fautif et la raison.

### API4 — Unrestricted Resource Consumption

**C'est le point central de cette API.** Quatre mesures, qui ne protègent pas
de la même chose.

| Mesure | Valeur | Ce qu'elle borne |
|---|---|---|
| Quota de génération | 30/minute par clé | la consommation dans le temps |
| Quota de recherche | 120/minute par clé | idem, plus haut : la recherche ne touche pas le fournisseur |
| Plafond de concurrence | 4 appels simultanés | la charge **instantanée** |
| Bornes de taille | sujet 500 car., code 20 000 car. | le coût d'un appel unitaire |

**Le quota et le plafond de concurrence sont deux choses distinctes.** Trente
appels lancés dans la même seconde respectent un quota de trente par minute et
saturent pourtant la mémoire du service et le débit du fournisseur.

**Le quota est imputé à la clé, pas à l'adresse.** Limiter par adresse punit
tous les consommateurs derrière un même réseau et n'arrête pas un client qui
change d'adresse. Et la clé n'est pas écrite en entier dans le compteur — huit
caractères préfixés — parce que les clés de limitation apparaissent dans les
journaux de diagnostic.

`nombre_questions` est plafonné à 10 et `nombre_fragments` à 20 : chaque unité
au-delà est un appel facturé de plus.

### API5 — Broken Function Level Authorization

**Traitement.** Six routes, aucune administrative, aucune d'écriture. Le service
ne persiste rien de ce qu'il reçoit — il n'y a donc pas de fonction privilégiée
à protéger.

La seule asymétrie est `/ai/sante`, ouverte, et elle est délibérée et documentée
ci-dessus.

### API6 — Unrestricted Access to Sensitive Business Flows

**Traitement.** Le flux détournable est évident : faire produire du contenu par
le modèle aux frais de l'organisme — le service comme passerelle gratuite vers
un fournisseur payant.

Trois freins : clé nominative par consommateur, quota par clé, et bornes de
taille sur les entrées. Un consommateur qui abuse est identifiable par sa clé
et révocable sans toucher aux autres.

**Le coût réel est mesuré**, pas supposé : chaque appel est tracé avec ses
jetons d'entrée et de sortie et son coût estimé, et le tableau de bord affiche
le cumul par modèle (C20).

### API7 — Server Side Request Forgery

**Traitement.** **Sans objet.** Aucun point de terminaison n'accepte d'URL. Les
seules requêtes sortantes du service vont au fournisseur de modèles, dont
l'adresse vient de la configuration et jamais du corps d'une requête.

Le corpus interrogé est un vector store local, sur disque, monté en lecture
seule dans le conteneur.

### API8 — Security Misconfiguration

**Traitement.**

- **Aucune trace d'exception renvoyée au client.** Une erreur inattendue rend
  un identifiant de corrélation ; la trace complète part au journal de
  monitorage. L'identifiant donne le diagnostic sans la divulgation — une trace
  expose les chemins du serveur, les versions des bibliothèques et parfois des
  valeurs de configuration.
- **Conteneur sans privilèges** : l'image crée un compte dédié et abandonne
  root avant de démarrer.
- **`DJANGO_DEBUG` forcé à `False`** dans le conteneur.
- **Aucun secret dans l'image** : toutes les valeurs sensibles viennent de
  l'environnement, avec `:?` dans le `docker-compose.yml` — le conteneur refuse
  de démarrer si l'une manque, plutôt que de démarrer diminué.
- **Un seul travailleur**, choix documenté : les compteurs Prometheus vivent en
  mémoire du processus, et plusieurs travailleurs feraient collecter au
  superviseur une fraction du trafic.

**Vérifié.** Une erreur de dépendance rend **503** avec
`identifiant_incident`, et la trace complète se retrouve au journal.

### API9 — Improper Inventory Management

**Traitement.** Six points de terminaison, tous documentés, schéma OpenAPI
engendré depuis le code :

```
POST /ai/cours        génération d'un cours
POST /ai/explication  réexplication adaptée d'une notion  (Pédagogue)
POST /ai/exercice     génération d'un exercice            (Coach)
POST /ai/feedback     retour sur une soumission de code   (Coach)
POST /ai/recherche    recherche RAG seule, sans génération
GET  /ai/sante        état du service
```

Documentation à `/ai/docs` (Swagger UI), `/ai/redoc` et `/ai/openapi.json`.

**Le schéma déclare l'authentification.** Le point avait été manqué : les
routes étaient protégées et le schéma n'en disait rien, si bien qu'un
consommateur lisant la documentation aurait découvert l'exigence par un 401 sans
explication. Corrigé — `APIKeyHeader` apparaît désormais dans
`components.securitySchemes`, et cinq routes sur six portent `security`.

Le préfixe `/ai/` distingue cette API de `/api/dataset/`, servie par un autre
framework dans un autre processus. La séparation exigée par le référentiel se
lit dans l'URL.

### API10 — Unsafe Consumption of APIs

**Traitement.** Cette API **consomme** un service tiers : le fournisseur de
modèles. C'est le seul des deux documents où ce point n'est pas sans objet.

- **La réponse du fournisseur est validée** par le contrat Pydantic de sortie,
  jamais renvoyée telle quelle.
- **Les erreurs du fournisseur sont converties** en réponses de service : un 404
  sur un modèle retiré du catalogue devient un 503 côté API, avec un
  identifiant de corrélation. Le code de retour du fournisseur est conservé
  dans les métriques, où il distingue un quota atteint (429) d'un modèle
  disparu (404) et d'une indisponibilité (503).
- **Le projet a déjà vécu ce cas** : un modèle codé en dur retiré par Groq a
  provoqué une panne complète de la couche IA (voir `docs/decisions/001`).
- **Le repli local** par Ollama est configuré, ce qui évite qu'une
  indisponibilité du fournisseur soit une indisponibilité du service.

---

## Ce qui n'est pas reçu, et pourquoi

`/ai/feedback` **n'accepte aucun identifiant d'apprenant.** Le retour porte sur
du code, pas sur une personne. Le service n'a pas besoin de savoir qui a écrit
la soumission pour la corriger — et ce qui n'est pas reçu ne peut ni fuiter, ni
être conservé par erreur, ni être transmis au fournisseur par distraction.

C'est la même règle que celle appliquée au corpus (`docs/rgpd_eduai_data.md`
§ 5) et à l'extracteur S4 : la minimisation s'applique à l'entrée, pas après
coup.

Le monitorage suit la même règle : il consigne la **longueur** des prompts et
des requêtes, jamais leur contenu.

---

## Ce qui reste à traiter

| Point | Portée | Traitement prévu |
|---|---|---|
| Clés sans expiration | API2 | Rotation, ou clés signées à durée limitée, si le service sort du réseau interne |
| Quota en mémoire du processus | API4 | Un seul travailleur aujourd'hui, donc exact. Redis serait nécessaire pour plusieurs |
| Pas de journalisation d'accès | API9 | Seuls les appels au fournisseur sont tracés, pas les appels reçus |
| Pas de plafond global | API4 | Le quota est par clé ; rien ne borne la somme de tous les consommateurs |

---

## Vérifications, en une commande

```bash
# Le service doit tourner, et CLE contenir une clé déclarée dans SERVICE_IA_CLES.
B=http://127.0.0.1:8100
curl -s -o /dev/null -w "santé sans clé   : %{http_code}\n" $B/ai/sante
curl -s -o /dev/null -w "cours sans clé   : %{http_code}\n" -X POST \
     -H 'Content-Type: application/json' -d '{"sujet":"python"}' $B/ai/cours
curl -s -o /dev/null -w "clé invalide     : %{http_code}\n" -X POST \
     -H 'Content-Type: application/json' -H "X-Cle-Service: fausse" \
     -d '{"sujet":"python"}' $B/ai/cours
curl -s -o /dev/null -w "entrée invalide  : %{http_code}\n" -X POST \
     -H 'Content-Type: application/json' -H "X-Cle-Service: $CLE" \
     -d '{"sujet":"   "}' $B/ai/cours
```

Attendu : `200`, `401`, `401`, `422`.
