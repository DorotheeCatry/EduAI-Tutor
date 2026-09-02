# Incident 016 — Le service Ollama en boucle de redémarrage, RAG indisponible

> **Numéroté après coup, le 2 septembre.** Ce dossier était le seul du
> répertoire à ne pas porter de numéro. Il prend le suivant disponible plutôt
> que sa place chronologique — 003 en l'occurrence : renuméroter aurait cassé
> toutes les références croisées du dépôt, qui citent les incidents par leur
> numéro. L'ordre du répertoire reste chronologique par le nom de fichier.

**Date de détection :** 28 août 2026, 15 h 50
**Date de début estimée :** 25 août 2026
**Compétence visée :** C21 (épreuve E5) — résolution d'incidents techniques
**Compétences concernées :** C10 (E3), C20 (E5)
**Sévérité :** majeure — fonctionnalité entière indisponible
**État :** **résolu et clos** — voir § 7

---

## 1. Déclenchement

L'incident n'a pas été détecté par une alerte. Il a été découvert **en cherchant
autre chose** : la préparation du protocole de comparaison de modèles (C7)
prévoyait un quatrième modèle servi localement, `qwen3:4b`. La vérification de
sa disponibilité — faite avant d'écrire le protocole, parce qu'un protocole bâti
sur un modèle indisponible ne vaut rien — a montré que le service ne tournait
pas.

C'est le premier fait notable de cet incident : **il durait depuis trois jours et
rien ne l'avait signalé.**

## 2. Périmètre impacté

| Fonction | Effet |
|---|---|
| Recherche RAG | **Indisponible.** Les fonctions d'embarquement appellent Ollama sur le port 11434 ; tous les appels échouaient en `Connection refused` |
| Agents Researcher et Pedagogue | Dégradés — privés de récupération de contexte |
| Repli local des modèles | **Indisponible.** Le projet n'avait aucun recours en cas d'indisponibilité de Groq |
| Benchmark C7 | Un modèle sur quatre non mesurable |
| API données, pipeline, application Django | Non affectés — aucun ne dépend d'Ollama |

Les symptômes étaient visibles depuis lundi sous la forme d'erreurs
`Connection refused` sur le port 11434, attribuées jusque-là à des échecs
ponctuels plutôt qu'à une panne permanente.

## 3. Constat

```
$ systemctl is-active ollama
activating
```

Le service n'était ni actif ni en échec définitif : il était en **boucle de
redémarrage**. Le compteur de tentatives de systemd affichait **12 517**.

Le journal donnait la même ligne à chaque tentative :

```
Error: mkdir /media/apprenant/Stockage: permission denied:
ensure path elements are traversable
```

## 4. Diagnostic — deux défauts, pas un

Le diagnostic initial n'a vu qu'une moitié du problème. **Deux défauts distincts se masquaient l'un l'autre** : tant que le premier empêchait le service de démarrer, le second restait invisible.

### Défaut 1 — le chemin n'était pas traversable

Une surcharge systemd déplaçait le magasin de modèles sur la grande partition :

```
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_MODELS=/media/apprenant/Stockage/ollama_models"
```

Le répertoire cible existait et était accessible en écriture. Le problème était
**au-dessus de lui**, sur le chemin d'accès :

| Chemin | Droits | Propriétaire |
|---|---|---|
| `/media/apprenant` | `drwxr-x---` | `root:root` |
| `/media/apprenant/Stockage` | `drwx------` | `apprenant:apprenant` |
| `/media/apprenant/Stockage/ollama_models` | `drwxrwxr-x` | `apprenant:apprenant` |

Le service tourne sous l'utilisateur système `ollama`, qui n'est ni `root` ni
`apprenant`. Aucun des deux répertoires parents ne lui accorde le bit
d'exécution, c'est-à-dire le droit de **traverser**. La destination était donc
inatteignable alors qu'elle était elle-même parfaitement accessible.

C'est le piège de ce premier diagnostic : vérifier les droits du répertoire
cible ne révèle rien. Sous Unix, l'accès à un chemin exige le droit de traversée
sur **chacun** de ses segments, et un point de montage en `drwx------` bloque
tout utilisateur autre que son propriétaire, quels que soient les droits en
dessous.

### Défaut 2 — la redirection avait déplacé le magasin sans déplacer les données

Une fois le chemin rendu traversable et le service relancé, il démarrait — et ne
servait rien :

```
$ curl -s http://127.0.0.1:11434/api/tags
{"models":[]}
```

La redirection posée le **26 août** avait changé l'adresse du magasin de modèles
sans y transporter son contenu. Le service pointait vers un dossier **créé le
jour même et vide**, tandis que les 3,8 Gio de modèles installés — dont
`mxbai-embed-large`, sur lequel repose tout le RAG — étaient restés à l'ancienne
adresse `/usr/share/ollama/.ollama/models`.

Ce second défaut était **indétectable tant que le premier durait** : un service
qui ne démarre pas ne peut pas révéler que son magasin est vide. C'est ce qui
donne à cet incident sa forme particulière — on croit avoir fini en corrigeant
le défaut visible, et on découvre qu'il en cachait un autre, de nature
différente, sur le même objet.

## 5. Résolution

En deux temps, un par défaut.

**Défaut 1 — rendre le chemin traversable, puis relancer :**

```bash
sudo chmod o+x /media/apprenant /media/apprenant/Stockage
sudo systemctl restart ollama
```

**Défaut 2 — transporter les modèles vers la nouvelle adresse :**

```bash
sudo rsync -a /usr/share/ollama/.ollama/models/ \
              /media/apprenant/Stockage/ollama_models/
sudo rm -rf /usr/share/ollama/.ollama/models
```

Le déplacement plutôt qu'un retéléchargement : les modèles étaient présents et
intacts, les rapatrier coûtait une copie locale au lieu de 3,8 Gio de transfert.
La suppression de l'ancien magasin **a rendu 3,8 Gio à la partition racine**,
qui était à 75 % d'occupation — un effet de bord bienvenu sur une machine où
l'espace racine avait déjà bloqué la construction d'une image Docker.

### Le point qui a coûté du temps

**Le `chmod` seul n'a rien changé.** Les droits étaient corrigés, le chemin était
devenu traversable, et le service continuait d'échouer à l'identique.

Parce qu'un service en boucle de redémarrage **rejoue son ancienne tentative**.
Il ne relit pas l'état du système entre deux essais : il reprend là où il en
était, avec le contexte qu'il avait au démarrage. Tant qu'il n'est pas relancé
explicitement, la correction est appliquée au système mais pas au processus qui
la subit.

C'est une variante du motif que ce projet documente dans ses dossiers d'incident. Les
précédents portaient sur un rapport de succès qui ne correspondait à rien ; ici,
c'est l'inverse et c'est le même mécanisme — **une correction réelle qui ne
produit aucun effet observable**, parce que rien n'a relu l'état corrigé. Dans
les deux cas, l'erreur consiste à croire qu'une action et son effet coïncident
sans l'avoir vérifié.

## 6. Vérification

```
$ systemctl is-active ollama
active
```

Le service démarre et répond sur le port 11434.

## 7. Clôture

```
$ ollama list
qwen3:4b                  2.5 Go
mxbai-embed-large:latest  0.7 Go
qwen3.5:4b                3.4 Go
```

Les trois modèles répondent à la nouvelle adresse. Le RAG dispose de son modèle
d'embarquement, et `qwen3:4b` — le quatrième modèle du protocole de comparaison
C7, resté « non mesuré » faute de service — devient mesurable.

**Incident clos.**

## 8. Ce que cet incident change

**Le repli local n'est pas un confort, c'est le seul recours souverain du
projet.** La comparaison de modèles (C7) a montré que les trois modèles mesurés
envoient tous leurs prompts chez un tiers, alors que ceux de l'agent Coach
contiennent du code d'apprenant. Le seul modèle qui aurait répondu autrement au
critère de souveraineté est précisément celui qui était en panne. Le § 7.8 de
`benchmark_modeles.md` note que la souveraineté est la seule case du tableau
qu'aucune mesure ne remplit — cet incident en est la cause.

**Une panne de trois jours n'a produit aucune alerte.** Le monitorage du projet
observe les appels qui *passent* par LangChain ; il ne surveille pas la
disponibilité des dépendances externes. Un service qui ne démarre pas ne produit
aucun appel, donc aucune trace, donc aucun taux d'erreur — et le silence se
confond avec le calme. C'est le pendant exact de l'incident de la sonde muette :
là, une sonde branchée ne traçait rien ; ici, l'absence de trace ne signale rien.

**Un défaut visible peut en cacher un autre sur le même objet.** C'est
l'enseignement propre à cet incident, et il ne se confond pas avec les
précédents. La permission de traversée et le magasin vide portaient tous deux
sur le magasin de modèles, mais relevaient de causes indépendantes — l'une de
droits Unix, l'autre d'une migration incomplète datant de deux jours plus tôt.
La première empêchait d'observer la seconde. Un incident n'est donc pas clos
quand sa cause identifiée est corrigée : il est clos quand la **fonction** est
vérifiée de bout en bout. Ici, `systemctl is-active` disait `active` alors que
le service ne servait rien ; c'est `ollama list`, qui interroge l'effet et non
l'état, qui l'a montré.

**Piste, non implémentée :** une sonde de disponibilité qui interroge
périodiquement les dépendances externes — Ollama, Groq, PostgreSQL — et consigne
leur état, plutôt que d'attendre qu'un appel échoue pour l'apprendre. Elle n'est
pas écrite ; l'écrire sans mesure de son utilité serait prématuré, mais l'absence
est identifiée.

## 9. Non-régression

Aucun test automatisé ne peut couvrir cet incident : il porte sur la
configuration d'un service système, hors du périmètre du dépôt. Le contrôle
retenu est documentaire — la vérification de disponibilité des modèles figure
désormais dans l'annexe de `docs/benchmark_modeles.md`, avec la commande qui
l'établit, et l'indexation du corpus (`apps/rag/indexation_corpus.py`) échoue
bruyamment plutôt qu'à moitié si le service d'embarquement ne répond pas.
