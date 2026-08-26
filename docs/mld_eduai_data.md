# Modèle logique de données — base `eduai_data`

**Date :** 26/08/2026
**Statut :** validé le 26/08/2026 — quatre corrections de relecture intégrées
**Compétence visée :** C4 (épreuve E1)
**Source :** [modèle conceptuel](mcd_eduai_data.md), validé le 26/08/2026

Le MLD traduit le modèle conceptuel en relations. Il fixe les tables, les clés,
les domaines logiques et les contraintes d'intégrité. Il ne fixe **pas** les
types PostgreSQL, les index ni l'ordre des scripts : cela relève du MPD.

**Convention de notation.** `table (**clé primaire**, #clé étrangère, attribut)`.
Un attribut suivi de `?` est nullable.

---

## 1. Règles de passage appliquées

| Règle | Application |
|---|---|
| Une entité devient une relation | `SOURCE`, `EXTRACTION`, `DOCUMENT`, `LICENCE`, `MOT_CLE` |
| Une association 1:n se traduit par une clé étrangère du côté (1,1) | `EXTRACTION.#code_source` ; pour `DOCUMENT`, les clés sont composites — voir §3 |
| Une association n:m devient une relation propre | `COLLECTE`, `DESCRIPTION` |
| Une association porteuse d'attributs devient une relation | `COLLECTE` porte `critere_collecte` et `vu_le` |
| Une spécialisation se traduit au choix | Une table par sous-type — voir §3 |

---

## 2. Relations

```
source            (**code_source**, nom, type_source, url_racine?,
                   contraintes_acces, duree_conservation_jours?)

licence           (**code_licence**, libelle, url_texte?,
                   redistribution_autorisee, attribution_requise,
                   mention_copyright?)

extraction        (**id_extraction**, #code_source, horodatage_debut,
                   duree_secondes, statut, nb_enregistrements, nb_erreurs,
                   fichier_sortie)

document          (**id_document**, #(code_source, type_source),
                   identifiant_source, #(code_licence, attribution_requise),
                   titre, contenu, url_source?, langue, extrait_le)

document_api_rest (**#id_document**, type_source, score, nombre_reponses,
                   nombre_vues, cree_le)

document_web      (**#id_document**, type_source, page, ancre_section?)

document_fichier  (**#id_document**, type_source, chemin_fichier, format,
                   module_pedagogique, index_section, origine_declaree)

document_base_donnees (**#id_document**, type_source)      -- S4, à compléter
document_big_data     (**#id_document**, type_source)      -- S5, à compléter

collecte          (**id_collecte**, #id_extraction, #id_document,
                   critere_collecte, vu_le)

mot_cle           (**code_mot_cle**, type_mot_cle)

description       (**#id_document, #code_mot_cle**)
```

---

## 3. Implémentation de la partition

C'est le point technique central du MLD. Le MCD décrit une spécialisation
**exclusive et totale** ; aucune de ces deux propriétés ne s'obtient
gratuitement en relationnel.

### Option retenue : une table par sous-type

Trois traductions étaient possibles.

| Traduction | Rejet ou adoption |
|---|---|
| Table unique avec colonnes nullables | Rejetée. 13 colonnes dont 9 vides pour tout document donné, et plus aucune contrainte `NOT NULL` possible sur des attributs pourtant obligatoires dans leur sous-type — `score` doit exister pour un document d'API et ne doit pas exister ailleurs |
| Héritage natif PostgreSQL (`INHERITS`) | Rejetée. Les clés primaires et les clés étrangères ne sont pas héritées : une table fille peut recevoir un doublon sans que la mère s'en aperçoive. La documentation PostgreSQL le signale elle-même comme une limite |
| **Une table par sous-type, liée par clé étrangère** | **Retenue.** Chaque attribut reste `NOT NULL` là où il est obligatoire, et la clé étrangère garantit qu'aucune ligne fille n'existe sans sa mère |

### Exclusivité : garantie de façon déclarative

Le mécanisme repose sur une clé étrangère composite portant le type de source.

1. `document` porte une colonne `type_source` et une contrainte
   `UNIQUE (id_document, type_source)`.
2. Chaque table fille porte à son tour `type_source`, contraint par un `CHECK`
   à la seule valeur qui la concerne.
3. Chaque table fille référence `document (id_document, type_source)`.

Illustration du mécanisme — le DDL définitif viendra au MPD :

```sql
-- côté mère
UNIQUE (id_document, type_source)

-- côté fille
type_source  NOT NULL  CHECK (type_source = 'api_rest'),
FOREIGN KEY (id_document, type_source)
    REFERENCES document (id_document, type_source) ON DELETE CASCADE
```

Un document dont la source est de type `scraping` ne peut alors **pas** obtenir
de ligne dans `document_api_rest` : la clé étrangère composite ne trouverait
aucune ligne mère correspondante. L'exclusivité est structurelle, pas
procédurale — aucun code applicatif ne peut la contourner.

### Les cinq tables filles existent dès le premier schéma

`document_base_donnees` et `document_big_data` sont créées vides, alors que S4
et S5 ne sont pas écrites. Sans elles, la première ligne chargée par S4
n'aurait aucune table fille où atterrir et échouerait sur la partition — or les
scripts de `/docker-entrypoint-initdb.d` ne s'exécutent qu'au premier démarrage
du volume : corriger après coup imposerait un `docker compose down -v`.

Elles ne portent pour l'instant que l'armature de la partition, sans attribut
propre : les métadonnées de S4 et S5 seront ajoutées par `ALTER TABLE` quand
ces extracteurs existeront. Une table sans attribut propre est inhabituelle,
mais elle est ici le prix d'un schéma qui n'aura pas à être rejoué.

### Totalité : déclencheur différé, avec repli

Aucune contrainte déclarative SQL n'exprime « toute ligne mère a exactement une
ligne fille » : ce serait une assertion inter-tables, que PostgreSQL
n'implémente pas.

Deux voies possibles :

- **Déclencheur de contrainte différé** (`CONSTRAINT TRIGGER … DEFERRABLE
  INITIALLY DEFERRED`), vérifiant en fin de transaction que la ligne fille
  existe. Le différé est indispensable : la ligne mère est nécessairement
  insérée avant sa fille, un contrôle immédiat échouerait toujours.
- **Requête de contrôle en fin de chargement**, faisant échouer le pipeline si
  elle retourne des lignes.

**Retenu : les deux, avec une clause de retrait.** Le déclencheur protège la
base contre toute écriture, d'où qu'elle vienne ; la requête de contrôle rend
le résultat lisible dans le rapport d'exécution du pipeline, ce qu'un échec de
transaction ne fait pas.

Si le déclencheur complique l'import — insertions par lots, `COPY`, ordre
d'écriture contraint — **il est retiré et seule la requête de contrôle est
conservée**. La garantie est alors plus faible, mais le chantier ne s'arrête
pas dessus : l'échéance du 4 septembre prime sur l'élégance de la contrainte.

La requête de contrôle est le complément arithmétique de la vérification déjà
faite sur les données brutes :

```
1 273 + 235 + 380 = 1 888 lignes dans document
```

Toute somme des tables filles différente du total de la mère signale une
partition rompue.

### Le même mécanisme pour la contrainte d'attribution

La règle « si la licence exige l'attribution, alors `url_source` est
obligatoire » traverse `document` et `licence`. Une version antérieure de ce
document la confiait au déclencheur. C'est inutile : `attribution_requise` est
entièrement déterminé par `code_licence`, exactement comme `type_source` l'est
par `code_source`. Le mécanisme déjà retenu pour la partition s'y applique tel
quel.

```sql
-- côté licence
UNIQUE (code_licence, attribution_requise)

-- côté document
attribution_requise  BOOLEAN NOT NULL,
FOREIGN KEY (code_licence, attribution_requise)
    REFERENCES licence (code_licence, attribution_requise),
CHECK (NOT attribution_requise OR url_source IS NOT NULL)
```

La clé étrangère composite interdit qu'un document annonce une valeur
d'`attribution_requise` différente de celle de sa licence ; le `CHECK`, devenu
purement local à la ligne, impose alors l'URL. **Aucun déclencheur, aucune
procédure** : la contrainte est entièrement déclarative, donc vérifiée par le
moteur à chaque écriture et impossible à contourner.

---

## 4. Domaines, nullabilité et contraintes

Longueurs maximales relevées sur les 1 928 enregistrements extraits. Les
domaines sont dimensionnés avec une marge, sans excès : une colonne trop large
n'est pas une contrainte, c'est une absence de contrainte.

### `source` — 5 lignes attendues

| Attribut | Domaine logique | Null | Contrainte |
|---|---|---|---|
| `code_source` | chaîne(2) | non | PK ; `CHECK` sur le motif `s[1-5]` |
| `nom` | chaîne(100) | non | `UNIQUE` |
| `type_source` | énuméré | non | `api_rest`, `scraping`, `fichier`, `base_donnees`, `big_data` |
| `url_racine` | chaîne(255) | **oui** | Nul pour une source locale (S3) |
| `contraintes_acces` | texte | non | Quota, robots.txt, conditions — exigé par C1 |
| `duree_conservation_jours` | entier | **oui** | `CHECK > 0`. **`NULL` signifie « sans terme »**, pas « non renseigné » |

`UNIQUE (code_source, type_source)` : contrainte technique, support de la clé
étrangère composite décrite en §3.

La sémantique de `NULL` sur `duree_conservation_jours` mérite d'être défendue,
car un `NULL` porteur de sens est en général une faute. Ici l'alternative —
une sentinelle du type `99999` — serait pire : elle se prêterait aux
comparaisons arithmétiques et une purge écrirait un jour `WHERE age >
duree_conservation_jours` sans se rendre compte qu'elle vient de dater
l'éternité. `NULL` est exclu de toute comparaison, ce qui est exactement le
comportement recherché.

### `licence` — 4 lignes attendues

| Attribut | Domaine logique | Null | Contrainte |
|---|---|---|---|
| `code_licence` | chaîne(20) | non | PK — `CC-BY-SA-4.0`, `PSF`, `PROPRIETAIRE`, `A_VERIFIER` |
| `libelle` | chaîne(150) | non | |
| `url_texte` | chaîne(255) | **oui** | Nul pour `PROPRIETAIRE` et `A_VERIFIER` |
| `redistribution_autorisee` | booléen | non | `faux` pour `A_VERIFIER` |
| `attribution_requise` | booléen | non | `vrai` pour `CC-BY-SA-4.0` et `PSF` |
| `mention_copyright` | chaîne(255) | **oui** | Notice fixe imposée par certaines licences |

Ces deux booléens ne documentent pas, ils **filtrent** : c'est par eux que les
82 documents à licence incertaine sont écartés de l'indexation RAG.

`UNIQUE (code_licence, attribution_requise)` : support de la clé étrangère
composite qui rend la contrainte d'attribution déclarative (§3).

**`mention_copyright` était initialement placée dans `document_web`.** Une
vérification sur les données a montré qu'elle y prend une valeur unique sur les
235 lignes — « Copyright (c) 2001-2026 Python Software Foundation » — et
qu'elle dépend de la licence PSF, non du document. C'était une seconde entorse
à la 3NF, non repérée à la première rédaction. Elle est corrigée par
déplacement : la notice appartient à la licence qui l'impose.

### `extraction` — 3 lignes aujourd'hui, une par exécution ensuite

| Attribut | Domaine logique | Null | Contrainte |
|---|---|---|---|
| `id_extraction` | entier auto | non | PK |
| `code_source` | chaîne(2) | non | FK → `source` |
| `horodatage_debut` | horodatage avec fuseau | non | |
| `duree_secondes` | décimal(10,2) | non | `CHECK >= 0` |
| `statut` | énuméré | non | `succes`, `echec` |
| `nb_enregistrements` | entier | non | `CHECK >= 0` |
| `nb_erreurs` | entier | non | `CHECK >= 0` |
| `fichier_sortie` | chaîne(255) | non | |

Deux contraintes méritent justification.

`UNIQUE (code_source, horodatage_debut)` rend le chargement idempotent :
rejouer l'import d'un même bilan ne crée pas une seconde exécution fantôme.

`CHECK (statut = 'echec' OR nb_enregistrements > 0)` — **une extraction ne peut
pas réussir en ne produisant rien.** Cette contrainte n'est pas théorique :
c'est exactement l'état qu'a connu l'extracteur S1 avant correction, quand un
filtre d'API inadapté renvoyait des réponses vides. Le bilan annonçait
`statut: succes, enregistrements: 0`. La base aurait refusé cette ligne.

### `document` — 1 888 lignes attendues

| Attribut | Domaine logique | Null | Max observé | Contrainte |
|---|---|---|---|---|
| `id_document` | entier auto | non | | PK |
| `code_source` | chaîne(2) | non | | FK composite avec `type_source` → `source` |
| `type_source` | énuméré | non | | Dénormalisation contrôlée — voir §5 |
| `identifiant_source` | chaîne(120) | non | 89 | |
| `code_licence` | chaîne(20) | non | | FK composite avec `attribution_requise` → `licence` |
| `attribution_requise` | booléen | non | | Dénormalisation contrôlée — voir §5 |
| `titre` | chaîne(255) | non | 130 | Non vide après suppression des espaces |
| `contenu` | texte | non | 149 083 | **Non vide** après suppression des espaces |
| `url_source` | chaîne(500) | **oui** | 125 | Voir ci-dessous |
| `langue` | énuméré | non | | `fr`, `en` |
| `extrait_le` | horodatage avec fuseau | non | | Date de **première** collecte |

`UNIQUE (code_source, identifiant_source)` : clé naturelle. L'unicité ne porte
pas sur `identifiant_source` seul — rien ne garantit qu'un identifiant Stack
Overflow ne collisionne jamais avec un identifiant du corpus local.

`UNIQUE (id_document, type_source)` : support de la clé étrangère composite.

`contenu` est un texte sans longueur maximale, assorti d'une contrainte de
non-vacuité, conformément à l'arbitrage. Le découpage relève de C3.

**Une seule clé étrangère vers `source`.** La clé composite
`(code_source, type_source)` garantit à elle seule l'intégrité référentielle de
`code_source` : une clé étrangère supplémentaire sur `code_source` seul serait
redondante, coûterait un index de plus et n'ajouterait aucune garantie. Elle est
supprimée. Même raisonnement pour `code_licence`, couvert par
`(code_licence, attribution_requise)`.

**Nullabilité de `url_source`.** Les 1 928 enregistrements en portent tous une,
mais S4 (base de données) et S5 (big data) n'en auront pas nécessairement. La
colonne est donc nullable, sous la contrainte
`CHECK (NOT attribution_requise OR url_source IS NOT NULL)` : sans elle, on
pourrait charger un document sous CC BY-SA sans moyen de créditer son auteur —
violation de licence silencieuse. Grâce à la dénormalisation
d'`attribution_requise`, ce `CHECK` est **local à la ligne**, donc entièrement
déclaratif (§3).

### Tables filles

**`document_api_rest`** — 1 273 lignes

| Attribut | Domaine | Null | Contrainte |
|---|---|---|---|
| `id_document` | entier | non | PK, FK composite → `document` |
| `type_source` | énuméré | non | `CHECK = 'api_rest'` |
| `score` | entier | non | Peut être négatif — un score Stack Overflow l'est parfois |
| `nombre_reponses` | entier | non | `CHECK >= 0` |
| `nombre_vues` | entier | non | `CHECK >= 0` |
| `cree_le` | horodatage avec fuseau | non | Fourni en secondes Unix, converti à la transformation (C3) |

**`document_web`** — 235 lignes

| Attribut | Domaine | Null | Max observé | Contrainte |
|---|---|---|---|---|
| `id_document` | entier | non | | PK, FK composite |
| `type_source` | énuméré | non | | `CHECK = 'scraping'` |
| `page` | chaîne(255) | non | 31 | |
| `ancre_section` | chaîne(255) | **oui** | 56 | Toutes renseignées aujourd'hui, mais une section Sphinx sans `id` est possible |

`mention_copyright` a été déplacée dans `licence` — voir plus haut.

**`document_fichier`** — 380 lignes

| Attribut | Domaine | Null | Max observé | Contrainte |
|---|---|---|---|---|
| `id_document` | entier | non | | PK, FK composite |
| `type_source` | énuméré | non | | `CHECK = 'fichier'` |
| `chemin_fichier` | chaîne(255) | non | 66 | |
| `format` | énuméré | non | | `md`, `pdf`, `ipynb` |
| `module_pedagogique` | chaîne(50) | non | 9 | |
| `index_section` | entier | non | | `CHECK >= 0` |
| `origine_declaree` | chaîne(255) | non | 23 | Issue du manifeste de provenance |

### `collecte` — 1 928 lignes aujourd'hui, croissante

| Attribut | Domaine | Null | Max observé | Contrainte |
|---|---|---|---|---|
| `id_collecte` | entier auto | non | | PK |
| `id_extraction` | entier | non | | FK → `extraction` |
| `id_document` | entier | non | | FK → `document` |
| `critere_collecte` | chaîne(200) | non | 66 | Tag pour S1, page pour S2, chemin pour S3 |
| `vu_le` | horodatage avec fuseau | non | | |

`UNIQUE (id_extraction, id_document, critere_collecte)`.

**Clé primaire technique plutôt que naturelle.** Le triplet ci-dessus identifie
la ligne, mais en faire la clé primaire imposerait une clé de 200 caractères
recopiée dans tout index. La clé technique reste petite ; l'unicité métier est
préservée par la contrainte.

`critere_collecte` est **non nullable**, y compris pour S4 et S5 : toute source
est interrogée par un chemin — une requête nommée, une partition. Autoriser le
nul aurait rendu la contrainte d'unicité inopérante, `NULL` n'étant jamais égal
à `NULL`.

### `mot_cle` — 806 lignes, et `description` — 5 200 lignes

| Attribut | Domaine | Null | Max observé | Contrainte |
|---|---|---|---|---|
| `code_mot_cle` | chaîne(60) | non | 30 | PK, forme normalisée en minuscules |
| `type_mot_cle` | énuméré | non | | `tag_source`, `module` |

`description (**#id_document, #code_mot_cle**)` : clé primaire composite des
deux clés étrangères. Aucun attribut propre.

Répartition observée : 804 tags issus de Stack Overflow, et seulement **2
modules** pour le corpus local — `01_python` et `resources`. Ce second chiffre
est bas ; il reflète l'arborescence réelle de `data/contents/`, où les autres
modules annoncés n'ont pas de fichiers. C'est un constat sur le corpus, pas un
défaut du modèle, mais il mérite d'être connu avant de s'appuyer sur
`module_pedagogique` pour filtrer.

---

## 5. Normalisation

Le schéma est en **troisième forme normale**, à une exception délibérée.

| Relation | Vérification |
|---|---|
| `source`, `licence`, `mot_cle` | Clé simple, attributs atomiques, aucune dépendance transitive |
| `extraction` | Tous les attributs dépendent de `id_extraction` seul |
| `document` | Voir l'exception ci-dessous |
| Tables filles | Tous les attributs dépendent de `id_document` |
| `collecte` | `critere_collecte` et `vu_le` dépendent du triplet complet, pas d'une partie — pas de dépendance partielle |
| `description` | Relation pure, sans attribut non clé |

**Les exceptions : `document.type_source` et `document.attribution_requise`.**
Ces deux attributs dépendent respectivement de `code_source` et de
`code_licence`, eux-mêmes non clés : ce sont des dépendances transitives, donc
deux entorses à la 3NF.

Elles sont assumées, pour la même raison : sans ces colonnes, les clés
étrangères composites qui rendent l'exclusivité de la partition et la
contrainte d'attribution **déclaratives** (§3) sont impossibles. Le choix est
donc entre une redondance contrôlée et une intégrité confiée au code
applicatif — c'est-à-dire non garantie.

Et les redondances sont **rendues inoffensives** : `document` porte les clés
étrangères composites `(code_source, type_source)` vers `source` et
`(code_licence, attribution_requise)` vers `licence`. Une valeur incohérente
avec sa source ou sa licence est rejetée par le moteur. La donnée est
dupliquée, mais elle ne peut pas diverger — ce qui est la seule chose qu'on
reproche vraiment à une dénormalisation.

C'est un cas où la 3NF stricte donnerait un schéma *moins* sûr : la forme
normale interdirait la redondance, donc la clé composite, donc la contrainte
déclarative, et l'intégrité retomberait sur du code.

**Une entorse involontaire, corrigée.** `document_web.mention_copyright`
dépendait de la licence et non du document : valeur unique sur les 235 lignes.
Elle n'avait aucune justification, contrairement aux deux précédentes, et a été
déplacée dans `licence`. C'est la différence entre une dénormalisation choisie
et une erreur de modélisation.

---

## 6. Volumétrie et vérification

| Table | Lignes attendues | Origine du chiffre |
|---|---|---|
| `source` | 5 | Les cinq types du référentiel |
| `licence` | 4 | Licences distinctes observées |
| `extraction` | 3 puis +1 par exécution | |
| `document` | 1 888 | 1 928 bruts − 40 doublons de collecte |
| `document_api_rest` | 1 273 | |
| `document_web` | 235 | |
| `document_fichier` | 380 | |
| `collecte` | 1 928 | Une par enregistrement brut |
| `mot_cle` | 806 | 804 tags + 2 modules |
| `description` | 5 200 | Associations document–mot-clé |

Deux égalités doivent tenir après chargement, et serviront de contrôle :

```
document_api_rest + document_web + document_fichier = document
        1 273     +      235     +       380        =   1 888   ✓

collecte = nombre total d'enregistrements bruts
  1 928  =                1 928                     ✓
```

La première vérifie la partition, la seconde qu'aucune collecte n'a été perdue
au chargement.

---

## 7. Ce que le MPD met en œuvre

- Types PostgreSQL concrets — `VARCHAR` contre `TEXT`, `ENUM` natif contre
  table de référence et clé étrangère, `TIMESTAMPTZ`, `NUMERIC`.
- Index, justifiés par les requêtes de C2 et non posés au hasard.
- Écriture du déclencheur de partition et de la contrainte d'attribution.
- Ordre des scripts dans `data_pipeline/load/sql/`, contraint par les
  dépendances de clés étrangères : les tables de référence (`source`,
  `licence`, `mot_cle`) avant `document`, elle-même avant ses filles et avant
  `collecte`.
- Dictionnaire de données.

---

## 8. Arbitrages retenus

| Point | Décision |
|---|---|
| Énumérés | `ENUM` natif PostgreSQL pour `statut`, `langue`, `format` et `type_mot_cle` — domaines fermés et stables. **Table de référence** pour `type_source`, déjà porté par `source` et destiné à recevoir un libellé |
| `ON DELETE` de `collecte` | `RESTRICT` vers `extraction` — supprimer une exécution ne doit pas emporter l'historique qu'on a décidé de conserver ; `CASCADE` vers `document` |
| Conservation de S4 | **90 jours** |
| Casse des mots-clés | Normalisation en minuscules à l'import, garantie par un `CHECK` |

### Ce que la durée de 90 jours suppose sur S4

Aucun `user_id`, aucune adresse IP, aucune adresse électronique n'entre dans
`eduai_data`. Un identifiant pseudonyme n'est retenu que si le lien entre
plusieurs soumissions d'un même apprenant est nécessaire au traitement — et
dans ce seul cas.

C'est cohérent avec l'absence d'entité « personne » posée au MCD : la
contrainte est ici reportée sur l'extracteur S4, qui devra écarter ces champs à
la source plutôt que les charger puis les purger. Une donnée qu'on ne collecte
pas n'a pas besoin de durée de conservation.
