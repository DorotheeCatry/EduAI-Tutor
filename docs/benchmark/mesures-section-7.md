### 7.1 Latence, en secondes

Mesures relevées par la sonde de monitorage du projet, sur les appels aboutis. Les appels en erreur en sont exclus : la durée d'un refus n'est pas la latence d'un modèle.

| Modèle | Appels retenus | Médiane | 9ᵉ décile | Minimum | Maximum | Écart-type |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | **0,98** | 1,92 | 0,50 | 2,19 | 0,47 |
| `openai/gpt-oss-20b` | 30 | **0,75** | 1,20 | 0,42 | 3,83 | 0,59 |
| `qwen/qwen3.6-27b` | 30 | **1,89** | 2,04 | 1,47 | 2,62 | 0,22 |
| `qwen3:4b` | 30 | **92,76** | 134,34 | 66,97 | 175,58 | 20,73 |

### 7.2 Latence médiane par agent

| Modèle | Pedagogue | Researcher | Coach | Watcher |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 1,16 | 0,95 | 1,00 | 0,95 |
| `openai/gpt-oss-20b` | 0,78 | 0,75 | 1,13 | 0,68 |
| `qwen/qwen3.6-27b` | 1,92 | 1,94 | 1,86 | 1,86 |
| `qwen3:4b` | 92,77 | 98,79 | 92,63 | 123,50 |

### 7.3 Jetons et coût

Jetons **rapportés par le fournisseur**, jamais estimés depuis une longueur de texte.

| Modèle | Jetons d'entrée (moy.) | Jetons de sortie (moy.) | Coût / 1000 requêtes |
|---|---|---|---|
| `openai/gpt-oss-120b` | 153 | 356 | 0,236 $ ⚠ |
| `openai/gpt-oss-20b` | 153 | 416 | 0,140 $ ⚠ |
| `qwen/qwen3.6-27b` | 96 | 768 | 0,480 $ ⚠ |
| `qwen3:4b` | — | — | 0,000 $ |

⚠ **Le tarif n'a pas été confronté à la grille du fournisseur.** Ces montants sont un ordre de grandeur, pas une facture. Voir § 6.

### 7.4 Fiabilité de la campagne

| Modèle | Appels | Succès | Erreurs | Tentatives écartées (quota) | Appels sans trace |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 30 | 0 | 0 | 0 |
| `openai/gpt-oss-20b` | 30 | 30 | 0 | 0 | 0 |
| `qwen/qwen3.6-27b` | 30 | 30 | 0 | 0 | 0 |
| `qwen3:4b` | 30 | 30 | 0 | 0 | 0 |

La colonne « appels sans trace » est le contrôle hérité de l'incident 003 : elle compte les appels pour lesquels la sonde n'a rien écrit sur le disque. Elle est à zéro — chaque appel mesuré a laissé une trace vérifiée.

La colonne « tentatives écartées » compte les appels rejoués après un refus pour quota. Leur latence a été jetée, jamais moyennée : une attente de quota mesure le palier tarifaire du compte, pas le modèle.

### 7.5 Troncature et raisonnement visible

Cette section n'était pas au protocole. Elle a été ajoutée parce que la campagne a mis au jour un fait que les tableaux précédents masquent : **une réponse tronquée y ressemble à une réponse courte.**

| Modèle | Réponses au plafond de jetons | Bloc `<think>` ouvert | …refermé |
|---|---|---|---|
| `openai/gpt-oss-120b` | 1/30 | 0/30 | 0/30 |
| `openai/gpt-oss-20b` | 3/30 | 0/30 | 0/30 |
| `qwen/qwen3.6-27b` | 25/30 | 30/30 | 5/30 |
| `qwen3:4b` | 0/30 | 0/30 | 0/30 |

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
