# Incident — le service Ollama en boucle de redémarrage, RAG indisponible

**Date de détection :** 28 août 2026, 15 h 50
**Date de début estimée :** 25 août 2026
**Compétence visée :** C21 (épreuve E5) — résolution d'incidents techniques
**Compétences concernées :** C10 (E3), C20 (E5)
**Sévérité :** majeure — fonctionnalité entière indisponible
**État :** résolu partiellement, voir § 7

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

## 4. Diagnostic

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

C'est le piège de ce diagnostic : vérifier les droits du répertoire cible ne
révèle rien. Sous Unix, l'accès à un chemin exige le droit de traversée sur
**chacun** de ses segments, et un point de montage en `drwx------` bloque tout
utilisateur autre que son propriétaire, quels que soient les droits en dessous.

## 5. Résolution

```bash
sudo chmod o+x /media/apprenant /media/apprenant/Stockage
sudo systemctl restart ollama
```

### Le point qui a coûté du temps

**Le `chmod` seul n'a rien changé.** Les droits étaient corrigés, le chemin était
devenu traversable, et le service continuait d'échouer à l'identique.

Parce qu'un service en boucle de redémarrage **rejoue son ancienne tentative**.
Il ne relit pas l'état du système entre deux essais : il reprend là où il en
était, avec le contexte qu'il avait au démarrage. Tant qu'il n'est pas relancé
explicitement, la correction est appliquée au système mais pas au processus qui
la subit.

C'est une variante du motif que ce projet documente depuis huit incidents. Les
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

## 7. Ce qui n'est pas résolu

**Le magasin de modèles est vide.**

```
$ curl -s http://127.0.0.1:11434/api/tags
{"models":[]}
```

La surcharge ayant été conservée, le service utilise désormais le répertoire de
la grande partition — qui n'a jamais servi. Les modèles installés vivent à
l'ancien emplacement, `/usr/share/ollama/.ollama/models`, où ils occupent
3,8 Gio : `mxbai-embed-large`, nécessaire au RAG, et `qwen3.5`.

Le service démarre donc, et ne sert rien. **Le RAG reste indisponible tant que
`mxbai-embed-large` n'est pas présent au nouvel emplacement.**

Deux voies, l'une et l'autre acceptables :

1. Retélécharger les modèles à la nouvelle adresse — `ollama pull
   mxbai-embed-large`, puis `ollama pull qwen3:4b` pour le benchmark. Simple, et
   coûte environ 3 Gio de transfert.
2. Recopier l'ancien magasin vers le nouveau. Plus rapide, mais demande des
   privilèges : le répertoire de destination appartient à `ollama`.

Un téléchargement était en cours au moment de la rédaction — 907 Mio déjà
présents à la nouvelle adresse.

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
