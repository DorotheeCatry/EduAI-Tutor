# Dictionnaire de données — base `eduai_data`

**Compétence visée :** C4 (épreuve E1)
**Engendré par :** `data_pipeline/load/generer_dictionnaire.py`
**Source :** les scripts de `data_pipeline/load/sql/`, à partir desquels le conteneur PostgreSQL construit la base.

> Ce document est engendré. Ne pas le modifier à la main : toute correction se fait dans les scripts SQL, puis on relance le générateur. C'est ce qui garantit qu'il ne peut pas diverger du schéma réel.

La base compte **13 tables**.

## Vue d'ensemble

| Table | Colonnes | Rôle |
|---|---|---|
| `type_source` | 3 | Les cinq types de sources exigés par le référentiel RNCP 37827 (C1). |
| `licence` | 6 | Conditions de réutilisation des contenus collectés. |
| `source` | 6 | Les cinq sources du pipeline. |
| `mot_cle` | 2 | Mots-clés qualifiant les documents, tous sources confondues. |
| `extraction` | 8 | Une exécution d'un extracteur. |
| `document` | 11 | Unité de contenu collectée, quelle que soit la source : une question et sa réponse acceptée, une section de documentation, une section de cours. |
| `document_api_rest` | 6 | Attributs propres aux documents issus d'un service web. |
| `document_web` | 4 | Attributs propres aux documents obtenus par scraping. |
| `document_fichier` | 7 | Attributs propres aux documents lus dans des fichiers. |
| `document_base_donnees` | 2 | Sous-entité de la partition pour la source de type base de données (S4). |
| `document_big_data` | 2 | Sous-entité de la partition pour la source de type big data (S5). |
| `collecte` | 5 | Acte de collecte d'un document par une exécution, selon un critère donné. |
| `description` | 2 | Association entre un document et les mots-clés qui le qualifient. |

---

## `type_source`

Les cinq types de sources exigés par le référentiel RNCP 37827 (C1).

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `code_type_source` | `VARCHAR(20)` | PK | oui | Identifiant du type : api_rest, scraping, fichier, base_donnees, big_data. |
| `libelle` | `VARCHAR(80)` | — | oui | Libellé lisible du type, affiché dans les rapports. |
| `description` | `TEXT` | — | oui | Définition du type au sens du référentiel, pour lever toute ambiguïté de classement. |

### Contraintes de `type_source`

- `CONSTRAINT type_source_pk PRIMARY KEY (code_type_source)`

---

## `licence`

Conditions de réutilisation des contenus collectés. Une licence couvre plusieurs documents.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `code_licence` | `VARCHAR(20)` | PK | oui | Identifiant court de la licence : CC-BY-SA-4.0, PSF, PROPRIETAIRE, A_VERIFIER. |
| `libelle` | `VARCHAR(150)` | — | oui | Intitulé complet de la licence. |
| `url_texte` | `VARCHAR(255)` | — | non | Adresse du texte de référence. Nul pour les licences sans texte publié. |
| `redistribution_autorisee` | `BOOLEAN` | — | oui | Faux interdit toute diffusion du contenu à un utilisateur, indexation RAG comprise : afficher un contenu est une redistribution. |
| `attribution_requise` | `BOOLEAN` | — | oui | Vrai impose que le document porte une url_source permettant de créditer la source. |
| `mention_copyright` | `VARCHAR(255)` | — | non | Notice fixe imposée par certaines licences, la PSF notamment. Attribut de la licence, non du document. |

### Contraintes de `licence`

- `CONSTRAINT licence_pk PRIMARY KEY (code_licence)`
- `CONSTRAINT licence_attribution_uk UNIQUE (code_licence, attribution_requise)`

---

## `source`

Les cinq sources du pipeline. Table de faible cardinalité mais structurante : elle rend la couverture des cinq types vérifiable par une requête.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `code_source` | `CHAR(2)` | PK | oui | Identifiant naturel de la source, de s1 à s5. |
| `nom` | `VARCHAR(100)` | — | oui | Nom lisible de la source, tel qu'il apparaît dans les rapports d'exécution. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Type de source au sens du référentiel. Recopié dans document pour rendre la partition déclarative. |
| `url_racine` | `VARCHAR(255)` | — | non | Point d'entrée de la source. Nul pour une source locale. |
| `contraintes_acces` | `TEXT` | — | oui | Quota, robots.txt, conditions d'utilisation. Documenté car C1 exige la consultation des contraintes de la source. |
| `duree_conservation_jours` | `SMALLINT` | — | non | Durée de conservation des documents. NULL signifie « sans terme », et non « non renseigné » : les droits sont détenus. |

### Contraintes de `source`

- `CONSTRAINT source_pk PRIMARY KEY (code_source)`
- `CONSTRAINT source_nom_uk UNIQUE (nom)`
- `CONSTRAINT source_type_fk FOREIGN KEY (code_type_source) REFERENCES type_source (code_type_source)`
- `CONSTRAINT source_type_uk UNIQUE (code_source, code_type_source)`
- `CONSTRAINT source_code_valide CHECK (code_source ~ '^s[1-5]$')`
- `CONSTRAINT source_conservation_positive CHECK (duree_conservation_jours IS NULL OR duree_conservation_jours > 0)`

---

## `mot_cle`

Mots-clés qualifiant les documents, tous sources confondues. Sert au filtrage thématique du RAG.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `code_mot_cle` | `VARCHAR(60)` | PK | oui | Forme normalisée du mot-clé, en minuscules. |
| `categorie` | `categorie_mot_cle` | — | oui | tag_source pour un mot-clé subi, issu de la source ; module pour une classification choisie par le projet. |

### Contraintes de `mot_cle`

- `CONSTRAINT mot_cle_pk PRIMARY KEY (code_mot_cle)`
- `CONSTRAINT mot_cle_minuscules CHECK (code_mot_cle = lower(code_mot_cle))`
- `CONSTRAINT mot_cle_non_vide CHECK (btrim(code_mot_cle) <> '')`

---

## `extraction`

Une exécution d'un extracteur. Sert la traçabilité C1, la détection d'incident par comparaison de volumétrie, et l'ancrage de la purge sur une date d'extraction.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_extraction` | `INTEGER (identité)` | PK | oui | Clé technique de l'exécution, engendrée par la base. |
| `code_source` | `CHAR(2)` | FK | oui | Source sur laquelle porte l'exécution. |
| `horodatage_debut` | `TIMESTAMPTZ` | — | oui | Début de l'exécution, avec fuseau. Forme avec code_source la clé d'idempotence du chargement. |
| `duree_secondes` | `NUMERIC(10,2)` | — | oui | Durée totale de l'exécution. Une dérive dans le temps signale une source qui ralentit. |
| `statut` | `statut_extraction` | — | oui | succes ou echec. Un echec est conservé : c'est une information, pas un déchet. |
| `nb_enregistrements` | `INTEGER` | — | oui | Volumétrie produite. Une chute par rapport à l'exécution précédente signale un incident de collecte. |
| `nb_erreurs` | `INTEGER` | — | oui | Erreurs tolérées pendant l'exécution, sans interruption du traitement. |
| `fichier_sortie` | `VARCHAR(255)` | — | oui | Chemin du fichier JSON Lines brut, pour rejouer la transformation sans réextraire. |

### Contraintes de `extraction`

- `CONSTRAINT extraction_pk PRIMARY KEY (id_extraction)`
- `CONSTRAINT extraction_source_fk FOREIGN KEY (code_source) REFERENCES source (code_source)`
- `CONSTRAINT extraction_unicite UNIQUE (code_source, horodatage_debut)`
- `CONSTRAINT extraction_duree_positive CHECK (duree_secondes >= 0)`
- `CONSTRAINT extraction_volume_positif CHECK (nb_enregistrements >= 0)`
- `CONSTRAINT extraction_erreurs_positif CHECK (nb_erreurs >= 0)`
- `CONSTRAINT extraction_succes_non_vide CHECK (statut = 'echec' OR nb_enregistrements > 0)`

---

## `document`

Unité de contenu collectée, quelle que soit la source : une question et sa réponse acceptée, une section de documentation, une section de cours.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER (identité)` | PK | oui | Clé technique du document, engendrée par la base. Préférée à l'identifiant de la source, dont le format peut changer sans préavis. |
| `code_source` | `CHAR(2)` | FK | oui | Source dont provient le document. Référencée conjointement avec code_type_source, par une clé étrangère composite. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Recopie contrôlée du type de la source. Dépendance transitive assumée : sans elle, l'exclusivité de la partition ne serait pas déclarative. |
| `identifiant_source` | `VARCHAR(120)` | — | oui | Identifiant stable côté source. Forme avec code_source la clé naturelle du document. |
| `code_licence` | `VARCHAR(20)` | FK | oui | Licence couvrant le document. Référencée conjointement avec attribution_requise, par une clé étrangère composite. |
| `attribution_requise` | `BOOLEAN` | FK | oui | Recopie contrôlée du booléen de la licence, pour la même raison : elle rend locale la contrainte sur url_source. |
| `titre` | `VARCHAR(255)` | — | oui | Titre du document. Non vide après suppression des espaces. |
| `contenu` | `TEXT` | — | oui | Contenu tel qu'extrait, sans longueur maximale. Le découpage en fragments relève de la transformation (C3). |
| `url_source` | `VARCHAR(500)` | — | non | Adresse permettant de citer la source. Obligatoire si la licence exige l'attribution. |
| `langue` | `langue_document` | — | oui | Langue du contenu. Sert au filtrage : le tuteur ne cite pas une source anglaise à une question posée en français sans le signaler. |
| `extrait_le` | `TIMESTAMPTZ` | — | oui | Date de première collecte du document. Les collectes suivantes sont enregistrées dans collecte. |

### Contraintes de `document`

- `CONSTRAINT document_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_source_fk FOREIGN KEY (code_source, code_type_source) REFERENCES source (code_source, code_type_source)`
- `CONSTRAINT document_licence_fk FOREIGN KEY (code_licence, attribution_requise) REFERENCES licence (code_licence, attribution_requise)`
- `CONSTRAINT document_cle_naturelle UNIQUE (code_source, identifiant_source)`
- `CONSTRAINT document_partition_uk UNIQUE (id_document, code_type_source)`
- `CONSTRAINT document_titre_non_vide CHECK (btrim(titre) <> '')`
- `CONSTRAINT document_contenu_non_vide CHECK (btrim(contenu) <> '')`
- `CONSTRAINT document_attribution_url CHECK (NOT attribution_requise OR url_source IS NOT NULL)`

---

## `document_api_rest`

Attributs propres aux documents issus d'un service web. Sous-entité de la partition de document.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document dont cette ligne porte les attributs propres. Clé primaire et clé étrangère à la fois : la sous-entité n'a pas d'existence indépendante. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Contraint à api_rest. C'est cette colonne qui, via la clé étrangère composite, rend l'exclusivité de la partition déclarative. |
| `score` | `INTEGER` | — | oui | Votes de la communauté. INTEGER et non SMALLINT : le maximum observé est 13 135, mais les questions les plus consultées dépassent la borne des 32 767. Aucune contrainte de positivité, un score peut être négatif. |
| `nombre_reponses` | `SMALLINT` | — | oui | Nombre de réponses. SMALLINT suffit largement : maximum observé 69. |
| `nombre_vues` | `INTEGER` | — | oui | Nombre de consultations. INTEGER obligatoire : maximum observé 8 105 583. |
| `cree_le` | `TIMESTAMPTZ` | — | oui | Date de création de la question sur la source. Fournie en secondes Unix par l'API, convertie à la transformation. |

### Contraintes de `document_api_rest`

- `CONSTRAINT document_api_rest_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_api_rest_type CHECK (code_type_source = 'api_rest')`
- `CONSTRAINT document_api_rest_fk FOREIGN KEY (id_document, code_type_source) REFERENCES document (id_document, code_type_source) ON DELETE CASCADE`
- `CONSTRAINT document_api_rest_reponses CHECK (nombre_reponses >= 0)`
- `CONSTRAINT document_api_rest_vues CHECK (nombre_vues >= 0)`

---

## `document_web`

Attributs propres aux documents obtenus par scraping. Sous-entité de la partition de document.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document dont cette ligne porte les attributs propres. Clé primaire et clé étrangère à la fois. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Contraint à scraping. Support de l'exclusivité de la partition. |
| `page` | `VARCHAR(255)` | — | oui | Chemin de la page d'origine sur le site source. |
| `ancre_section` | `VARCHAR(255)` | — | non | Identifiant HTML de la section, qui permet le lien profond. Nullable : une section sans attribut id reste possible. |

### Contraintes de `document_web`

- `CONSTRAINT document_web_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_web_type CHECK (code_type_source = 'scraping')`
- `CONSTRAINT document_web_fk FOREIGN KEY (id_document, code_type_source) REFERENCES document (id_document, code_type_source) ON DELETE CASCADE`

---

## `document_fichier`

Attributs propres aux documents lus dans des fichiers. Sous-entité de la partition de document.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document dont cette ligne porte les attributs propres. Clé primaire et clé étrangère à la fois. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Contraint à fichier. Support de l'exclusivité de la partition. |
| `chemin_fichier` | `VARCHAR(255)` | — | oui | Chemin relatif du fichier dans le corpus. |
| `format` | `format_fichier` | — | oui | Format du fichier d'origine, qui détermine le lecteur employé à l'extraction. |
| `module_pedagogique` | `VARCHAR(50)` | — | oui | Module d'origine dans l'arborescence du corpus. Sert au filtrage thématique. |
| `index_section` | `SMALLINT` | — | oui | Rang de la section dans son fichier, qui restitue l'ordre de lecture. |
| `origine_declaree` | `VARCHAR(255)` | — | oui | Provenance déclarée dans le manifeste data/contents/provenance.json. |

### Contraintes de `document_fichier`

- `CONSTRAINT document_fichier_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_fichier_type CHECK (code_type_source = 'fichier')`
- `CONSTRAINT document_fichier_fk FOREIGN KEY (id_document, code_type_source) REFERENCES document (id_document, code_type_source) ON DELETE CASCADE`
- `CONSTRAINT document_fichier_index_positif CHECK (index_section >= 0)`

---

## `document_base_donnees`

Sous-entité de la partition pour la source de type base de données (S4). Créée vide et sans attribut propre : l'extracteur n'existe pas encore, mais son absence ferait échouer le premier chargement sur la contrainte de partition.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document dont cette ligne porte les attributs propres. Clé primaire et clé étrangère à la fois. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Contraint à base_donnees. Support de l'exclusivité de la partition. |

### Contraintes de `document_base_donnees`

- `CONSTRAINT document_base_donnees_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_base_donnees_type CHECK (code_type_source = 'base_donnees')`
- `CONSTRAINT document_base_donnees_fk FOREIGN KEY (id_document, code_type_source) REFERENCES document (id_document, code_type_source) ON DELETE CASCADE`

---

## `document_big_data`

Sous-entité de la partition pour la source de type big data (S5). Créée vide pour la même raison que document_base_donnees.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document dont cette ligne porte les attributs propres. Clé primaire et clé étrangère à la fois. |
| `code_type_source` | `VARCHAR(20)` | FK | oui | Contraint à big_data. Support de l'exclusivité de la partition. |

### Contraintes de `document_big_data`

- `CONSTRAINT document_big_data_pk PRIMARY KEY (id_document)`
- `CONSTRAINT document_big_data_type CHECK (code_type_source = 'big_data')`
- `CONSTRAINT document_big_data_fk FOREIGN KEY (id_document, code_type_source) REFERENCES document (id_document, code_type_source) ON DELETE CASCADE`

---

## `collecte`

Acte de collecte d'un document par une exécution, selon un critère donné. Historisée intégralement : une chute de volumétrie entre deux exécutions signale un incident.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_collecte` | `INTEGER (identité)` | PK | oui | Clé technique de la collecte. Préférée au triplet naturel (extraction, document, critère), qui serait recopié dans chaque index. |
| `id_extraction` | `INTEGER` | FK | oui | Exécution au cours de laquelle le document a été vu. Suppression en RESTRICT : l'historique ne s'efface pas par effet de bord. |
| `id_document` | `INTEGER` | FK | oui | Document collecté. Suppression en CASCADE : une collecte sans document n'a aucun sens. |
| `critere_collecte` | `VARCHAR(200)` | — | oui | Chemin par lequel le document a été atteint : le tag pour un service web, la page pour du scraping, le fichier pour une source locale. Non nullable, une source étant toujours interrogée par un chemin. |
| `vu_le` | `TIMESTAMPTZ` | — | oui | Horodatage de cette collecte précise, distinct de la date de première extraction du document. |

### Contraintes de `collecte`

- `CONSTRAINT collecte_pk PRIMARY KEY (id_collecte)`
- `CONSTRAINT collecte_extraction_fk FOREIGN KEY (id_extraction) REFERENCES extraction (id_extraction) ON DELETE RESTRICT`
- `CONSTRAINT collecte_document_fk FOREIGN KEY (id_document) REFERENCES document (id_document) ON DELETE CASCADE`
- `CONSTRAINT collecte_unicite UNIQUE (id_extraction, id_document, critere_collecte)`
- `CONSTRAINT collecte_critere_non_vide CHECK (btrim(critere_collecte) <> '')`

---

## `description`

Association entre un document et les mots-clés qui le qualifient. Relation pure, sans attribut propre.

| Colonne | Type | Clé | Obligatoire | Description |
|---|---|---|---|---|
| `id_document` | `INTEGER` | PK, FK | oui | Document qualifié par le mot-clé. |
| `code_mot_cle` | `VARCHAR(60)` | PK, FK | oui | Mot-clé qualifiant le document. Suppression en RESTRICT : un mot-clé encore employé ne se supprime pas par mégarde. |

### Contraintes de `description`

- `CONSTRAINT description_pk PRIMARY KEY (id_document, code_mot_cle)`
- `CONSTRAINT description_document_fk FOREIGN KEY (id_document) REFERENCES document (id_document) ON DELETE CASCADE`
- `CONSTRAINT description_mot_cle_fk FOREIGN KEY (code_mot_cle) REFERENCES mot_cle (code_mot_cle) ON DELETE RESTRICT`
