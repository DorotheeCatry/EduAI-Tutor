# Incident 003 — L'instrument de mesure en panne silencieuse

**Date :** 27–28 août 2026
**Composant :** `apps/monitoring/sondes.py`
**Gravité :** majeure — aucune trace produite en conditions réelles, sans le moindre signal
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C20 (E5) — monitorage ; C9 (E2) ; C10 (E3)

---

## 1. Déclenchement

**27/08, 15:19.** Mise en service du monitorage du service IA. La sonde
s'annonce branchée, écrit un événement de démarrage, et les vérifications
passent : un appel Groq réel est tracé avec ses 86 jetons d'entrée, un modèle
inexistant est tracé avec son code de retour 404.

**27/08, 18:53.** Le serveur Django est lancé pour que les traces s'accumulent.
Il journalise `[monitorage] sonde branchée`.

**28/08, 15:40.** Écriture de l'API du service IA. La consigne était explicite :
*« vérifier que le point d'accroche LangChain fonctionne aussi dans le processus
FastAPI »*. Un appel à `/ai/recherche` est passé, il échoue — Ollama est arrêté —
et l'API répond correctement 503 avec un identifiant de corrélation.

**Le journal de monitorage ne contient rien.**

Ni l'erreur, ni la recherche, ni la latence. Le fichier porte l'événement de
démarrage du service, écrit une seconde plus tôt par le même processus. La sonde
écrivait donc bien — mais elle ne recevait aucun rappel.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Service IA (FastAPI) | Aucun appel tracé, depuis sa création |
| **Serveur Django** | **Aucun appel de requête tracé, depuis le 27/08 18:53** |
| Scripts et ligne de commande | Tracés correctement, du début à la fin |
| Métriques Prometheus | Alimentées par les mêmes rappels : vides elles aussi |
| Tableau de bord Grafana | Affichait la seule santé du journal, aucune série d'appel |
| Données perdues | **22 heures de traces d'exploitation**, non rattrapables |
| Service rendu aux utilisateurs | **Aucun impact.** L'application fonctionnait normalement |

**C'est l'instrument de mesure qui était en panne, pas ce qu'il mesurait.**

Et il l'était de la pire manière : en se déclarant opérationnel. Le journal du
serveur affichait `[monitorage] sonde branchée`, le point de terminaison
`/metrics` répondait, le tableau de bord s'affichait. Tout indiquait un
monitorage en fonctionnement.

---

## 3. Diagnostic

### 3.1 Écarter les causes évidentes

- **La sonde n'écrit pas ?** Non : l'événement de démarrage du service, écrit
  par le même processus une seconde plus tôt, était bien présent.
- **Le point d'accroche n'est pas installé ?** Non : `installer()` renvoyait
  `True` et journalisait son succès.
- **Le rappel n'existe pas pour ce type d'appel ?** Non : le même code traçait
  parfaitement les recherches lancées depuis un script.

### 3.2 La différence entre ce qui marchait et ce qui ne marchait pas

| Contexte | Traces produites |
|---|---|
| Script `uv run python -c ...` | **oui** |
| Requête HTTP au service FastAPI | **non** |
| Requête HTTP au serveur Django | **non** |

Le partage n'est pas entre les frameworks : il est entre **le fil d'exécution
qui a démarré le programme** et **celui qui traite une requête**.

### 3.3 Cause racine

`installer()` posait la sonde ainsi :

```python
register_configure_hook(_sonde_active, inheritable=True)
_sonde_active.set(sonde)          # ← la faute
```

`_sonde_active` est une `ContextVar`. Une valeur posée par `set()` n'est visible
que **dans le contexte qui l'a posée et dans ceux qui en dérivent**.

Or :

- sous FastAPI, chaque requête s'exécute dans **sa propre tâche asyncio** ;
- sous WSGI, chaque requête s'exécute dans **son propre fil**, qui démarre avec
  un contexte vide ;
- un script, lui, exécute tout dans le contexte où l'import a eu lieu.

**Aucune requête n'héritait du contexte du démarrage.** LangChain consultait la
variable, y trouvait `None`, et n'attachait aucun rappel. La sonde était
installée, joignable, fonctionnelle — et jamais sollicitée.

### 3.4 Pourquoi les vérifications précédentes ne l'ont pas vu

**Elles tournaient toutes dans des scripts.** L'appel Groq de contrôle, le
modèle inexistant, la recherche RAG en erreur : trois vérifications, trois
processus dont le contexte était celui de l'import. Les trois passaient.

C'est l'angle mort exact : **on avait vérifié que la sonde fonctionne, jamais
qu'elle fonctionne là où le service tourne.**

---

## 4. Résolution

La sonde devient la **valeur par défaut** de la variable de contexte, au lieu
d'y être posée :

```python
_sonde_active: ContextVar[SondeServiceIA | None] = ContextVar(
    "sonde_monitorage", default=sonde,
)
```

Une valeur par défaut est lue par **tout** contexte, quel qu'en soit le fil ou la
tâche — elle n'a pas à être héritée puisqu'elle n'appartient à personne.

L'appel `set()` est supprimé, avec un commentaire qui dit pourquoi il ne doit pas
revenir.

---

## 5. Tests en succès

| Test | Attendu | Obtenu |
|---|---|---|
| Appel `/ai/recherche` depuis FastAPI | un événement au journal | **`recherche_rag`, agent `researcher`, latence 0,0095 s, `ValueError`** |
| Journal avant / après l'appel | une ligne de plus | 5 → 6 |
| Événement de démarrage | toujours écrit | oui |
| Échecs de la sonde | aucun | 0 |

Le même correctif répare le serveur Django : la cause était commune, la
correction l'est aussi.

---

## 6. Ce que cet incident ajoute aux précédents

C'est la **variante la plus retorse** du motif que ce projet documente depuis six
jours.

| Incident | Ce qui mentait |
|---|---|
| S1, 26/08 | un extracteur : « succès » à zéro enregistrement |
| Chargeur, 27/08 | un chargeur : 6 836 documents sur une base vide |
| Rapport S5, 27/08 | un rapport de mesure, écrasé par une exécution partielle |
| API `/sources/`, 27/08 | un décompte supérieur au corpus réel |
| Source de données Grafana, 27/08 | un tableau de bord provisionné qui n'aurait rien affiché |
| Conversion Spark, 28/08 | rien — la conception était en cause, pas la mesure |
| **Sonde, 28/08** | **l'instrument de mesure lui-même** |

Les cinq premiers étaient détectables **parce qu'on mesurait**. Celui-ci ne
l'était pas : c'est l'appareil de mesure qui était en panne, et un appareil en
panne ne signale pas sa propre panne.

**La leçon, et elle est générale :** un instrument doit être éprouvé **dans les
conditions où il servira**, pas dans celles où il est commode de le tester. Une
sonde vérifiée en script et déployée dans un serveur n'a pas été vérifiée.

**Une conséquence concrète est déjà en place.** Le monitorage compte séparément
les événements *émis* et les lignes *réellement écrites*, et le tableau de bord
trace leur écart. Mais ce contrôle-là n'aurait rien vu ici : les deux compteurs
étaient cohérents, à zéro. Il manque un indicateur d'**absence de trafic tracé
alors que le service reçoit des requêtes** — deux mesures qui ne se rencontrent
pas aujourd'hui, le service ne journalisant pas ses appels reçus.

---

## 7. Reste à faire

- **Compter les appels reçus par les API**, et pas seulement les appels sortants
  vers le fournisseur. Leur écart avec les traces produites détecterait cette
  panne. Aujourd'hui, un service qui reçoit du trafic sans rien tracer est
  indiscernable d'un service au repos.
- **Éprouver la sonde depuis un serveur** dans la suite de tests à venir (C18),
  et non depuis un script : c'est précisément la condition qui manquait.
