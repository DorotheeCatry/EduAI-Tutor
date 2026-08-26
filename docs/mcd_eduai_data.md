# Modèle conceptuel de données — base `eduai_data`

**Date :** 26/08/2026
**Statut :** validé sur le fond le 26/08/2026 — corrections de cardinalité, de partition et de clés étrangères intégrées
**Compétence visée :** C4 (épreuve E1) — création d'une base de données dans le
respect du RGPD
**Périmètre :** uniquement les documents collectés par les cinq extracteurs du
pipeline. La base applicative `eduai_app` (utilisateurs, cours, exercices,
quiz) fait l'objet d'un modèle distinct, relevant de C17.

---

## 1. Ce que le modèle doit accueillir

Le contrat de données commun aux cinq extracteurs est la dataclass
`Enregistrement` de
[base_extractor.py](../data_pipeline/extract/base_extractor.py) : `identifiant`,
`titre`, `contenu`, `source_nom`, `source_type`, `source_url`, `licence`,
`langue`, `extrait_le`, `metadonnees`.

Trois sources sur cinq sont déjà extraites. Le modèle est construit sur leurs
données réelles, et non sur une projection théorique :

| Source | Type de source | Documents | Langue | Licences distinctes |
|---|---|---|---|---|
| Stack Overflow | `api_rest` | 1 313 | en | 1 — CC BY-SA 4.0 |
| Documentation Python | `scraping` | 235 [^s2] | en | 1 — PSF License Agreement |
| Corpus pédagogique local | `fichier` | 380 | fr | 2 — Propriétaire (298), à vérifier (82) |
| **Total** | | **1 928** | | **4** |

[^s2]: Compte revérifié en réexécutant l'extracteur : 235 enregistrements, avec
    un jeu d'identifiants strictement identique à celui du fichier en place. Les
    16 pages parcourues contiennent 247 balises `<section>` ; 12 sont écartées
    par le seuil de 200 caractères, qui élimine les sommaires et les renvois sans
    contenu propre. 247 et 235 sont donc les deux seuls comptes reproductibles.

Les deux sources restantes — S4 (base de données) et S5 (système big data) —
ne sont pas encore écrites. Le modèle doit les accueillir sans être remanié.

### Le champ `metadonnees` diffère selon la source

C'est le point qui structure tout le modèle. Chaque extracteur remplit un
dictionnaire de forme différente :

| Source | Clés de `metadonnees` |
|---|---|
| Stack Overflow | `tag_recherche`, `tags`, `score`, `nombre_reponses`, `vues`, `cree_le` |
| Documentation Python | `section_html`, `page`, `copyright` |
| Corpus local | `module`, `fichier`, `format`, `origine`, `section_index` |

Aucune clé n'est commune aux trois. Un modèle qui les aplatirait dans une même
table produirait une majorité de colonnes vides.

---

## 2. Deux constats issus des données, et ce qu'ils imposent

### 2.1 Un document peut être collecté plusieurs fois dans une même exécution

Sur les 1 928 enregistrements bruts, **40 identifiants apparaissent deux fois**
— 1 888 documents distincts. Exemple relevé dans les données :

```
so_16476924   tag_recherche = python    tags = [python, pandas, dataframe, loops]
so_16476924   tag_recherche = pandas    tags = [python, pandas, dataframe, loops]
```

Il ne s'agit pas de deux documents mais **d'un seul document atteint par deux
chemins de collecte**. Le critère de recherche (`tag_recherche`) est donc une
propriété de l'acte de collecte, pas du document.

Conséquence sur le modèle : une association **COLLECTE** porte le critère,
entre l'extraction et le document. Ce choix résout au passage l'idempotence —
relancer un extracteur ajoute des collectes, sans dupliquer les documents.

### 2.2 Une source peut porter plusieurs licences

Le corpus local mélange du contenu produit par l'autrice (298 documents) et des
fichiers d'origine non tranchée (82 documents, licence « A VERIFIER »).

Conséquence : la licence se rattache au **document**, pas à la source. Rattacher
la licence à la source aurait fait disparaître cette distinction, alors qu'elle
conditionne le droit de redistribuer.

---

## 3. Entités

### SOURCE

Les cinq sources exigées par le référentiel. Table de faible cardinalité (5
lignes) mais structurante : c'est elle qui rend la couverture des cinq types
vérifiable par une seule requête.

| Attribut | Nature | Rôle |
|---|---|---|
| `code_source` | texte court | Identifiant naturel : `s1`, `s2`, `s3`, `s4`, `s5` |
| `nom` | texte | Libellé lisible (« Stack Overflow ») |
| `type_source` | énuméré | `api_rest`, `scraping`, `fichier`, `base_donnees`, `big_data` |
| `url_racine` | texte | Point d'entrée de la source, nul pour une source locale |
| `contraintes_acces` | texte | Quota, `robots.txt`, conditions d'utilisation — exigé par C1 |
| `duree_conservation_jours` | entier | Durée au-delà de laquelle les documents sont purgés (RGPD) |

`type_source` est énuméré et non libre : les cinq valeurs sont fixées par le
référentiel, une valeur hors liste serait une erreur de saisie.

### EXTRACTION

Une exécution d'un extracteur. Correspond au bilan déjà retourné par
`ExtracteurBase.executer()`, aujourd'hui seulement journalisé.

| Attribut | Nature | Rôle |
|---|---|---|
| `id_extraction` | identifiant | |
| `horodatage_debut` | horodatage | Début de l'exécution |
| `duree_secondes` | décimal | |
| `statut` | énuméré | `succes`, `echec` |
| `nb_enregistrements` | entier | Volumétrie produite |
| `nb_erreurs` | entier | Erreurs tolérées pendant l'exécution |
| `fichier_sortie` | texte | Chemin du JSONL brut, pour rejouer la transformation |

Cette entité n'existait dans aucune version antérieure du pipeline. Elle est
ajoutée pour trois raisons : la traçabilité exigée par C1, la possibilité de
comparer deux exécutions pour détecter une source qui se dégrade, et l'ancrage
de la purge RGPD sur une date d'extraction plutôt que sur une date de contenu.

### DOCUMENT

L'unité de contenu, quelle que soit la source. Un document est une section
autonome : une question Stack Overflow avec sa réponse acceptée, une section
Sphinx, une section de cours.

| Attribut | Nature | Rôle |
|---|---|---|
| `id_document` | identifiant | Clé technique |
| `code_source` | référence | Source dont provient le document — association PROVIENT_DE |
| `code_licence` | référence | Licence couvrant le document — association EST_COUVERT_PAR |
| `identifiant_source` | texte | Identifiant stable côté source (`so_16476924`, `pydoc_…`) |
| `titre` | texte | Médiane 41 caractères, maximum relevé 130 |
| `contenu` | texte long | Médiane 1 224 caractères, maximum relevé 149 083 |
| `url_source` | texte | Adresse permettant de citer la source — **support de l'attribution** |
| `langue` | énuméré | `fr` ou `en` ; 1 548 documents en anglais, 380 en français |
| `extrait_le` | horodatage | Date de première collecte |

L'unicité porte sur le couple (`SOURCE`, `identifiant_source`) et non sur
`identifiant_source` seul : rien ne garantit qu'un identifiant Stack Overflow ne
collisionne jamais avec un identifiant du corpus local.

### Spécialisation de DOCUMENT selon le type de source

Chaque type de source apporte ses propres attributs, tous renseignés à 100 %
dans leur sous-ensemble et absents ailleurs. Ils sont donc modélisés en
**spécialisation**.

> **Contrainte de partition (X,T).** La spécialisation est à la fois
> **exclusive** — un document appartient à une sous-entité et une seule, jamais
> à deux — et **totale** : tout document appartient à exactement une
> sous-entité, aucun ne reste au niveau de `DOCUMENT` seul. Les deux moitiés de
> la contrainte se déduisent du type de sa source, qui est unique et toujours
> renseigné.
>
> Le diagramme ci-dessous la représente par trois relations un-à-zéro-ou-un
> (`||--o|`) : la notation `erDiagram` de Mermaid ne sait pas exprimer une
> partition. Le zéro-ou-un y traduit le point de vue d'une sous-entité prise
> isolément — un document donné n'a pas de ligne dans `DOCUMENT_WEB` s'il vient
> de l'API — et non une autorisation d'appartenir à aucune.
>
> Cet écart entre le modèle et sa représentation impose une implémentation
> explicite au MPD. L'exclusivité sera garantie de façon déclarative par une
> clé étrangère composite portant le type de source ; la totalité, qu'aucune
> contrainte déclarative ne couvre en SQL, par un déclencheur ou par une
> vérification à la fin du chargement. Le MLD en précisera le mécanisme.

**DOCUMENT_API_REST** (1 313 documents)

| Attribut | Nature | Rôle |
|---|---|---|
| `score` | entier | Votes de la communauté — sert au filtrage qualité |
| `nombre_reponses` | entier | |
| `nombre_vues` | entier | |
| `cree_le` | horodatage | Fourni en secondes Unix par l'API, converti à la transformation |

**DOCUMENT_WEB** (235 documents)

| Attribut | Nature | Rôle |
|---|---|---|
| `page` | texte | Chemin de la page d'origine (`/3/tutorial/errors.html`) |
| `ancre_section` | texte | Identifiant HTML de la section, permet le lien profond |
| `mention_copyright` | texte | Notice imposée par la licence PSF |

**DOCUMENT_FICHIER** (380 documents)

| Attribut | Nature | Rôle |
|---|---|---|
| `chemin_fichier` | texte | Chemin relatif dans le corpus |
| `format` | énuméré | `md`, `pdf`, `ipynb` |
| `module_pedagogique` | texte | Module d'origine (`01_python`…), sert au filtrage thématique |
| `index_section` | entier | Rang de la section dans le fichier, restitue l'ordre de lecture |
| `origine_declaree` | texte | Provenance issue du manifeste `data/contents/provenance.json` |

S4 et S5 ajouteront chacune leur spécialisation, sans toucher aux existantes.

### LICENCE

Quatre licences distinctes pour 1 928 documents. Entité séparée parce que les
conditions de réutilisation sont des données à part entière, pas une étiquette.

| Attribut | Nature | Rôle |
|---|---|---|
| `code_licence` | texte court | `CC-BY-SA-4.0`, `PSF`, `PROPRIETAIRE`, `A_VERIFIER` |
| `libelle` | texte | Intitulé complet |
| `url_texte` | texte | Texte de référence de la licence |
| `redistribution_autorisee` | booléen | Répond à : ce document peut-il sortir du projet ? |
| `attribution_requise` | booléen | Répond à : faut-il citer la source à l'affichage ? |

Ces deux booléens sont le cœur de l'entité. Ils permettent d'écarter par
requête, et non par mémoire, les documents qu'on n'a pas le droit de
redistribuer — les 82 documents « à vérifier » du corpus notamment.

### MOT_CLE

804 mots-clés distincts, 4 999 associations, en moyenne 3,8 par document
Stack Overflow, 5 au maximum. Les mots-clés servent au filtrage thématique du
RAG.

| Attribut | Nature | Rôle |
|---|---|---|
| `code_mot_cle` | texte | Forme normalisée (`machine-learning`) |
| `type_mot_cle` | énuméré | `tag_source` (issu de la source), `module` (classification interne) |

`type_mot_cle` évite de confondre un tag subi (`sql-server`, venu de Stack
Overflow) et une classification choisie (`01_python`, imposée par
l'arborescence du corpus).

---

## 4. Associations et cardinalités

| Association | Entités | Cardinalités (Merise) | Lecture |
|---|---|---|---|
| **FAIT_OBJET_DE** | SOURCE → EXTRACTION | SOURCE (0,n) — EXTRACTION (1,1) | Une source donne lieu à plusieurs exécutions ; une exécution porte sur une seule source |
| **COLLECTE** | EXTRACTION ↔ DOCUMENT | EXTRACTION (0,n) — DOCUMENT (1,n) | Une exécution collecte zéro à plusieurs documents — zéro lorsqu'elle échoue ; un document est collecté au moins une fois, et peut l'être plusieurs fois, y compris dans une même exécution |
| **PROVIENT_DE** | DOCUMENT → SOURCE | DOCUMENT (1,1) — SOURCE (0,n) | Un document appartient à une source et une seule |
| **EST_COUVERT_PAR** | DOCUMENT → LICENCE | DOCUMENT (1,1) — LICENCE (0,n) | Tout document porte exactement une licence — jamais aucune |
| **EST_DECRIT_PAR** | DOCUMENT ↔ MOT_CLE | DOCUMENT (0,n) — MOT_CLE (0,n) | Un document porte zéro à plusieurs mots-clés |

L'association **COLLECTE** porte deux attributs propres :

| Attribut | Rôle |
|---|---|
| `critere_collecte` | Chemin par lequel le document a été atteint : le tag pour S1, la page pour S2, le fichier pour S3 |
| `vu_le` | Horodatage de cette collecte précise |

C'est ce qui distingue « ce document existe » de « ce document a été vu telle
fois par tel chemin ». Sans cet attribut, les 40 doublons relevés en §2.1
seraient soit perdus, soit dupliqués en base.

---

## 5. Diagramme

```mermaid
erDiagram
    SOURCE {
        texte code_source PK
        texte nom
        enum type_source
        texte url_racine
        texte contraintes_acces
        entier duree_conservation_jours
    }
    EXTRACTION {
        entier id_extraction PK
        texte code_source FK
        horodatage horodatage_debut
        decimal duree_secondes
        enum statut
        entier nb_enregistrements
        entier nb_erreurs
        texte fichier_sortie
    }
    DOCUMENT {
        entier id_document PK
        texte code_source FK
        texte identifiant_source
        texte code_licence FK
        texte titre
        texte contenu
        texte url_source
        enum langue
        horodatage extrait_le
    }
    COLLECTE {
        entier id_extraction FK
        entier id_document FK
        texte critere_collecte
        horodatage vu_le
    }
    LICENCE {
        texte code_licence PK
        texte libelle
        texte url_texte
        booleen redistribution_autorisee
        booleen attribution_requise
    }
    MOT_CLE {
        texte code_mot_cle PK
        enum type_mot_cle
    }
    DESCRIPTION {
        entier id_document FK
        texte code_mot_cle FK
    }
    DOCUMENT_API_REST {
        entier id_document PK
        entier score
        entier nombre_reponses
        entier nombre_vues
        horodatage cree_le
    }
    DOCUMENT_WEB {
        entier id_document PK
        texte page
        texte ancre_section
        texte mention_copyright
    }
    DOCUMENT_FICHIER {
        entier id_document PK
        texte chemin_fichier
        enum format
        texte module_pedagogique
        entier index_section
        texte origine_declaree
    }

    SOURCE   ||--o{ EXTRACTION : "fait l'objet de"
    SOURCE   ||--o{ DOCUMENT   : "fournit"
    LICENCE  ||--o{ DOCUMENT   : "couvre"
    EXTRACTION ||--o{ COLLECTE : "enregistre"
    DOCUMENT   ||--|{ COLLECTE : "est vu dans"
    DOCUMENT   ||--o{ DESCRIPTION : "porte"
    MOT_CLE    ||--o{ DESCRIPTION : "qualifie"
    DOCUMENT   ||--o| DOCUMENT_API_REST : "spécialisation"
    DOCUMENT   ||--o| DOCUMENT_WEB      : "spécialisation"
    DOCUMENT   ||--o| DOCUMENT_FICHIER  : "spécialisation"
```

### Alternative textuelle au diagramme

Le schéma comporte six entités principales et trois spécialisations.

`SOURCE` est au centre : elle alimente `EXTRACTION` (une source, plusieurs
exécutions) et `DOCUMENT` (une source, plusieurs documents). `LICENCE` couvre
`DOCUMENT` : chaque document porte exactement une licence, une licence couvre
plusieurs documents. `EXTRACTION` et `DOCUMENT` sont reliés par l'entité
associative `COLLECTE`, qui matérialise une relation plusieurs-à-plusieurs et
porte le critère de collecte ainsi que l'horodatage. Une extraction peut
n'enregistrer aucune collecte — c'est le cas d'une exécution en échec, qui
reste malgré tout tracée. `MOT_CLE` et `DOCUMENT`
sont reliés par l'entité associative `DESCRIPTION`, également
plusieurs-à-plusieurs. Enfin, `DOCUMENT` se spécialise en trois sous-entités
— `DOCUMENT_API_REST`, `DOCUMENT_WEB` et `DOCUMENT_FICHIER` — chacune reliée
par une relation un-à-zéro-ou-un et portant les attributs propres à son type de
source. Cette notation est une limite de Mermaid : la spécialisation réelle est
une partition, exclusive et totale, décrite au paragraphe 3.

---

## 6. RGPD — ce que le modèle ne contient pas

**Aucune entité « personne », par construction.**

L'API Stack Exchange expose pour chaque question un objet `owner` contenant
`display_name`, `user_id`, `profile_image` et `link` — soit un pseudonyme, un
identifiant persistant et une photo. Ces champs constituent des données à
caractère personnel.

L'extracteur S1 **ne les collecte pas**. Vérifié sur les 1 928 enregistrements
extraits : aucune clé de `metadonnees` ne désigne une personne. L'attribution
exigée par la licence CC BY-SA est assurée par `url_source`, qui pointe vers la
question d'origine où l'auteur est crédité par Stack Overflow lui-même.

C'est l'application directe du principe de **minimisation** de l'article 5.1.c
du RGPD : la donnée n'est pas anonymisée après coup, elle n'est jamais
collectée. Ne pas la détenir dispense des obligations qui suivent — durée de
conservation, droit d'accès, droit d'effacement.

Deux dispositions complémentaires figurent malgré tout dans le modèle :

- `SOURCE.duree_conservation_jours` fixe une durée de conservation par source,
  applicable même en l'absence de données personnelles — un contenu sous
  licence peut devoir être retiré si la licence change ;
- l'entité `EXTRACTION` permet une purge par exécution : supprimer une
  extraction et les documents qu'elle seule a collectés est une opération
  traçable, ce qu'un effacement au fil de l'eau ne serait pas.

Le document `docs/rgpd_eduai_data.md` (étape 3) détaillera finalité, base
légale et procédure d'effacement.

---

## 7. Ce qui est volontairement hors modèle

- **Les chunks et vecteurs du RAG.** ChromaDB est un artefact aval, reconstruit
  à partir de cette base. Le stocker ici dupliquerait la donnée sans bénéfice.
- **Les données de l'application.** Utilisateurs, cours, exercices et quiz
  vivent dans `eduai_app`, base distincte relevant de C17.
- **Le texte transformé.** `DOCUMENT.contenu` porte le contenu tel qu'extrait.
  Les normalisations relevant de C3 produiront leurs propres colonnes ou tables,
  définies à l'étape suivante.

---

## 8. Options écartées

| Option | Raison du rejet |
|---|---|
| Une colonne `metadonnees` en JSONB sur `DOCUMENT` | Aucune contrainte d'intégrité possible, aucun type vérifié, index moins efficaces. C4 attend « des types adaptés, pas du TEXT par défaut partout » — un JSONB fourre-tout est la même faiblesse sous un autre nom |
| Une table par source, sans entité `DOCUMENT` commune | Toute requête transversale au corpus deviendrait une union de cinq tables, et l'ajout de S4 puis S5 imposerait de réécrire ces requêtes |
| Licence portée par `SOURCE` | Contredit par les données : le corpus local porte deux licences distinctes (§2.2) |
| Tags stockés en tableau PostgreSQL sur `DOCUMENT` | Interdit de compter les documents par mot-clé sans dénormaliser à chaque requête, et n'empêche pas les variantes d'écriture d'un même tag |
| `identifiant_source` comme clé primaire | Rien ne garantit l'unicité entre sources ; une clé technique isole le modèle des changements de format d'identifiant côté source |

---

## 9. Arbitrages retenus

Les quatre points laissés ouverts ont été tranchés le 26/08/2026. Ils sont
consignés ici parce qu'ils conditionnent le MLD.

### Durée de conservation

365 jours pour S1, S2 et S5 ; `NULL` — conservation sans terme — pour S3, dont
les droits sont détenus par l'autrice du projet.

Le motif n'est pas juridique : CC BY-SA 4.0 et la licence PSF sont
irrévocables, un retrait de la source ne retire pas le droit d'usage déjà
acquis. Le motif est la **fraîcheur** : une réponse Stack Overflow de plus d'un
an peut décrire une API obsolète, et un tuteur qui la cite induit l'apprenant
en erreur. Le quota n'est pas un frein — S1 a consommé 15 requêtes sur 300
pour produire 1 313 documents, une réextraction annuelle est indolore.

`duree_conservation_jours` est donc **nullable**, et `NULL` y signifie « sans
terme » et non « non renseigné ». Le MLD documentera cette sémantique.

La valeur pour S4 reste à fixer : elle dépendra de la base retenue comme
source, qui n'est pas encore choisie.

### Les 82 documents « A VERIFIER »

Chargés en base avec `redistribution_autorisee = faux`, puis **exclus de
l'indexation RAG par requête**.

Le raisonnement à retenir pour l'oral : afficher un contenu à un utilisateur
est une redistribution. Un document dont on ignore la licence ne peut donc pas
alimenter les réponses du tuteur. Les charger malgré tout les rend dénombrables
et traçables — on peut prouver qu'ils sont écartés, ce qu'un rejet silencieux à
l'import ne permettrait pas.

C'est ce qui donne leur portée réelle aux deux booléens de `LICENCE` : ils ne
documentent pas, ils filtrent.

### Contenu

`contenu` est un texte sans longueur maximale, assorti d'une **contrainte de
non-vacuité**. Le découpage relève de C3, pas du stockage.

Le document le plus long — 149 083 caractères — a été identifié :
`data/contents/resources/python__total_cheatsheet.md`, la *Comprehensive Python
Cheatsheet* du dépôt `gto76/python-cheatsheet`. **Ce n'est pas un artefact
d'extraction.** Le fichier produit un seul enregistrement pour une raison
vérifiée : il ne contient aucun titre ATX (`#`, `##`). Ses 71 titres sont au
format Setext — soulignés par `===` ou `---` — que le découpeur de S3 ne
reconnaît pas. Les 23 lignes commençant par `#` du fichier sont toutes des
commentaires Python situés dans des blocs de code, correctement neutralisés
avant découpage : le mécanisme prévu pour ne pas couper les exemples de code a
fonctionné exactement comme voulu.

Deux conséquences. La première est sans effet ici : ce fichier est justement
l'un des 82 « A VERIFIER », donc écarté de l'indexation — il provient d'un
dépôt tiers. La seconde vaut pour C3 : le découpeur devra gérer les titres
Setext, sans quoi tout document rédigé dans ce style arrivera d'un bloc.

### Historisation des collectes

Toutes les lignes de `COLLECTE` sont conservées. Le coût est négligeable au
regard du volume, et l'historique a une valeur propre : **une chute de
volumétrie entre deux exécutions d'une même source signale un incident** —
sélecteur CSS obsolète, changement de schéma d'API, fichier disparu. C'est une
mesure exploitable pour le suivi en production (E5), obtenue sans instrumenter
quoi que ce soit de plus.
