/*
 * Schéma physique de la base eduai_data.
 *
 * Compétence visée : C4 (épreuve E1) — modèle physique de données
 * Source : docs/mld_eduai_data.md, validé le 26/08/2026
 *
 * Contenu : domaines énumérés, tables de référence, tables principales,
 * spécialisations de document, tables d'association. Les index sont dans
 * 02_index.sql, les contraintes procédurales dans 03_contraintes.sql, les
 * données de référence dans 04_donnees_reference.sql.
 *
 * L'ordre des créations suit les dépendances de clés étrangères : rien n'est
 * référencé avant d'exister.
 *
 * Les commentaires SQL (COMMENT ON) ne sont pas décoratifs : le dictionnaire
 * de données de docs/ est engendré à partir d'eux, ce qui interdit qu'il
 * diverge du schéma réel.
 */

-- ===========================================================================
-- 1. Domaines énumérés
-- ===========================================================================
--
-- Choix : ENUM natif pour les domaines fermés et stables, table de référence
-- pour type_source. Motivation : un ENUM est compact, trié dans l'ordre de
-- déclaration et vérifié par le moteur, mais ajouter une valeur exige un
-- ALTER TYPE. C'est acceptable pour des domaines qui ne bougeront pas —
-- une extraction réussit ou échoue, un fichier est .md, .pdf ou .ipynb.
-- type_source échappe à cette règle : ses cinq valeurs sont fixées par le
-- référentiel mais elles portent un libellé et une description, ce qu'un ENUM
-- ne sait pas transporter.

CREATE TYPE statut_extraction AS ENUM ('succes', 'echec');
CREATE TYPE langue_document  AS ENUM ('fr', 'en');
CREATE TYPE format_fichier   AS ENUM ('md', 'pdf', 'ipynb');
CREATE TYPE categorie_mot_cle AS ENUM ('tag_source', 'module');


-- ===========================================================================
-- 2. Tables de référence
-- ===========================================================================

-- --- 2.1 Types de source -----------------------------------------------------
-- Les cinq types exigés par le référentiel. Table figée : son contenu est une
-- exigence d'évaluation, pas une donnée métier.

CREATE TABLE type_source (
    code_type_source  VARCHAR(20)  NOT NULL,
    libelle           VARCHAR(80)  NOT NULL,
    description       TEXT         NOT NULL,

    CONSTRAINT type_source_pk PRIMARY KEY (code_type_source)
);

COMMENT ON TABLE  type_source IS
    'Les cinq types de sources exigés par le référentiel RNCP 37827 (C1).';
COMMENT ON COLUMN type_source.code_type_source IS
    'Identifiant du type : api_rest, scraping, fichier, base_donnees, big_data.';
COMMENT ON COLUMN type_source.libelle IS
    'Libellé lisible du type, affiché dans les rapports.';
COMMENT ON COLUMN type_source.description IS
    'Définition du type au sens du référentiel, pour lever toute ambiguïté de classement.';


-- --- 2.2 Licences ------------------------------------------------------------
-- Les deux booléens ne documentent pas, ils filtrent : ce sont eux qui
-- écartent de l'indexation les documents qu'on n'a pas le droit de rediffuser.

CREATE TABLE licence (
    code_licence              VARCHAR(20)  NOT NULL,
    libelle                   VARCHAR(150) NOT NULL,
    url_texte                 VARCHAR(255),
    redistribution_autorisee  BOOLEAN      NOT NULL,
    attribution_requise       BOOLEAN      NOT NULL,
    mention_copyright         VARCHAR(255),

    CONSTRAINT licence_pk PRIMARY KEY (code_licence),

    -- Support de la clé étrangère composite portée par document. Sans cette
    -- contrainte, la règle « attribution requise implique URL renseignée » ne
    -- pourrait pas être déclarative.
    CONSTRAINT licence_attribution_uk UNIQUE (code_licence, attribution_requise)
);

COMMENT ON TABLE  licence IS
    'Conditions de réutilisation des contenus collectés. Une licence couvre plusieurs documents.';
COMMENT ON COLUMN licence.code_licence IS
    'Identifiant court de la licence : CC-BY-SA-4.0, PSF, PROPRIETAIRE, A_VERIFIER.';
COMMENT ON COLUMN licence.libelle IS
    'Intitulé complet de la licence.';
COMMENT ON COLUMN licence.url_texte IS
    'Adresse du texte de référence. Nul pour les licences sans texte publié.';
COMMENT ON COLUMN licence.redistribution_autorisee IS
    'Faux interdit toute diffusion du contenu à un utilisateur, indexation RAG comprise : afficher un contenu est une redistribution.';
COMMENT ON COLUMN licence.attribution_requise IS
    'Vrai impose que le document porte une url_source permettant de créditer la source.';
COMMENT ON COLUMN licence.mention_copyright IS
    'Notice fixe imposée par certaines licences, la PSF notamment. Attribut de la licence, non du document.';


-- --- 2.3 Sources -------------------------------------------------------------

CREATE TABLE source (
    code_source               CHAR(2)      NOT NULL,
    nom                       VARCHAR(100) NOT NULL,
    code_type_source          VARCHAR(20)  NOT NULL,
    url_racine                VARCHAR(255),
    contraintes_acces         TEXT         NOT NULL,
    duree_conservation_jours  SMALLINT,

    CONSTRAINT source_pk        PRIMARY KEY (code_source),
    CONSTRAINT source_nom_uk    UNIQUE (nom),
    CONSTRAINT source_type_fk   FOREIGN KEY (code_type_source)
        REFERENCES type_source (code_type_source),

    -- Support de la clé étrangère composite portée par document : c'est elle
    -- qui rend l'exclusivité de la partition déclarative.
    CONSTRAINT source_type_uk   UNIQUE (code_source, code_type_source),

    CONSTRAINT source_code_valide
        CHECK (code_source ~ '^s[1-5]$'),
    CONSTRAINT source_conservation_positive
        CHECK (duree_conservation_jours IS NULL OR duree_conservation_jours > 0)
);

COMMENT ON TABLE  source IS
    'Les cinq sources du pipeline. Table de faible cardinalité mais structurante : elle rend la couverture des cinq types vérifiable par une requête.';
COMMENT ON COLUMN source.code_source IS
    'Identifiant naturel de la source, de s1 à s5.';
COMMENT ON COLUMN source.nom IS
    'Nom lisible de la source, tel qu''il apparaît dans les rapports d''exécution.';
COMMENT ON COLUMN source.code_type_source IS
    'Type de source au sens du référentiel. Recopié dans document pour rendre la partition déclarative.';
COMMENT ON COLUMN source.url_racine IS
    'Point d''entrée de la source. Nul pour une source locale.';
COMMENT ON COLUMN source.contraintes_acces IS
    'Quota, robots.txt, conditions d''utilisation. Documenté car C1 exige la consultation des contraintes de la source.';
COMMENT ON COLUMN source.duree_conservation_jours IS
    'Durée de conservation des documents. NULL signifie « sans terme », et non « non renseigné » : les droits sont détenus.';


-- --- 2.4 Mots-clés -----------------------------------------------------------

CREATE TABLE mot_cle (
    code_mot_cle   VARCHAR(60)       NOT NULL,
    categorie      categorie_mot_cle NOT NULL,

    CONSTRAINT mot_cle_pk PRIMARY KEY (code_mot_cle),

    -- La normalisation en minuscules est garantie par la base, pas seulement
    -- appliquée à l'import : sans cela, « SQL » et « sql » deviendraient deux
    -- mots-clés distincts au premier extracteur qui ne normaliserait pas.
    CONSTRAINT mot_cle_minuscules CHECK (code_mot_cle = lower(code_mot_cle)),
    CONSTRAINT mot_cle_non_vide   CHECK (btrim(code_mot_cle) <> '')
);

COMMENT ON TABLE  mot_cle IS
    'Mots-clés qualifiant les documents, tous sources confondues. Sert au filtrage thématique du RAG.';
COMMENT ON COLUMN mot_cle.code_mot_cle IS
    'Forme normalisée du mot-clé, en minuscules.';
COMMENT ON COLUMN mot_cle.categorie IS
    'tag_source pour un mot-clé subi, issu de la source ; module pour une classification choisie par le projet.';


-- ===========================================================================
-- 3. Tables principales
-- ===========================================================================

-- --- 3.1 Extractions ---------------------------------------------------------
-- Une ligne par exécution d'un extracteur. Matérialise le bilan que
-- ExtracteurBase.executer() se contente aujourd'hui de journaliser.

CREATE TABLE extraction (
    id_extraction       INTEGER       GENERATED ALWAYS AS IDENTITY,
    code_source         CHAR(2)       NOT NULL,
    horodatage_debut    TIMESTAMPTZ   NOT NULL,
    duree_secondes      NUMERIC(10,2) NOT NULL,
    statut              statut_extraction NOT NULL,
    nb_enregistrements  INTEGER       NOT NULL,
    nb_erreurs          INTEGER       NOT NULL,
    fichier_sortie      VARCHAR(255)  NOT NULL,

    CONSTRAINT extraction_pk PRIMARY KEY (id_extraction),
    CONSTRAINT extraction_source_fk FOREIGN KEY (code_source)
        REFERENCES source (code_source),

    -- Idempotence du chargement : rejouer l'import d'un même bilan ne crée pas
    -- une seconde exécution fantôme.
    CONSTRAINT extraction_unicite UNIQUE (code_source, horodatage_debut),

    CONSTRAINT extraction_duree_positive  CHECK (duree_secondes >= 0),
    CONSTRAINT extraction_volume_positif  CHECK (nb_enregistrements >= 0),
    CONSTRAINT extraction_erreurs_positif CHECK (nb_erreurs >= 0),

    -- Une extraction ne peut pas réussir en ne produisant rien.
    -- Contrainte tirée d'un incident réel : avant correction, l'extracteur S1
    -- utilisait un filtre d'API qui ne renvoyait ni le corps des questions ni
    -- les réponses. Le bilan annonçait « succes, 0 enregistrement » — un échec
    -- silencieux que cette contrainte aurait transformé en erreur bruyante.
    CONSTRAINT extraction_succes_non_vide
        CHECK (statut = 'echec' OR nb_enregistrements > 0)
);

COMMENT ON TABLE  extraction IS
    'Une exécution d''un extracteur. Sert la traçabilité C1, la détection d''incident par comparaison de volumétrie, et l''ancrage de la purge sur une date d''extraction.';
COMMENT ON COLUMN extraction.horodatage_debut IS
    'Début de l''exécution, avec fuseau. Forme avec code_source la clé d''idempotence du chargement.';
COMMENT ON COLUMN extraction.duree_secondes IS
    'Durée totale de l''exécution. Une dérive dans le temps signale une source qui ralentit.';
COMMENT ON COLUMN extraction.statut IS
    'succes ou echec. Un echec est conservé : c''est une information, pas un déchet.';
COMMENT ON COLUMN extraction.nb_enregistrements IS
    'Volumétrie produite. Une chute par rapport à l''exécution précédente signale un incident de collecte.';
COMMENT ON COLUMN extraction.nb_erreurs IS
    'Erreurs tolérées pendant l''exécution, sans interruption du traitement.';
COMMENT ON COLUMN extraction.fichier_sortie IS
    'Chemin du fichier JSON Lines brut, pour rejouer la transformation sans réextraire.';


-- --- 3.2 Documents -----------------------------------------------------------

CREATE TABLE document (
    id_document          INTEGER      GENERATED ALWAYS AS IDENTITY,
    code_source          CHAR(2)      NOT NULL,
    code_type_source     VARCHAR(20)  NOT NULL,
    identifiant_source   VARCHAR(120) NOT NULL,
    code_licence         VARCHAR(20)  NOT NULL,
    attribution_requise  BOOLEAN      NOT NULL,
    titre                VARCHAR(255) NOT NULL,
    contenu              TEXT         NOT NULL,
    url_source           VARCHAR(500),
    langue               langue_document NOT NULL,
    extrait_le           TIMESTAMPTZ  NOT NULL,

    CONSTRAINT document_pk PRIMARY KEY (id_document),

    -- Clé étrangère composite, et non deux clés séparées : elle garantit à la
    -- fois l'intégrité référentielle de code_source et la cohérence de
    -- code_type_source avec sa source. Une clé supplémentaire sur code_source
    -- seul serait redondante et coûterait un index de plus.
    CONSTRAINT document_source_fk FOREIGN KEY (code_source, code_type_source)
        REFERENCES source (code_source, code_type_source),

    -- Même mécanisme : attribution_requise ne peut pas diverger de sa licence.
    CONSTRAINT document_licence_fk FOREIGN KEY (code_licence, attribution_requise)
        REFERENCES licence (code_licence, attribution_requise),

    -- Clé naturelle. L'unicité porte sur le couple et non sur
    -- identifiant_source seul : rien ne garantit qu'un identifiant Stack
    -- Overflow ne collisionne jamais avec un identifiant du corpus local.
    CONSTRAINT document_cle_naturelle UNIQUE (code_source, identifiant_source),

    -- Support des clés étrangères composites des tables filles.
    CONSTRAINT document_partition_uk UNIQUE (id_document, code_type_source),

    CONSTRAINT document_titre_non_vide   CHECK (btrim(titre) <> ''),
    CONSTRAINT document_contenu_non_vide CHECK (btrim(contenu) <> ''),

    -- Grâce à la recopie d'attribution_requise, cette règle est locale à la
    -- ligne, donc entièrement déclarative. Sans elle, un document sous licence
    -- CC BY-SA pourrait être chargé sans moyen de créditer son auteur.
    CONSTRAINT document_attribution_url
        CHECK (NOT attribution_requise OR url_source IS NOT NULL)
);

COMMENT ON TABLE  document IS
    'Unité de contenu collectée, quelle que soit la source : une question et sa réponse acceptée, une section de documentation, une section de cours.';
COMMENT ON COLUMN document.identifiant_source IS
    'Identifiant stable côté source. Forme avec code_source la clé naturelle du document.';
COMMENT ON COLUMN document.code_type_source IS
    'Recopie contrôlée du type de la source. Dépendance transitive assumée : sans elle, l''exclusivité de la partition ne serait pas déclarative.';
COMMENT ON COLUMN document.attribution_requise IS
    'Recopie contrôlée du booléen de la licence, pour la même raison : elle rend locale la contrainte sur url_source.';
COMMENT ON COLUMN document.titre IS
    'Titre du document. Non vide après suppression des espaces.';
COMMENT ON COLUMN document.contenu IS
    'Contenu tel qu''extrait, sans longueur maximale. Le découpage en fragments relève de la transformation (C3).';
COMMENT ON COLUMN document.url_source IS
    'Adresse permettant de citer la source. Obligatoire si la licence exige l''attribution.';
COMMENT ON COLUMN document.langue IS
    'Langue du contenu. Sert au filtrage : le tuteur ne cite pas une source anglaise à une question posée en français sans le signaler.';
COMMENT ON COLUMN document.extrait_le IS
    'Date de première collecte du document. Les collectes suivantes sont enregistrées dans collecte.';


-- ===========================================================================
-- 4. Spécialisations de document
-- ===========================================================================
--
-- Partition exclusive et totale. L'exclusivité est déclarative : chaque table
-- fille contraint code_type_source par un CHECK et référence le couple
-- (id_document, code_type_source) de la mère. Un document issu du scraping ne
-- peut donc pas obtenir de ligne dans document_api_rest — la clé étrangère
-- composite ne trouverait aucune ligne mère correspondante.
--
-- La totalité, qu'aucune contrainte déclarative n'exprime en SQL, est traitée
-- dans 03_contraintes.sql.
--
-- Les cinq tables sont créées ici, y compris celles de S4 et S5 dont les
-- extracteurs n'existent pas. Motivation : les scripts de
-- /docker-entrypoint-initdb.d ne s'exécutent qu'au premier démarrage du
-- volume. Créer ces tables plus tard imposerait un « docker compose down -v »,
-- donc la perte des données déjà chargées.

CREATE TABLE document_api_rest (
    id_document       INTEGER     NOT NULL,
    code_type_source  VARCHAR(20) NOT NULL,
    score             INTEGER     NOT NULL,
    nombre_reponses   SMALLINT    NOT NULL,
    nombre_vues       INTEGER     NOT NULL,
    cree_le           TIMESTAMPTZ NOT NULL,

    CONSTRAINT document_api_rest_pk PRIMARY KEY (id_document),
    CONSTRAINT document_api_rest_type CHECK (code_type_source = 'api_rest'),
    CONSTRAINT document_api_rest_fk FOREIGN KEY (id_document, code_type_source)
        REFERENCES document (id_document, code_type_source) ON DELETE CASCADE,

    CONSTRAINT document_api_rest_reponses CHECK (nombre_reponses >= 0),
    CONSTRAINT document_api_rest_vues     CHECK (nombre_vues >= 0)
);

COMMENT ON TABLE  document_api_rest IS
    'Attributs propres aux documents issus d''un service web. Sous-entité de la partition de document.';
COMMENT ON COLUMN document_api_rest.score IS
    'Votes de la communauté. INTEGER et non SMALLINT : le maximum observé est 13 135, mais les questions les plus consultées dépassent la borne des 32 767. Aucune contrainte de positivité, un score peut être négatif.';
COMMENT ON COLUMN document_api_rest.nombre_reponses IS
    'Nombre de réponses. SMALLINT suffit largement : maximum observé 69.';
COMMENT ON COLUMN document_api_rest.nombre_vues IS
    'Nombre de consultations. INTEGER obligatoire : maximum observé 8 105 583.';
COMMENT ON COLUMN document_api_rest.cree_le IS
    'Date de création de la question sur la source. Fournie en secondes Unix par l''API, convertie à la transformation.';


CREATE TABLE document_web (
    id_document       INTEGER      NOT NULL,
    code_type_source  VARCHAR(20)  NOT NULL,
    page              VARCHAR(255) NOT NULL,
    ancre_section     VARCHAR(255),

    CONSTRAINT document_web_pk PRIMARY KEY (id_document),
    CONSTRAINT document_web_type CHECK (code_type_source = 'scraping'),
    CONSTRAINT document_web_fk FOREIGN KEY (id_document, code_type_source)
        REFERENCES document (id_document, code_type_source) ON DELETE CASCADE
);

COMMENT ON TABLE  document_web IS
    'Attributs propres aux documents obtenus par scraping. Sous-entité de la partition de document.';
COMMENT ON COLUMN document_web.page IS
    'Chemin de la page d''origine sur le site source.';
COMMENT ON COLUMN document_web.ancre_section IS
    'Identifiant HTML de la section, qui permet le lien profond. Nullable : une section sans attribut id reste possible.';


CREATE TABLE document_fichier (
    id_document        INTEGER        NOT NULL,
    code_type_source   VARCHAR(20)    NOT NULL,
    chemin_fichier     VARCHAR(255)   NOT NULL,
    format             format_fichier NOT NULL,
    module_pedagogique VARCHAR(50)    NOT NULL,
    index_section      SMALLINT       NOT NULL,
    origine_declaree   VARCHAR(255)   NOT NULL,

    CONSTRAINT document_fichier_pk PRIMARY KEY (id_document),
    CONSTRAINT document_fichier_type CHECK (code_type_source = 'fichier'),
    CONSTRAINT document_fichier_fk FOREIGN KEY (id_document, code_type_source)
        REFERENCES document (id_document, code_type_source) ON DELETE CASCADE,

    CONSTRAINT document_fichier_index_positif CHECK (index_section >= 0)
);

COMMENT ON TABLE  document_fichier IS
    'Attributs propres aux documents lus dans des fichiers. Sous-entité de la partition de document.';
COMMENT ON COLUMN document_fichier.chemin_fichier IS
    'Chemin relatif du fichier dans le corpus.';
COMMENT ON COLUMN document_fichier.format IS
    'Format du fichier d''origine, qui détermine le lecteur employé à l''extraction.';
COMMENT ON COLUMN document_fichier.module_pedagogique IS
    'Module d''origine dans l''arborescence du corpus. Sert au filtrage thématique.';
COMMENT ON COLUMN document_fichier.index_section IS
    'Rang de la section dans son fichier, qui restitue l''ordre de lecture.';
COMMENT ON COLUMN document_fichier.origine_declaree IS
    'Provenance déclarée dans le manifeste data/contents/provenance.json.';


-- Tables filles de S4 et S5 : armature de la partition seule. Leurs attributs
-- propres seront ajoutés par ALTER TABLE quand ces extracteurs existeront.

CREATE TABLE document_base_donnees (
    id_document       INTEGER     NOT NULL,
    code_type_source  VARCHAR(20) NOT NULL,

    CONSTRAINT document_base_donnees_pk PRIMARY KEY (id_document),
    CONSTRAINT document_base_donnees_type CHECK (code_type_source = 'base_donnees'),
    CONSTRAINT document_base_donnees_fk FOREIGN KEY (id_document, code_type_source)
        REFERENCES document (id_document, code_type_source) ON DELETE CASCADE
);

COMMENT ON TABLE document_base_donnees IS
    'Sous-entité de la partition pour la source de type base de données (S4). Créée vide et sans attribut propre : l''extracteur n''existe pas encore, mais son absence ferait échouer le premier chargement sur la contrainte de partition.';


CREATE TABLE document_big_data (
    id_document       INTEGER     NOT NULL,
    code_type_source  VARCHAR(20) NOT NULL,

    CONSTRAINT document_big_data_pk PRIMARY KEY (id_document),
    CONSTRAINT document_big_data_type CHECK (code_type_source = 'big_data'),
    CONSTRAINT document_big_data_fk FOREIGN KEY (id_document, code_type_source)
        REFERENCES document (id_document, code_type_source) ON DELETE CASCADE
);

COMMENT ON TABLE document_big_data IS
    'Sous-entité de la partition pour la source de type big data (S5). Créée vide pour la même raison que document_base_donnees.';


-- ===========================================================================
-- 5. Tables d'association
-- ===========================================================================

-- --- 5.1 Collectes -----------------------------------------------------------
-- Une ligne par « ce document a été vu dans cette exécution, par ce chemin ».
-- C'est cette table qui absorbe les doublons de collecte : une même question
-- atteinte par deux tags donne un document et deux collectes.

CREATE TABLE collecte (
    id_collecte       INTEGER      GENERATED ALWAYS AS IDENTITY,
    id_extraction     INTEGER      NOT NULL,
    id_document       INTEGER      NOT NULL,
    critere_collecte  VARCHAR(200) NOT NULL,
    vu_le             TIMESTAMPTZ  NOT NULL,

    CONSTRAINT collecte_pk PRIMARY KEY (id_collecte),

    -- RESTRICT : supprimer une exécution ne doit pas emporter l'historique
    -- qu'on a décidé de conserver. La suppression devient un acte délibéré,
    -- qui impose de traiter d'abord les collectes.
    CONSTRAINT collecte_extraction_fk FOREIGN KEY (id_extraction)
        REFERENCES extraction (id_extraction) ON DELETE RESTRICT,

    -- CASCADE : une collecte sans document n'a aucun sens.
    CONSTRAINT collecte_document_fk FOREIGN KEY (id_document)
        REFERENCES document (id_document) ON DELETE CASCADE,

    CONSTRAINT collecte_unicite UNIQUE (id_extraction, id_document, critere_collecte),
    CONSTRAINT collecte_critere_non_vide CHECK (btrim(critere_collecte) <> '')
);

COMMENT ON TABLE  collecte IS
    'Acte de collecte d''un document par une exécution, selon un critère donné. Historisée intégralement : une chute de volumétrie entre deux exécutions signale un incident.';
COMMENT ON COLUMN collecte.critere_collecte IS
    'Chemin par lequel le document a été atteint : le tag pour un service web, la page pour du scraping, le fichier pour une source locale. Non nullable, une source étant toujours interrogée par un chemin.';
COMMENT ON COLUMN collecte.vu_le IS
    'Horodatage de cette collecte précise, distinct de la date de première extraction du document.';


-- --- 5.2 Descriptions --------------------------------------------------------

CREATE TABLE description (
    id_document   INTEGER     NOT NULL,
    code_mot_cle  VARCHAR(60) NOT NULL,

    CONSTRAINT description_pk PRIMARY KEY (id_document, code_mot_cle),
    CONSTRAINT description_document_fk FOREIGN KEY (id_document)
        REFERENCES document (id_document) ON DELETE CASCADE,

    -- RESTRICT : un mot-clé encore employé ne se supprime pas par mégarde.
    CONSTRAINT description_mot_cle_fk FOREIGN KEY (code_mot_cle)
        REFERENCES mot_cle (code_mot_cle) ON DELETE RESTRICT
);

COMMENT ON TABLE description IS
    'Association entre un document et les mots-clés qui le qualifient. Relation pure, sans attribut propre.';
