# Incident 004 — Une protection qui rendait la fonction impossible

**Date :** 29 août 2026
**Composant :** `docker-compose.yml`, service `service_ia`
**Gravité :** bloquante — `/ai/recherche` indisponible depuis le conteneur
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C9 (E2), C10 (E3), C13 (E3)
**Identifiants de corrélation :** `f033fe55185d` (détection), `88ce29eda658`
(reproduction du 29/08)

---

## 1. Déclenchement

Essais du RAG avant mise en ligne. Chaque appel à `/ai/recherche` sur le
service conteneurisé répond **503** avec un identifiant de corrélation, message
générique côté client :

```json
{"detail":"Une dépendance du service est momentanément indisponible.",
 "code":"dependance_indisponible","identifiant_incident":"88ce29eda658"}
```

Le journal du conteneur porte la cause exacte :

```
[88ce29eda658] Dépendance indisponible : Recherche impossible dans le corpus :
error returned from database: (code: 8) attempt to write a readonly database
```

Aucune autre route n'est touchée : `/ai/sante` répond 200, l'authentification
fonctionne, les générations aboutissent. **Seule la recherche documentaire est
morte** — c'est-à-dire tout le RAG.

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| `/ai/recherche` depuis le conteneur | **totalement indisponible** |
| Recherche RAG depuis un processus lancé sur la machine hôte | fonctionnelle |
| Génération de cours, explications, exercices, retours | non touchées |
| Données | **aucune perte** — la base n'a jamais été ouverte |
| Utilisateurs | aucun : le défaut est antérieur à toute mise en ligne |

## 3. Diagnostic

Le message désigne son objet sans détour : une base ouverte en lecture seule,
sur laquelle une écriture est tentée. Restait à comprendre **pourquoi une
lecture écrit**.

Le montage du corpus dans `docker-compose.yml` portait le suffixe `:ro` :

```yaml
- ./apps/rag/chroma:/app/apps/rag/chroma:ro
```

ChromaDB persiste ses données dans SQLite. **SQLite écrit sur son support même
lorsqu'on ne fait que lire** : il ouvre un journal WAL, pose un fichier de
verrous, peut créer des index temporaires. Ces écritures ne sont pas une
conséquence de la requête, elles sont une condition de l'ouverture de la base.
Un support en lecture seule ne permet donc pas d'ouvrir la base **du tout** —
pas seulement d'y écrire.

D'où l'asymétrie constatée : depuis la machine hôte, le même corpus et le même
code fonctionnent, le dossier n'y étant pas monté en lecture seule.

### Pourquoi cela n'avait pas été vu plus tôt

Le montage existait depuis la création du service conteneurisé. Aucune
recherche n'avait été passée **depuis le conteneur** : les vérifications du RAG
avaient toutes été faites sur la machine hôte. C'est le même angle mort que
l'incident 003 — un dispositif éprouvé ailleurs que là où il sert.

## 4. Résolution

Le suffixe `:ro` est retiré du montage du corpus. Celui du monitorage reste
inchangé : il est déjà en écriture, et il doit l'être.

Le compromis est écrit à l'endroit du montage, et non seulement dans le journal
de décisions : c'est le fichier que quelqu'un relira avant de « rétablir » la
protection. Décision `018-corpus-vectoriel-monte-en-ecriture.md`.

## 5. Vérification

Reproduction puis correction, sur le service réellement en fonctionnement :

| Étape | Montage | Appel `/ai/recherche` | Résultat |
|---|---|---|---|
| Avant | `rw=false` | requête « les listes en python » | **503**, `attempt to write a readonly database` |
| Après recréation du conteneur | `rw=true` | même requête | **200**, 5 fragments rendus, extraits pertinents |

`docker inspect` confirme le changement de mode de montage entre les deux
étapes. La vérification n'est pas « le conteneur démarre » mais « la recherche
renvoie des fragments ».

## 6. Ce que l'incident enseigne

**Une protection qui empêche la fonction qu'elle protège n'est pas une
protection sévère : c'est une panne.** Le `:ro` était un bon réflexe — le
service lit, il n'a pas à écrire — appliqué à un moteur dont la lecture écrit.
Le réflexe reste bon ; c'est sa vérification qui manquait.

Et il faut le dire dans l'autre sens aussi : **retirer le `:ro` retire une
garantie réelle**, celle qu'aucune régression ne puisse altérer le corpus. Ce
n'est pas un faux problème réglé, c'est un risque désormais assumé, borné par
le fait que le corpus est reconstructible, sans donnée personnelle, et sans
route d'écriture exposée. La solution qui rendrait la garantie — ChromaDB en
service distinct — est identifiée, chiffrée en travail, et remise à après la
soutenance.
