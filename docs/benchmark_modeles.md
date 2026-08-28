# Comparaison de services d'IA — protocole, mesures et décision

**Date de rédaction du protocole :** 28 août 2026
**Compétence visée :** C7 (épreuve E2) — comparaison de services d'intelligence artificielle
**Compétences concernées :** C6 (E2) — veille ; C10 (E3) — intégration du modèle ; C20 (E5)

---

> **Ce document est écrit et commité AVANT toute mesure.**
>
> Les critères, leur pondération et la grille de notation qui suivent sont fixés
> sans connaître les résultats. C'est la seule manière d'éviter le travers le
> plus courant de ce genre d'exercice : choisir après coup les critères qui
> désignent le modèle qu'on avait envie de retenir.
>
> Les sections 1 à 6 ont été commitées seules, sans les sections « Mesures » et
> « Décision », qui étaient alors vides. L'historique Git en fait foi : le
> commit `8cb868f` ajoute ce document sans un seul chiffre de mesure. Les mesures
> sont arrivées ensuite, dans un commit distinct.
>
> Une seule chose a été ajoutée après coup : le § 7.5, sur la troncature. Il
> DÉCRIT les données — il ne modifie aucun critère de décision, et il le dit.

---

## 1. Question posée

Quel modèle affecter à chacun des quatre agents d'EduAI Tutor — Researcher,
Pedagogue, Coach, Watcher — sachant que leurs besoins diffèrent ?

Le routage actuel, acté en décision 001, a été décidé sur des considérations
générales de qualité et de latence, **sans mesure**. Ce document a pour objet de
le confirmer ou de le corriger sur des données.

## 2. Modèles comparés

| Identifiant | Fournisseur | Rôle dans la comparaison |
|---|---|---|
| `openai/gpt-oss-120b` | Groq | Modèle de qualité, routage actuel de Researcher et Pedagogue |
| `openai/gpt-oss-20b` | Groq | Modèle rapide, routage actuel de Coach et Watcher |
| `qwen/qwen3.6-27b` | Groq | Famille distincte — contrôle que le résultat ne tient pas au seul fournisseur d'origine |
| `qwen3:4b` | Ollama, local | Repli souverain, exécuté sur la machine |

Le quatrième n'est pas un concurrent des trois autres : il est **quatre à trente
fois plus petit**. Il est présent pour répondre à une question distincte — que
perd-on en repassant en local ? — et il serait malhonnête de le noter sur la
même échelle sans le dire.

## 3. Critères, fixés avant mesure

Six critères, dont quatre se mesurent et deux se constatent.

| # | Critère | Nature | Comment il est établi |
|---|---|---|---|
| 1 | **Latence** | mesuré | Médiane et neuvième décile des durées d'appel, relevés dans le journal de monitorage |
| 2 | **Jetons consommés** | mesuré | Jetons d'entrée et de sortie tels que **rapportés par le fournisseur**, jamais estimés depuis une longueur de texte |
| 3 | **Coût pour mille requêtes** | mesuré | Jetons moyens × tarif du fournisseur. Voir § 6 sur la fiabilité des tarifs |
| 4 | **Qualité pédagogique** | **noté à la main** | Grille du § 5, appliquée en aveugle par l'autrice du projet |
| 5 | **Souveraineté des données** | constaté | Le prompt sort-il de la machine ? Quelles conditions le fournisseur impose-t-il ? |
| 6 | **Disponibilité tarifaire** | constaté | Le modèle est-il accessible au projet, et à quelles limites de débit ? |

### Pourquoi pas de note globale pondérée

Aucune pondération n'est fixée, et c'est délibéré. Agréger six critères
hétérogènes en un score unique donnerait un classement d'apparence objective
dont le résultat dépendrait entièrement de coefficients choisis par le
rédacteur. La décision du § 8 nommera les critères qui l'ont emportée, agent par
agent, plutôt qu'un chiffre.

## 4. Protocole de mesure

**Dix prompts**, représentatifs des quatre agents du projet :

| Agent | Nombre | Nature |
|---|---|---|
| Pedagogue | 3 | Génération de cours, réexplication adaptée, reformulation pour débutant |
| Researcher | 2 | Synthèse à partir de fragments, réponse à une question technique |
| Coach | 3 | Retour sur du code fautif, génération d'exercice, correction d'erreur |
| Watcher | 2 | Classification d'une méprise, détection de type d'erreur |

**Quatre modèles × dix prompts × trois répétitions = 120 appels.**

Les trois répétitions ne servent pas à moyenner la qualité — un modèle ne change
pas d'avis — mais à **mesurer la dispersion de la latence**, comme cela a été
fait pour la conversion Spark. Une latence médiane sans dispersion ne dit pas si
le service est régulier ou erratique.

**Paramètres tenus constants** : même prompt au caractère près, même température,
même plafond de jetons de sortie, appels séquentiels et non concurrents. Deux
mesures ne se comparent que si elles ont subi les mêmes conditions.

**Instrumentation** : aucune n'est écrite pour ce benchmark. Le monitorage du
projet trace déjà agent, modèle, latence, jetons et coût estimé pour tout appel
passant par LangChain. Le benchmark fournit un protocole et une lecture des
traces, pas une sonde de plus.

## 5. Grille de notation de la qualité

**La qualité n'est pas mesurée automatiquement.** Un modèle juge d'autres
modèles avec des biais connus — préférence pour les réponses longues, pour son
propre style, pour la famille dont il est issu — et aucun de ces biais ne serait
défendable devant un jury. Les réponses sont donc notées à la main.

Le tableau des réponses est produit **côte à côte, sans indiquer quel modèle a
produit quoi** : la notation est faite en aveugle, puis les identités révélées.

Cinq axes, notés de 0 à 3 :

| Axe | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Exactitude technique** | erreurs factuelles | approximations | correct | correct et précis |
| **Adaptation au niveau** | hors sujet pour le niveau visé | inégale | adaptée | adaptée et explicitement graduée |
| **Utilité de l'exemple** | aucun exemple | exemple décoratif | exemple pertinent | exemple exécutable et commenté |
| **Concision** | délayé au point de nuire | verbeux | juste | dense sans être elliptique |
| **Respect du format demandé** | format ignoré | format approximatif | format respecté | format respecté et exploitable tel quel |

Note maximale : 15 par réponse.

**Les cinq axes ne sont pas pondérés entre eux** — même raison qu'au § 3.

## 6. Réserve sur les tarifs

Les tarifs de `apps/monitoring/tarifs.json` portent tous
`"a_verifier": true` : **ils n'ont pas été confrontés à la grille du
fournisseur.** Tout coût calculé à partir d'eux est un ordre de grandeur, et les
mesures le signalent explicitement.

Cette vérification demande un accès à la console Groq, qui n'est pas
programmatique. Elle relève de l'autrice du projet. Tant qu'elle n'est pas
faite, le critère 3 est établi **en jetons**, qui sont mesurés, et non en
monnaie, qui est déduite.

Un coût plausible et faux serait pire qu'un coût absent : c'est le motif que ce
projet documente dans ses dossiers d'incident.

## 7. Mesures

Campagne du 28 août 2026, 16 h 09 à 16 h 21 (UTC+2). **90 appels sur les 120
prévus** : les trois modèles Groq ont été mesurés, le quatrième ne l'a pas été
— voir l'annexe. 90 succès, 0 erreur, 0 tentative écartée pour quota.

Les mesures brutes sont dans `benchmark/mesures.jsonl`, les réponses dans
`benchmark/reponses.jsonl` : les tableaux ci-dessous se recalculent avec
`uv run python -m benchmark.analyser`, ils ne sont pas recopiés à la main.

### 7.1 Latence, en secondes

Mesures relevées par la sonde de monitorage du projet, sur les appels aboutis. Les appels en erreur en sont exclus : la durée d'un refus n'est pas la latence d'un modèle.

| Modèle | Appels retenus | Médiane | 9ᵉ décile | Minimum | Maximum | Écart-type |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | **0,98** | 1,92 | 0,50 | 2,19 | 0,47 |
| `openai/gpt-oss-20b` | 30 | **0,75** | 1,20 | 0,42 | 3,83 | 0,59 |
| `qwen/qwen3.6-27b` | 30 | **1,89** | 2,04 | 1,47 | 2,62 | 0,22 |
| `qwen3:4b` | 0 | **non mesuré** | — | — | — | — |

### 7.2 Latence médiane par agent

| Modèle | Pedagogue | Researcher | Coach | Watcher |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 1,16 | 0,95 | 1,00 | 0,95 |
| `openai/gpt-oss-20b` | 0,78 | 0,75 | 1,13 | 0,68 |
| `qwen/qwen3.6-27b` | 1,92 | 1,94 | 1,86 | 1,86 |
| `qwen3:4b` | non mesuré | non mesuré | non mesuré | non mesuré |

### 7.3 Jetons et coût

Jetons **rapportés par le fournisseur**, jamais estimés depuis une longueur de texte.

| Modèle | Jetons d'entrée (moy.) | Jetons de sortie (moy.) | Coût / 1000 requêtes |
|---|---|---|---|
| `openai/gpt-oss-120b` | 153 | 356 | 0,236 $ ⚠ |
| `openai/gpt-oss-20b` | 153 | 416 | 0,140 $ ⚠ |
| `qwen/qwen3.6-27b` | 96 | 768 | 0,480 $ ⚠ |
| `qwen3:4b` | non mesuré | non mesuré | non mesuré |

⚠ **Le tarif n'a pas été confronté à la grille du fournisseur.** Ces montants sont un ordre de grandeur, pas une facture. Voir § 6.

### 7.4 Fiabilité de la campagne

| Modèle | Appels | Succès | Erreurs | Tentatives écartées (quota) | Appels sans trace |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 30 | 0 | 0 | 0 |
| `openai/gpt-oss-20b` | 30 | 30 | 0 | 0 | 0 |
| `qwen/qwen3.6-27b` | 30 | 30 | 0 | 0 | 0 |
| `qwen3:4b` | 0 | 0 | 0 | 0 | — |

La colonne « appels sans trace » est le contrôle hérité de l'incident 003 : elle compte les appels pour lesquels la sonde n'a rien écrit sur le disque. Elle est à zéro — chaque appel mesuré a laissé une trace vérifiée.

La colonne « tentatives écartées » compte les appels rejoués après un refus pour quota. Leur latence a été jetée, jamais moyennée : une attente de quota mesure le palier tarifaire du compte, pas le modèle.

### 7.5 Troncature et raisonnement visible

Cette section n'était pas au protocole. Elle a été ajoutée parce que la campagne a mis au jour un fait que les tableaux précédents masquent : **une réponse tronquée y ressemble à une réponse courte.**

| Modèle | Réponses au plafond de jetons | Bloc `<think>` ouvert | …refermé |
|---|---|---|---|
| `openai/gpt-oss-120b` | 1/30 | 0/30 | 0/30 |
| `openai/gpt-oss-20b` | 3/30 | 0/30 | 0/30 |
| `qwen/qwen3.6-27b` | 25/30 | 30/30 | 5/30 |

### 7.6 Mesure complémentaire — hors protocole

La campagne principale imposait un plafond de 800 jetons à tous les modèles. Sous ce plafond, `qwen/qwen3.6-27b` rendait des réponses tronquées : la question se posait de savoir si l'on mesurait le modèle ou la contrainte.

Une mesure a donc été refaite pour ce seul modèle, à 4000 jetons, sur les dix prompts, une répétition. **Elle ne figure pas dans les tableaux précédents et ne s'y compare pas** : ses paramètres diffèrent. Elle répond à une question distincte — le modèle est-il handicapé par le plafond, ou par lui-même ?

| Grandeur | Protocole (800 jetons) | Complément (4000 jetons) |
|---|---|---|
| Latence médiane | 1,89 s | 4,31 s |
| Jetons de sortie (moy.) | 768 | 2052 |
| Coût / 1000 requêtes | 0,480 $ ⚠ | 1,250 $ ⚠ |
| Bloc de raisonnement refermé | 5/30 | 10/10 |

**Réponse : par lui-même.** Le plafond relevé, le modèle répond correctement aux dix prompts, classification comprise. Mais il consomme alors en moyenne 2052 jetons de sortie là où les deux autres en consomment moins de 416, pour des réponses de longueur comparable : l'écart est du raisonnement visible, pas du contenu rendu à l'utilisateur. Le surcoût et la latence supplémentaire sont donc une propriété du modèle, non un artefact du protocole.

C'est le point qui rend la comparaison défendable. Sans cette mesure, on aurait écarté un modèle sur un plafond qu'on lui avait soi-même imposé — un raisonnement circulaire qu'un jury aurait relevé.

### 7.7 Ce que la cadence a appris sur la disponibilité — critère 6

Un premier essai, à 0,5 seconde entre deux appels, a produit trois refus 429 sur
les trois derniers des dix appels. À 6 secondes, les 90 appels de la campagne
sont passés sans un seul refus.

Ce chiffre n'est pas anecdotique, c'est le critère 6 : le palier gratuit tient
environ **dix appels par minute** sur ce jeu de prompts. Pour une classe de
trente apprenants travaillant en même temps, ce palier ne suffit pas — la
question du passage à un palier payant se pose avant celle du choix du modèle.

Il a aussi fallu **désactiver les tentatives automatiques du client** pour
mesurer quoi que ce soit. Le client Groq réessaie de lui-même après un refus, et
son attente tombe à l'intérieur de l'appel chronométré : un appel a été relevé à
5,99 secondes alors que le modèle n'en avait consommé qu'une fraction. Sans
`max_retries=0`, la campagne aurait décrit le palier tarifaire du compte en
croyant décrire les modèles.

### 7.8 Critère 5 — souveraineté des données

Ce critère ne se mesure pas, il se constate, et le constat est le même pour les
trois modèles mesurés : **le prompt sort de la machine.** Il part chez Groq, aux
conditions de service de Groq.

Ce n'est pas neutre pour ce projet. Les prompts de l'agent Coach contiennent du
code d'apprenant, c'est-à-dire une production personnelle rattachable à une
personne identifiée — le point traité au § 5 de `rgpd_eduai_data.md`. La sonde
de monitorage ne conserve d'ailleurs que la LONGUEUR des prompts, jamais leur
contenu, précisément pour cette raison.

Le seul modèle qui aurait répondu autrement à ce critère est celui qui n'a pas
pu être mesuré. **La souveraineté est donc, aujourd'hui, la case vide du
tableau** — et c'est la seule des six qu'aucune mesure ne vient remplir.

## 8. Décision

### Ce qui est acquis sur les critères mesurés

`qwen/qwen3.6-27b` **est écarté.** Il est deux fois plus lent que `gpt-oss-120b`
sous plafond identique, quatre fois plus lent une fois le plafond levé, et
coûte de deux à cinq fois plus cher pour un contenu rendu de longueur
comparable. L'écart est du raisonnement visible : le modèle facture et fait
attendre pour un texte que l'utilisateur ne lit pas. Le § 7.6 établit que ce
n'est pas un effet du protocole.

Le routage acté en décision 001 **est confirmé** sur les critères mesurés :

| Agent | Modèle retenu | Critères qui l'emportent |
|---|---|---|
| Researcher | `openai/gpt-oss-120b` | Jetons de sortie les plus bas (356) pour la tâche la plus exigeante ; latence médiane sous la seconde |
| Pedagogue | `openai/gpt-oss-120b` | Même raison ; la génération de cours est la tâche où la qualité prime et où l'écart de latence de 0,23 s ne se voit pas |
| Coach | `openai/gpt-oss-20b` | Latence médiane de 0,75 s : le retour sur code est interactif, c'est là que la latence se ressent |
| Watcher | `openai/gpt-oss-20b` | Latence la plus basse (0,68 s sur ses prompts) et coût le plus bas ; la classification n'appelle pas le modèle le plus fort |

Un point mérite d'être relevé parce qu'il contredit l'intuition : **`gpt-oss-120b`
consomme MOINS de jetons de sortie que `gpt-oss-20b`** — 356 contre 416 en
moyenne. Le modèle le plus gros est le plus concis. Son coût pour mille
requêtes reste supérieur (0,236 $ contre 0,140 $) parce que son tarif au jeton
est plus élevé, mais l'écart est bien moindre que le rapport des tailles ne le
laissait attendre. C'est exactement le genre de fait qu'une décision prise sans
mesure ne pouvait pas connaître.

### Ce qui reste ouvert

**Le critère 4, la qualité pédagogique, n'est pas tranché.** La notation en
aveugle est préparée dans `benchmark/notation-aveugle.md` et attend d'être
remplie à la main. Elle est la seule chose qui pourrait déplacer la décision, et
d'une seule manière : si `gpt-oss-20b` se révélait nettement plus faible que
`gpt-oss-120b` sur les trois prompts de l'agent Coach — le retour sur code
fautif est la tâche la plus délicate du jeu — l'écart de coût, 0,10 $ pour mille
requêtes, ne justifierait pas de conserver le modèle rapide. Coach passerait
alors sur `gpt-oss-120b`, et Watcher resterait sur le modèle rapide.

**Le critère 5, la souveraineté, n'est pas tranché non plus**, faute d'un modèle
local en état de marche. Tant que le service Ollama ne démarre pas, le projet n'a
aucun repli si Groq devient indisponible ou si une contrainte interdit la sortie
du code des apprenants. Ce n'est pas un manque de confort : c'est le seul risque
de cette comparaison qui puisse arrêter le service.

### Réserve sur les coûts

Tous les montants de ce document portent ⚠ et restent **des ordres de grandeur**.
La table `apps/monitoring/tarifs.json` n'a pas été confrontée à la grille du
fournisseur ; elle ne peut l'être que depuis la console Groq, hors d'atteinte
d'un script. Tant que les entrées portent `"a_verifier": true`, le classement
par coût vaut par ses RAPPORTS, non par ses valeurs absolues — et si les tarifs
relevés changeaient les rapports, la décision serait à revoir.

---

## Annexe — état des services

| Modèle | État | Détail |
|---|---|---|
| `openai/gpt-oss-120b` | disponible | vérifié sur `/v1/models` |
| `openai/gpt-oss-20b` | disponible | vérifié sur `/v1/models` |
| `qwen/qwen3.6-27b` | disponible | vérifié sur `/v1/models` |
| `qwen3:4b` | **indisponible** | service Ollama en échec de démarrage, voir ci-dessous |

**Le service Ollama est en boucle de redémarrage — 12 517 tentatives.** Sa
surcharge systemd le pointe vers `/media/apprenant/Stockage/ollama_models`,
répertoire situé sous un point de montage dont les droits sont `drwx------
apprenant:apprenant`. L'utilisateur système `ollama` ne peut pas le traverser :

```
Error: mkdir /media/apprenant/Stockage: permission denied
```

C'est la même cause qui faisait échouer les recherches RAG toute la semaine —
les fonctions d'embedding appellent Ollama sur le port 11434.

Le correctif demande des privilèges. Le plus simple est de rendre au service son
emplacement par défaut, où deux modèles sont déjà installés :

```bash
sudo rm /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama
ollama pull qwen3:4b        # seul qwen3.5 est présent aujourd'hui
```

Le correctif n'ayant pas pu être appliqué avant la campagne, le quatrième modèle
est resté **non mesuré**. Les tableaux du § 7 portent la mention plutôt qu'une
case vide : une case vide se lit comme un oubli, une mention se lit comme un
fait. Une fois le service rétabli, la colonne se complète sans rejouer le reste :

```bash
uv run python -m benchmark.executer --modeles qwen3:4b
uv run python -m benchmark.analyser
```
