# Incident 001 — Chargement annoncé réussi sur une base restée vide

**Date :** 27 août 2026
**Composant :** `data_pipeline/load/chargeur.py`
**Gravité :** majeure — perte totale du résultat, sans aucun signal
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C4 (E1), C20 (E5)

---

## 1. Déclenchement

**27/08/2026, 15:42.** Premier lancement du chargeur sur le corpus transformé,
6 836 documents, après complétion des nomenclatures.

Le programme se termine normalement, code de sortie 0, et journalise :

```
15:42:58 INFO  Bilan — 6836 documents lus, 6836 chargés, 1211 mots-clés,
                20544 rattachements, 0 rejets, 50.11 s
```

Aucun avertissement, aucune exception, cinquante secondes de travail effectif.
Le rapport de chargement est écrit sur disque avec ces mêmes chiffres.

Le contrôle de vérification, exécuté immédiatement après depuis `psql`, donne :

```
 description | 0     document_big_data     | 0
 document    | 0     document_fichier      | 0
 mot_cle     | 0     document_api_rest     | 0
```

**Huit tables à zéro.** Le chargeur affirmait avoir écrit 6 836 documents,
1 211 mots-clés et 20 544 rattachements. La base n'en contenait aucun.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Base `eduai_data` | Aucune écriture. Base restée dans son état initial. |
| Base `eduai_app` | Aucun. Le chargeur ne s'y connecte pas. |
| Application Django | Aucun. Elle ne lit pas `eduai_data`. |
| Corpus transformé | Intact. Le chargeur est en lecture seule sur `corpus.jsonl`. |
| Données perdues | **Aucune.** L'incident est une non-écriture, pas une destruction. |
| Données personnelles | Aucune en cause. `eduai_data` n'en contient pas. |
| Pipeline aval | Le vector store n'aurait rien eu à indexer. |

**La gravité ne tient pas aux dégâts mais au silence.** Un échec bruyant aurait
coûté cinq minutes. Ici, le seul indicateur disponible — le bilan du programme —
affirmait le contraire de la réalité. Sans le contrôle en base, l'erreur serait
passée, et le pipeline aurait été déclaré terminé sur une base vide.

---

## 3. Diagnostic

Cinq étapes, de l'hypothèse la plus probable à la cause réelle.

### 3.1 Vérifier que le symptôme est réel

Deuxième requête depuis `psql`, tables comptées une à une : confirmé, tout est à
zéro. Le symptôme n'est pas un artefact d'affichage.

### 3.2 Écarter l'erreur de cible

Hypothèse : le chargeur écrit dans une autre base. **Écartée.** Le journal
indique `eduai_data`, et surtout la lecture des nomenclatures a retourné
6 licences et 5 sources — tables qui n'existent que dans `eduai_data`. Le
chargeur était bien connecté à la bonne base.

### 3.3 Écarter la défaillance du pilote

Hypothèse : `connexion.transaction()` de psycopg ne valide pas. Test isolé :
une connexion neuve, un `INSERT` dans un bloc `with cx.transaction():`, puis
lecture depuis une seconde connexion. **La ligne est visible.** Le mécanisme
fonctionne — l'anomalie vient de son usage, pas du pilote.

### 3.4 Instrumenter pour localiser la perte

Exécution du chargeur avec observation de part et d'autre du bloc de
chargement :

```
AVANT                    : ('eduai_data', 0)
APRÈS, même connexion    : ('eduai_data', 6836)
transaction ouverte ?    : True
statut transaction       : 2   (INTRANS)
APRÈS, autre connexion   : 0
```

Le diagnostic est là. Les écritures existent, elles sont visibles **dans la
transaction du chargeur** et nulle part ailleurs. La transaction n'a jamais été
validée. La fermeture de la connexion l'a annulée.

### 3.5 Cause racine

`initialiser()` appelle `_lire_nomenclatures()`, qui exécute deux `SELECT`.
psycopg n'étant pas en mode `autocommit`, **ces lectures ouvrent une
transaction implicite** qui reste ouverte.

Lorsque `charger()` entre ensuite dans `with self.connexion.transaction():`,
psycopg constate qu'une transaction est déjà en cours. Le gestionnaire de
contexte ne peut donc pas ouvrir un bloc de premier niveau : il pose un **point
de reprise** (`SAVEPOINT`). À la sortie du bloc, il libère le point de reprise —
et ne valide rien, puisqu'il n'est pas propriétaire de la transaction englobante.

Le chargeur voyait donc ses propres écritures, les comptait honnêtement, et
rendait un bilan exact du point de vue de sa transaction. `close()` a ensuite
annulé l'ensemble.

Le défaut ne se manifeste que si une requête a été exécutée avant le bloc de
chargement. C'est précisément ce qu'ajoutait la lecture des nomenclatures,
introduite pour une bonne raison — vérifier les licences avant d'insérer — et
dont l'effet de bord transactionnel n'était pas visible.

---

## 4. Résolution

Deux corrections, dont une seule était strictement nécessaire.

### 4.1 Corriger la cause

Clore explicitement la transaction implicite à la fin de la lecture des
nomenclatures. Ces `SELECT` n'ayant rien écrit, `rollback()` est le geste juste :

```python
# `connexion.transaction()` ne valide QUE s'il est le bloc le plus externe.
# Laissée ouverte, la transaction implicite ferait de lui un simple point de
# reprise : le chargement paraîtrait réussir et la fermeture annulerait tout.
self.connexion.rollback()
```

### 4.2 Rendre le défaut bruyant s'il revient

La correction ci-dessus supprime l'occurrence connue. Elle ne protège pas d'une
occurrence future : toute requête ajoutée un jour entre l'initialisation et le
chargement rouvrirait une transaction implicite et ramènerait le même silence.

Contrôle explicite du statut transactionnel à la sortie du bloc :

```python
statut = self.connexion.info.transaction_status
if statut != psycopg.pq.TransactionStatus.IDLE:
    raise RuntimeError(
        "La transaction de chargement n'a pas été validée "
        f"(statut {statut!r}). Aucune donnée n'a été écrite. "
        "Une transaction implicite englobait le bloc de chargement."
    )
```

Le mode de défaillance passe de « bilan flatteur, base vide, code 0 » à
« exception nommée, message explicite, code de sortie non nul ».

---

## 5. Tests en succès

| Test | Attendu | Obtenu |
|---|---|---|
| Rechargement après correctif | documents visibles depuis une autre connexion | **6 836** |
| Spécialisations | 1 273 / 235 / 380 / 4 948 | conformes |
| Partition totale | 0 document sans table fille | **0** |
| Mots-clés et rattachements | 1 211 et 20 544 | conformes |
| Rejets | 0 | **0** |
| Répartition source × licence | identique au rapport de transformation | conforme |
| Idempotence | relance sans doublon | mêmes comptes, même `max(id_document)` |
| **Non-régression du garde-fou** | le défaut reproduit doit échouer bruyamment | **exception levée** |

Le dernier test mérite d'être détaillé, un garde-fou non éprouvé n'en étant pas
un. Le défaut a été reproduit délibérément : après `initialiser()`, un `SELECT 1`
rouvre une transaction implicite, puis `charger()` est appelé.

```
transaction implicite ouverte, statut : 2
RÉSULTAT : garde-fou déclenché ✓
  message : La transaction de chargement n'a pas été validée
            (statut <TransactionStatus.INTRANS: 2>). Aucune donnée n'a été écrite.
```

Base vérifiée intacte après ce test : 6 836 documents.

---

## 6. Parenté avec l'incident S1 du 26 août

**C'est deux fois le même motif.**

Le 26 août, l'extracteur S1 rendait un bilan `succes, 0 enregistrement` : un
filtre d'API inadapté ne ramenait aucune question, et le programme concluait à
la réussite parce qu'aucune étape n'avait échoué.

Le 27 août, le chargeur rend un bilan `6 836 chargés` sur une base vide : la
transaction n'est pas validée, et le programme conclut à la réussite parce
qu'aucune étape n'a échoué.

Dans les deux cas, **le programme rend compte de son intention, pas de son
effet.** Il décrit fidèlement ce qu'il a tenté et ignore ce qui en est advenu à
l'extérieur de lui-même. Le bilan est sincère et faux.

Les contre-mesures suivent la même logique, à deux niveaux différents :

| Incident | Contre-mesure | Niveau |
|---|---|---|
| S1, 26/08 | Contrainte `extraction_succes_non_vide` : `statut = 'echec' OR nb_enregistrements > 0` | Base de données |
| Chargeur, 27/08 | Contrôle du statut transactionnel après le bloc de chargement | Applicatif |

**Leçon commune, à appliquer aux prochains composants du pipeline : un
traitement doit vérifier son effet observable depuis l'extérieur de son propre
processus, et non son état interne.** Compter ce qu'on croit avoir écrit ne
prouve rien ; le relire depuis une autre connexion le prouve.

### Application immédiate

La règle a été appliquée en sens inverse à la source S4 : une base applicative
vide y produit légitimement zéro enregistrement, et ce cas est traité comme un
succès explicite et journalisé, non comme une anomalie. Le critère n'est donc
pas « zéro est suspect » mais « le bilan doit décrire l'effet réel ».

Cette distinction ouvre un point à trancher, relevé pendant la rédaction du
présent document : **la contrainte `extraction_succes_non_vide`, écrite le
26 août pour se prémunir du cas S1, refusera d'enregistrer l'extraction S4
légitimement vide.** Elle a été conçue quand toutes les sources étaient
externes. Le point est traité au chantier suivant, celui du bilan d'extraction
persisté.
