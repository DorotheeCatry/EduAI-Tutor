# Incident 002 — Une conversion correcte à petite échelle, rédhibitoire à grande

**Date :** 27–28 août 2026
**Composant :** `data_pipeline/extract/sql/s5_conversion_parquet.spark.sql`
**Gravité :** majeure — traitement impraticable, aucune donnée perdue
**Statut :** résolu, gain mesuré
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C2 (E1) — optimisation de requête ; C20 (E5)

---

## 1. Déclenchement

**27/08, 22:56.** Lancement de la conversion du dump Stack Overflow — 97 Gio de
XML — par la requête qui traitait le dump Data Science, 123 Mio, en 76 secondes.

**28/08, 12:45.** Après **13 h 50**, le compteur affiche **24 tâches terminées
sur 775**.

**28/08, 13:15.** Après **14 h 19**, **48 tâches sur 775**.

Aucune erreur. Aucun avertissement. La conversion avançait — simplement trop
lentement pour aboutir. C'est ce qui rend cet incident différent des précédents :
rien ne mentait, tout était exact, et le résultat était inatteignable.

**Projection.** 48 tâches en 14 h 19, soit 6,0 Gio traités sur 97 — un débit de
**0,12 Mio/s**. Achèvement projeté : **environ trois semaines**. La soutenance
est dans dix-sept jours.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Corpus existant | **Aucun.** Le corpus Data Science, 4 948 documents, était sauvegardé |
| Base `eduai_data` | Aucun. La conversion écrit du Parquet, pas la base |
| Machine | 8 cœurs et 12 Gio mobilisés pendant 22 h, charge moyenne 12 à 15 |
| Autres chantiers | Ralentis. Aucun traitement lourd ne pouvait être lancé en parallèle |
| Données perdues | **Aucune.** Table Parquet partielle de 2,2 Gio, sans marqueur `_SUCCESS`, supprimée |

**La gravité tient au temps, pas aux dégâts.** Vingt-deux heures de machine pour
un résultat inutilisable, dans une période où chaque journée compte.

---

## 3. Diagnostic

### 3.1 Écarter la panne

Le traitement n'était ni bloqué ni en erreur : le compteur de tâches avançait, la
table Parquet grossissait — 1,5 Gio après quatorze heures. Ce n'était donc pas un
interblocage ni une attente réseau, mais un **coût unitaire trop élevé**.

### 3.2 Localiser le coût

La requête de conversion appelait `xpath_string` **treize fois par ligne** :

```sql
CAST(xpath_string(ligne, '/row/@Id')         AS BIGINT) AS id_post,
CAST(xpath_string(ligne, '/row/@PostTypeId') AS INT)    AS type_post,
...                                          -- onze autres appels
```

`xpath_string` est une fonction native de Spark, exécutée dans la JVM — il n'y
avait donc **aucun aller-retour Python à supprimer**, le piège habituel n'étant
pas celui-ci. Mais chaque appel **construit un arbre XML complet du fragment**.
Treize appels, c'est treize analyses du même fragment, puis treize arbres jetés.

Sur 78 926 lignes, cela coûte quelques dizaines de secondes. Sur une soixantaine
de millions, cela devient le traitement tout entier.

### 3.3 Constater que le filtrage arrivait trop tard

Second facteur, aggravant le premier : **toutes** les lignes étaient analysées,
puis filtrées ensuite par la requête de sélection. Le dump Stack Overflow est
généraliste ; l'écrasante majorité de ses questions ne relève pas du programme
de la formation. Le traitement payait le coût d'extraction de tout ce qu'il
allait écarter.

### 3.4 Cause racine

**Une conception dimensionnée pour l'échelle où elle a été écrite.** Analyser
avant de filtrer, et analyser treize fois, sont des choix invisibles à 123 Mio
et rédhibitoires à 97 Gio. Le rapport entre les deux volumes est de 800 ; le
rapport entre les temps l'aurait été aussi, sans les effets de charge mémoire
qui l'ont encore dégradé.

---

## 4. Résolution

Trois changements, par ordre de gain attendu.

### 4.1 Filtrer avant d'analyser

Les prédicats portent désormais sur le **texte brut**, par `LIKE` — une recherche
de sous-chaîne, sans analyse ni allocation. Une ligne écartée à ce stade n'est
jamais analysée.

Sont retenues les questions portant l'un des thèmes du programme **et** une
réponse acceptée, puis **les seules réponses que ces questions ont acceptées**.
Retenir toutes les réponses aurait conservé la moitié du dump ; les restreindre
suppose de connaître les identifiants attendus, d'où deux balayages du texte
plutôt qu'un. **Deux balayages à `LIKE` coûtent moins qu'un seul à treize
analyses XML** — c'est le calcul qui a décidé.

### 4.2 Supprimer les allers-retours Python

**Rien à supprimer : il n'y en avait aucun.** La conversion était déjà
entièrement en SQL natif. Ce point est consigné parce qu'il est le premier
suspect dans ce genre d'incident, et parce que l'écarter a orienté le diagnostic
vers la vraie cause.

### 4.3 Supprimer toute analyse XML

L'objectif était de ramener treize analyses à une. Il n'en reste **aucune** :
les attributs sont lus par expressions régulières ancrées sur leur nom, qui ne
construisent pas d'arbre et n'allouent pas d'objet par nœud.

Conséquence à traiter : `xpath_string` **décodait les entités XML**. Sans lui,
`&lt;p&gt;` ne serait plus reconnu comme une balise par le nettoyage effectué en
Python, et le corpus se remplirait de balisage brut. Le décodage est donc
explicite, appliqué aux seules lignes retenues, et `&amp;` est décodé **en
dernier** : le décoder en premier transformerait un `&lt;` littéral voulu par
l'auteur en véritable balise.

---

## 5. Tests en succès

### 5.1 Fidélité — à périmètre constant

La nouvelle requête a été rejouée sur le dump Data Science avec un motif de
thèmes permissif, afin que le périmètre soit **identique** à celui de l'ancienne
version. Sans cette précaution, la comparaison aurait mêlé un changement de
performance et un changement de périmètre.

| Contrôle | Résultat |
|---|---|
| Documents produits | **4 948**, exactement comme la référence |
| Identifiants manquants | **0** |
| Identifiants en trop | **0** |
| `titre` | 0 écart sur 4 948 |
| `source_url`, `licence`, `langue`, `source_type` | 0 écart |
| mots-clés, métadonnées | 0 écart |
| `contenu` | **1 écart sur 4 948** |

### 5.2 L'unique écart, et pourquoi il est conservé

Le document `se_datascience_11816` diffère : l'ancienne version rend **trois
espaces** là où la nouvelle rend **trois tabulations**, dans une trace Java citée
à l'intérieur d'un bloc de code. Longueurs identiques, reste du texte identique.

Retour à la source brute : le XML contient de **vraies tabulations** dans la
valeur d'attribut, non des entités `&#x9;` — le fichier n'en contient aucune.

La cause est une règle de la norme XML : lors de la lecture d'une **valeur
d'attribut**, un analyseur conforme remplace chaque tabulation, retour chariot et
saut de ligne par une espace. `xpath_string` appliquait cette normalisation ;
l'extraction par expression régulière ne l'applique pas et rend les octets
d'origine.

**L'écart est conservé, et c'est un choix.** Le corpus est un corpus de code, où
l'indentation porte du sens — le projet protège d'ailleurs explicitement les
blocs de code de toute normalisation d'espaces ailleurs dans le pipeline. Rendre
les tabulations d'origine est plus fidèle à ce que l'auteur a écrit que de les
aplatir en espaces.

C'est aussi exactement le type d'écart qu'un contrôle par simple décompte aurait
laissé passer : **4 948 documents des deux côtés, et un texte modifié**. La
comparaison de contenu était nécessaire.

### 5.3 Gain mesuré

**À données identiques** — dump Data Science, 123 Mio, même périmètre :

| Version | Conversion |
|---|---|
| Ancienne (`xpath_string` ×13) | **75,80 s** |
| Nouvelle (filtre puis regex) | **35,03 s** |
| **Gain** | **×2,2** |

Le facteur est modeste parce qu'à ce volume l'amorçage de Spark — une quinzaine
de secondes — pèse davantage que le traitement.

**À l'échelle**, trois points de mesure sur des sous-ensembles du dump Stack
Overflow, machine libre :

| Volume | Conversion | Débit | Sélection | Documents |
|---|---|---|---|---|
| 123 Mio | 35,03 s | 3,5 Mio/s | 10,75 s | 4 948 |
| 1,9 Gio | 76,96 s | 25 Mio/s | 25,69 s | 20 707 |
| 9,4 Gio | 226,24 s | **42 Mio/s** | 77,34 s | 88 799 |

Le débit **croît** avec le volume : le coût fixe d'amorçage s'amortit.

**Comparaison des deux versions à grande échelle :**

| | Ancienne | Nouvelle |
|---|---|---|
| Débit constaté | 0,12 Mio/s (6,0 Gio en 14 h 19) | 42 Mio/s (9,4 Gio en 226 s) |
| Projection sur 97 Gio | **≈ 3 semaines** | **≈ 40 min** de conversion |
| Rapport | | **≈ 350×** |

**Précision d'honnêteté :** le chiffre de l'ancienne version est une observation
partielle — la conversion a été arrêtée à 48 tâches sur 775, elle n'a jamais
abouti. Le rapport de 350 est donc une projection à partir d'un débit constaté,
non la comparaison de deux exécutions complètes. Le seul rapport mesuré de bout
en bout sur les mêmes données est celui de 2,2 sur le dump Data Science.

---

## 6. Ce que cet incident ajoute aux précédents

Les cinq incidents antérieurs partageaient un motif : **un rapport de succès qui
ne correspondait à rien**. Celui-ci en diffère, et c'est ce qui le rend utile.

**Ici, tout était exact.** Le compteur de tâches disait vrai, la table grossissait
vraiment, aucun composant ne mentait. Le défaut n'était pas dans la mesure mais
dans la **conception** : un traitement correct, dimensionné pour l'échelle à
laquelle il a été écrit et jamais éprouvé à celle où il devait servir.

La leçon n'est donc pas « vérifier l'effet » mais **« vérifier l'échelle »** : un
traitement validé sur un échantillon n'est pas validé. Le rapport de volume entre
le jeu d'essai et le jeu réel — ici 800 — est une information qu'il faut
regarder avant de lancer, pas après quatorze heures.

**Le garde-fou du projet a néanmoins servi.** Le palier de 2 Gio a produit zéro
document, les 2 premiers Go du dump ne contenant que des posts de 2008 à 2010,
antérieurs à la fenêtre de fraîcheur. Le socle d'extraction a rendu
`statut: echec` et non `succes` — la contrainte née de l'incident S1 du 26 août
a fonctionné dans un cas qu'elle n'avait pas été écrite pour couvrir.

---

## 7. Reste à faire

- **Lancer la conversion complète** sur les 97 Gio, machine libre, le soir.
  Projection : 40 min de conversion, environ 13 min de sélection.
- **Mesurer le résultat réel** et le confronter à la projection ci-dessus. Une
  projection n'est pas une mesure, et ce document le dit à chaque fois qu'il en
  donne une.
- **Évaluer la carte d'attributs** par `str_to_map`, écartée faute de pouvoir la
  vérifier pendant que la machine travaillait. Le gain attendu est secondaire :
  c'est le filtrage préalable qui écarte le volume.
