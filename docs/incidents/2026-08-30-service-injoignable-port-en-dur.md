# Incident 008 — Un conteneur sain, un service injoignable

**Date :** 30 août 2026
**Composant :** `service_ia/Dockerfile`
**Gravité :** majeure — le service IA déployé n'a jamais répondu à une requête
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — déploiement ; C9 (E2)

---

## 1. Déclenchement

**30/08, en fin de journée.** Premier déploiement sur Railway. L'application web
répond, les migrations passent, la génération IA fonctionne.

Le service IA, lui, répond `404` sur `/ai/sante`. Puis, une fois son démarrage
corrigé côté hébergeur, « Application failed to respond » sur toute requête.

**Ses journaux ne montrent aucune erreur.** Uvicorn démarre, annonce son
écoute, et reste en marche.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Service IA (C9) | **Aucune requête servie**, depuis sa mise en ligne |
| Recherche RAG, génération par l'API | Inatteignables |
| Application web | **Aucun impact** — elle appelle les agents dans son propre processus |
| Données | Aucune perte : le service n'a rien traité |

---

## 3. Diagnostic

### 3.1 Ce que disait la première réponse

Un `404` sur `/ai/sante` se lit comme une route absente. Le relevé a écarté
cette lecture : **toutes** les adresses répondaient `404`, y compris `/`, et
l'en-tête portait `x-railway-fallback: true`. C'est l'edge de l'hébergeur qui
répondait, faute de service actif derrière ce domaine.

Le message a ensuite changé pour « Application failed to respond » : la
plateforme voyait un conteneur, et n'obtenait rien de lui.

### 3.2 Cause racine

Le `CMD` de l'image portait le port en dur :

```dockerfile
CMD ["/app/.venv/bin/uvicorn", "service_ia.main:application", \
     "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
```

Railway attribue un port par la variable `PORT` et **n'interroge que
celui-là**. Le conteneur écoutait sur 8100, la plateforme frappait ailleurs.

Deux détails rendent la panne silencieuse :

- **Le service allait bien.** Il servait, correctement, sur un port que
  personne n'interrogeait. Aucun journal d'erreur ne pouvait exister.
- **La forme exec d'un `CMD` n'étend pas les variables d'environnement.**
  Écrire `--port ${PORT}` dans cette forme aurait transmis la chaîne
  littérale : la correction n'était pas d'ajouter une variable là où il y
  avait un nombre.

### 3.3 Pourquoi l'application web n'avait pas le problème

Elle démarre par `docker/entree-web.sh`, qui lit `${PORT:-8000}`. Le script
existait pour enchaîner les migrations avant le serveur ; le fait qu'il lise le
port de l'environnement en était une conséquence, pas une intention. **Le
service IA n'avait pas de script, donc pas d'endroit où lire quoi que ce soit.**

### 3.4 Pourquoi rien ne l'avait signalé avant

**Le port est libre en local.** On choisit le sien, `docker-compose` publie
8100, et tout concorde. La contrainte n'apparaît qu'avec un hébergeur qui
impose le sien — c'est-à-dire au premier déploiement, jamais avant.

C'est la troisième occurrence du même motif en trois jours : une chose vérifiée
dans un contexte, utilisée dans un autre. La sonde de monitorage éprouvée en
script et déployée dans un serveur (incident 003). Les tests écrits avec
`DEBUG=True` et exécutés avec `DEBUG=False` (incident 007). Le port choisi
librement en local et imposé en production.

---

## 4. Résolution

Un script de démarrage, sur le modèle de celui de l'application web :

```sh
PORT_ECOUTE="${PORT:-8100}"
exec /app/.venv/bin/uvicorn service_ia.main:application \
    --host 0.0.0.0 --port "${PORT_ECOUTE}" --workers 1 \
    --proxy-headers --forwarded-allow-ips '*'
```

La valeur de repli sert au lancement local et au fichier de composition, qui
publie toujours 8100 : **le comportement local est inchangé.**

Deux corrections l'accompagnent :

- **La sonde de vivacité de l'image** interrogeait `127.0.0.1:8100` en dur.
  Elle aurait déclaré le conteneur malade dès qu'un autre port est imposé —
  soit exactement quand le service va bien mais écoute ailleurs. Elle lit
  désormais `PORT` avec le même repli.
- **`--proxy-headers` et `--forwarded-allow-ips`**, que l'application web
  portait déjà. Sans eux, toute requête paraît venir de l'adresse du proxy ; or
  la limitation de débit se rabat sur l'adresse quand aucune clé de service
  n'est fournie, ce qui est le cas de `/ai/sante`. Le quota de la sonde aurait
  été partagé entre tous les appelants.

---

## 5. Tests en succès

| Cas | Attendu | Obtenu |
|---|---|---|
| `PORT=9123` imposé au conteneur | écoute sur 9123 | **`[demarrage] uvicorn sur 0.0.0.0:9123`**, `/ai/sante` → **200** |
| Aucune variable `PORT` | repli sur 8100 | **`[demarrage] uvicorn sur 0.0.0.0:8100`**, `/ai/sante` → **200** |
| Sonde de vivacité de l'image | `healthy` | **`healthy`** après 45 s |
| Construction de l'image | succès | succès |

Un troisième essai a échoué avant ceux-ci, pour une raison sans rapport :
`DJANGO_SECRET_KEY` absente de l'environnement d'essai. **C'est le
comportement voulu** — un secret manquant interrompt le démarrage au lieu de
basculer sur une valeur de repli (décision 008). Le message nommait la
variable et la commande pour en produire une.

---

## 6. Ce que cet incident ajoute

Les incidents 003 et 007 portaient sur des instruments : une sonde, des tests.
Celui-ci porte sur **le service lui-même**, et il est le premier où la panne
n'a laissé aucune trace dans les journaux du composant en cause — parce qu'il
n'y avait rien à signaler de son point de vue.

**La leçon :** ce qui est libre en développement peut être imposé en
production, et cette asymétrie ne se découvre qu'en déployant. Un port, un
répertoire accessible en écriture, une variable d'environnement absente : trois
choses dont le poste ne dit rien, et dont ce projet a maintenant payé les
trois.

---

## 7. Reste à faire

- **Redéployer le service IA** sur l'image republiée par la chaîne, et repasser
  les sept contrôles de `docker/verifier-deploiement.sh`.
- Vérifier, une fois joignable, que la latence d'embarquement mesurée sur
  `/api/embeddings` se retrouve — ou non — dans le temps de bout en bout d'un
  `POST /ai/recherche` (réserve 7).
