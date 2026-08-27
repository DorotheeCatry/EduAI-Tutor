# Sécurité de l'API du jeu de données — OWASP API Security Top 10

**Date :** 27 août 2026
**Portée :** `/api/dataset/*`, application `apps/api_data`
**Compétence visée :** C5 (épreuve E1) — API REST exposant le jeu de données
**Compétences concernées :** C4 (E1) — RGPD et licences ; C13 (E3) — sécurité

Ce document traite l'API du **jeu de données** (C5, Bloc 1). L'API du **service
IA** (C9, Bloc 2), qui vivra dans un service FastAPI distinct, fera l'objet de
son propre document : les deux périmètres n'ont ni les mêmes données, ni les
mêmes risques, ni la même surface.

---

## Résumé du modèle de menace

L'API est **en lecture seule** sur un corpus documentaire qui **ne contient
aucune donnée à caractère personnel** (voir `docs/rgpd_eduai_data.md` § 4). Les
deux risques principaux ne sont donc ni la fuite de données personnelles ni
l'altération des données, mais :

1. **La redistribution de contenus dont la licence l'interdit.** Le corpus
   agrège cinq sources aux conditions différentes ; certaines interdisent la
   rediffusion. Les diffuser engagerait l'organisme.
2. **La consommation de ressources.** Le corpus pèse une vingtaine de
   mégaoctets de texte. Un appel mal borné le sérialise intégralement.

---

## Les dix points

### API1 — Broken Object Level Authorization

**Risque.** Un utilisateur atteint un objet auquel il n'a pas droit en devinant
son identifiant.

**Traitement.** Le corpus n'a pas de propriétaire par objet : tout compte
authentifié voit les mêmes documents. La règle d'autorisation n'est donc pas
« à qui appartient cet objet ? » mais « cet objet est-il diffusable ? », et
elle est portée par le gestionnaire par défaut du modèle
(`DocumentExposableManager`), non par les vues.

**Vérifié.** Un document sous licence `A_VERIFIER` existant en base sous
l'identifiant 15484 renvoie **404** en accès direct, **0 résultat** par filtre,
et **0 résultat** par recherche plein texte sur son propre titre.

### API2 — Broken Authentication

**Risque.** Authentification absente, contournable ou fondée sur un secret
partagé.

**Traitement.** Deux mécanismes : jeton porteur (`TokenAuthentication`) pour
les clients programmatiques, session pour la documentation interactive
consultée depuis un navigateur. Un jeton est révocable individuellement, sans
toucher au mot de passe du compte.

**Vérifié.** Sans en-tête `Authorization`, tous les points de terminaison
renvoient **401**.

**Limite assumée.** Les jetons DRF n'expirent pas. Pour un service exposé au
public, une rotation ou un passage à des jetons courts signés serait
nécessaire. Le service est aujourd'hui interne et publié sur la boucle locale.

### API3 — Broken Object Property Level Authorization

**Risque.** L'API renvoie plus de champs qu'elle ne devrait, ou en accepte plus
qu'elle ne devrait.

**Traitement.** Les sérialiseurs listent explicitement leurs champs — aucun
`fields = "__all__"`. Aucun sérialiseur d'écriture n'existe, donc aucun champ
n'est acceptable en entrée.

Deux champs sont exposés délibérément parce que le consommateur en a besoin
pour respecter la licence : `attribution_requise` et `url_source`. Les taire
reviendrait à distribuer un contenu sous condition sans énoncer la condition.

### API4 — Unrestricted Resource Consumption

**Risque.** Un appel ramène un volume arbitraire, ou un client appelle sans
limite.

**Traitement.**

| Mesure | Valeur |
|---|---|
| Pagination | 20 éléments par page, obligatoire |
| Plafond de page | 100, `taille_page` au-delà est ramené à 100 |
| Quota par compte | 1 000 requêtes par jour |
| Contenu en liste | extrait de 400 caractères, texte intégral au détail seul |
| Recherche | index GIN, `Bitmap Index Scan` et non balayage complet |

**Vérifié.** `?taille_page=100000` renvoie **100** éléments. Avec un quota
abaissé à 3 par minute pour l'essai, la quatrième requête renvoie **429**.

**Limite mesurée et assumée.** Le quota anonyme (`AnonRateThrottle`) **ne se
déclenche jamais** sur cette API. DRF vérifie les permissions *avant* la
limitation de débit : une requête sans jeton reçoit 401 et n'atteint pas le
compteur. Vérifié : quatre requêtes anonymes avec un quota de 2 par minute
renvoient `[401, 401, 401, 401]`, et non `[401, 401, 429, 429]`.

Ce n'est pas un défaut de configuration mais l'ordre de traitement de DRF, et
il n'est pas gênant ici : tous les points de terminaison exigent une
authentification, donc une requête anonyme est rejetée avant tout accès à la
base — elle ne coûte presque rien. Une inondation anonyme relève d'une
protection en amont (proxy inverse, limitation par adresse), pas du cadre
applicatif. Le quota anonyme est conservé pour qu'un point de terminaison
public ajouté un jour soit couvert d'emblée.

### API5 — Broken Function Level Authorization

**Risque.** Une fonction sensible est atteignable par un utilisateur qui ne
devrait pas y accéder — typiquement, l'écriture.

**Traitement.** Trois garde-fous superposés, tenus par trois acteurs différents.

| Garde-fou | Tenu par |
|---|---|
| `ReadOnlyModelViewSet` : aucune route d'écriture n'est routée | le routage HTTP |
| Le routeur de base lève `EcritureInterdite` sur toute écriture | le code Django |
| Le rôle `eduai_lecture` ne dispose que du `SELECT` | PostgreSQL |

Ils échouent différemment : un bogue du routeur ne contourne pas le rôle, un
point de terminaison ajouté par distraction ne contourne ni l'un ni l'autre.

**Vérifié.** `POST`, `PUT` et `DELETE` sur `/api/dataset/documents/` renvoient
**405**. Le rôle `eduai_lecture` reçoit `permission denied for table document`
sur un `DELETE` direct. Et `manage.py migrate --database=eduai_data` est refusé
par PostgreSQL avant même que le routeur ne soit consulté — démonstration
fortuite mais nette de l'intérêt de la superposition.

### API6 — Unrestricted Access to Sensitive Business Flows

**Risque.** Un flux métier légitime est automatisé à grande échelle et détourné
de son usage.

**Traitement.** Le flux détournable ici est l'aspiration du corpus complet, qui
permettrait de le republier hors de ses conditions de licence. Trois freins :
authentification nominative, quota journalier, et exclusion des documents non
redistribuables. Le corpus reste massivement aspirable par un compte légitime —
c'est assumé : il est destiné à être consommé par le service RAG du projet, et
les documents qui sortent sont ceux dont la licence autorise la rediffusion.

### API7 — Server Side Request Forgery

**Risque.** L'API récupère une ressource à une URL fournie par le client.

**Traitement.** **Sans objet.** Aucun point de terminaison n'accepte d'URL ni
n'émet de requête sortante. Le champ `url_source` est renvoyé au client, jamais
suivi par le serveur.

### API8 — Security Misconfiguration

**Risque.** Réglages permissifs, traces d'erreur exposées, en-têtes absents.

**Traitement.**

- `DEBUG` lu depuis l'environnement, **`False` par défaut** : une variable
  oubliée dégrade le confort, jamais la sécurité (décision 008).
- `ALLOWED_HOSTS` limité à la boucle locale par défaut.
- Hors débogage : redirection HTTPS, HSTS d'un an, cookies de session et CSRF
  marqués `Secure` et `SameSite`.
- `DJANGO_DEBUG=False manage.py check --deploy` : **aucun avertissement**.
- Aucun secret dans le code versionné ; la clé Django, le mot de passe
  PostgreSQL et celui du rôle de lecture vivent dans `.env`, exclu du dépôt.
- Le schéma OpenAPI est engendré depuis le code : il ne peut pas décrire des
  routes qui n'existent pas, ni taire celles qui existent.

### API9 — Improper Inventory Management

**Risque.** Des points de terminaison oubliés, non documentés, ou d'anciennes
versions restées en ligne.

**Traitement.** Sept points de terminaison, tous en `GET`, tous documentés :

```
GET /api/dataset/documents/                 liste paginée, filtrable, recherche
GET /api/dataset/documents/{id_document}/   détail + attributs du type de source
GET /api/dataset/sources/                   les cinq sources et leurs contraintes
GET /api/dataset/sources/{code_source}/     détail d'une source
GET /api/dataset/extractions/               historique des campagnes
GET /api/dataset/extractions/{id}/          détail d'une campagne
GET /api/dataset/statistiques/              volumétrie du corpus
```

La documentation est engendrée depuis le code et servie à `/api/docs/`
(Swagger UI), `/api/redoc/` (ReDoc) et `/api/schema/` (OpenAPI 3). Le schéma
est restreint au préfixe `/api/dataset` : les vues de l'application web n'y
figurent pas.

Le préfixe distingue l'API du jeu de données (C5) de celle du service IA (C9),
qui prendra le sien. La séparation exigée par le référentiel se lit dans l'URL,
avant d'ouvrir le code.

### API10 — Unsafe Consumption of APIs

**Risque.** Le service consomme une API tierce sans valider ce qu'elle renvoie.

**Traitement.** **Sans objet pour cette API**, qui ne consomme rien. La
consommation d'API tierces a lieu dans le pipeline (extracteur S1 sur l'API
Stack Exchange), hors ligne et hors de ce périmètre. L'extracteur y valide les
champs attendus, écarte les enregistrements malformés en les comptant, et
s'arrête au-delà de cinquante erreurs — un problème systémique n'est pas un
problème ponctuel.

---

## Ce qui reste à traiter

| Point | Portée | Traitement prévu |
|---|---|---|
| Jetons sans expiration | API2 | Rotation, ou jetons signés à durée limitée, si le service sort du réseau interne |
| Quota partagé en mémoire | API4 | Le compteur de débit vit dans le cache local du processus. Avec plusieurs processus, chacun applique son propre quota. Redis, déjà présent pour les WebSockets, réglerait le point |
| Inondation anonyme | API4 | Relève d'un proxy inverse, hors du cadre applicatif |
| Journalisation des accès | API9 | Aucune trace applicative des appels à l'API ; seuls les journaux du serveur en gardent la trace |

---

## Vérifications, en une commande

```bash
# Le serveur doit tourner, et JETON contenir un jeton valide.
curl -s -o /dev/null -w "sans jeton      : %{http_code}\n" \
     http://127.0.0.1:8000/api/dataset/documents/
curl -s -o /dev/null -w "avec jeton      : %{http_code}\n" \
     -H "Authorization: Token $JETON" http://127.0.0.1:8000/api/dataset/documents/
curl -s -o /dev/null -w "POST (écriture) : %{http_code}\n" -X POST \
     -H "Authorization: Token $JETON" http://127.0.0.1:8000/api/dataset/documents/
curl -s -H "Authorization: Token $JETON" \
     "http://127.0.0.1:8000/api/dataset/documents/?licence=A_VERIFIER"
```

Attendu : `401`, `200`, `405`, et une liste vide.
