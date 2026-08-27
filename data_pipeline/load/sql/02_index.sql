/*
 * Index de la base eduai_data.
 *
 * Compétence visée : C4 (épreuve E1) — « index justifiés par les requêtes
 * prévues, pas posés au hasard »
 *
 * Principe retenu : un index se justifie par une requête ou par une contrainte
 * référentielle, jamais par précaution. Chaque index créé ci-dessous porte le
 * motif qui l'appelle. La fin du fichier liste, tout aussi explicitement, les
 * index qui ne sont PAS créés et pourquoi — un index inutile n'est pas neutre,
 * il ralentit chaque écriture et occupe de l'espace.
 *
 * Fait à connaître, qui commande la moitié de ce fichier : PostgreSQL crée
 * automatiquement un index pour une clé primaire et pour une contrainte
 * UNIQUE, mais **jamais pour une clé étrangère**. Or une suppression dans la
 * table référencée provoque, pour chaque ligne supprimée, un parcours complet
 * de la table référençante si sa colonne n'est pas indexée.
 *
 * Les mesures EXPLAIN ANALYZE relèvent des requêtes de C2, écrites après le
 * chargement : on ne mesure pas un plan sur une base vide.
 */

-- ===========================================================================
-- 1. Index appelés par les clés étrangères
-- ===========================================================================

-- Requête servie : « combien de fois ce document a-t-il été collecté, et
-- par quelles exécutions ? ». Contrainte servie : ON DELETE CASCADE depuis
-- document. Sans cet index, supprimer un document impose un parcours complet
-- de collecte, table appelée à devenir la plus volumineuse du schéma puisque
-- l'historique y est conservé intégralement.
CREATE INDEX idx_collecte_document ON collecte (id_document);

-- Requête servie : « quels documents cette exécution a-t-elle collectés ? »,
-- qui fonde la comparaison de volumétrie entre deux exécutions d'une même
-- source. Contrainte servie : ON DELETE RESTRICT depuis extraction, dont la
-- vérification parcourt collecte à chaque tentative de suppression.
CREATE INDEX idx_collecte_extraction ON collecte (id_extraction);

-- Requête servie : « quels documents portent ce mot-clé ? », c'est-à-dire le
-- filtrage thématique du RAG. La clé primaire de description est
-- (id_document, code_mot_cle) : elle sert la lecture dans ce sens, mais pas
-- dans l'autre. Sans cet index, partir d'un mot-clé impose de parcourir les
-- 5 200 associations.
CREATE INDEX idx_description_mot_cle ON description (code_mot_cle);

-- Contrainte servie : la clé étrangère composite de document vers source.
-- La contrainte UNIQUE (id_document, code_type_source) indexe le couple dans
-- ce sens, mais rien n'indexe le côté référençant.
-- Requête servie : le dénombrement des documents par source, qui alimente le
-- rapport d'exécution du pipeline et la preuve de couverture des cinq types.
CREATE INDEX idx_document_source ON document (code_source);

-- Contrainte servie : la clé étrangère composite de document vers licence.
-- Requête servie, et c'est la principale du projet : la sélection des
-- documents indexables par le RAG, qui joint document et licence pour écarter
-- ceux dont la redistribution n'est pas autorisée.
CREATE INDEX idx_document_licence ON document (code_licence);

-- Contrainte servie : la clé étrangère de extraction vers source.
-- Requête servie : l'historique des exécutions d'une source donnée, ordonné
-- par date. L'index composite sert les deux à la fois, et la colonne de tri
-- est incluse pour éviter un tri explicite.
CREATE INDEX idx_extraction_source_date ON extraction (code_source, horodatage_debut DESC);


-- ===========================================================================
-- 2. Index appelés par une requête métier
-- ===========================================================================

-- Requête servie : la sélection du corpus à indexer, filtrée par langue. Le
-- tuteur ne présente pas indifféremment une source anglaise à une question
-- posée en français.
--
-- L'index est **partiel** : il ne couvre que les documents portant une URL de
-- source, seuls candidats à une citation. Un index partiel est plus petit,
-- donc plus souvent maintenu en mémoire, et son existence documente à elle
-- seule la règle métier qui la sous-tend.
CREATE INDEX idx_document_langue_citable
    ON document (langue)
    WHERE url_source IS NOT NULL;


-- ===========================================================================
-- 3. Index volontairement absents
-- ===========================================================================
--
-- Cette section fait partie du livrable : renoncer à un index est une décision
-- au même titre que d'en créer un.
--
-- * Recherche plein texte sur document.contenu (GIN sur to_tsvector).
--   Non créé. La recherche sémantique du projet passe par le vecteur de
--   ChromaDB, pas par la base relationnelle. Un index GIN sur 1 888 documents
--   coûterait plusieurs mégaoctets et un surcoût à chaque écriture, pour un
--   usage qui n'existe pas dans les requêtes prévues. À reconsidérer si une
--   recherche lexicale exacte devient nécessaire.
--
-- * Index sur document.identifiant_source seul.
--   Non créé. La contrainte UNIQUE (code_source, identifiant_source) crée déjà
--   un index dont identifiant_source n'est pas la colonne de tête — mais toute
--   recherche par identifiant vient d'un extracteur, qui connaît sa source et
--   fournit donc les deux colonnes.
--
-- * Index sur document.extrait_le, pour la purge par durée de conservation.
--   Non créé pour l'instant. La purge est une opération périodique et rare
--   qui parcourt de toute façon une large fraction de la table : le planificateur
--   choisirait un parcours séquentiel même avec l'index disponible. À créer si
--   la volumétrie change d'ordre de grandeur avec S4 et S5.
--
-- * Index sur les tables filles de la partition.
--   Non créés. Leur clé primaire est id_document, qui est aussi la colonne de
--   jointure avec la mère : l'index de clé primaire suffit.
--
-- * Index sur les tables de référence type_source, licence, source.
--   Non créés. Elles comptent respectivement 5, 4 et 5 lignes. Un parcours
--   séquentiel y est plus rapide qu'un accès indexé, et le planificateur
--   ignorerait l'index.


-- ===========================================================================
-- Index de recherche plein texte, ajouté pour l'API du jeu de données (C5)
-- ===========================================================================
--
-- Compétence visée : C5 (épreuve E1) — recherche sur le corpus
-- Compétence visée : C2 (épreuve E1) — optimisation d'une requête de collecte
--
-- Motivation : le point de terminaison /api/dataset/documents/ propose une
-- recherche plein texte sur le titre et le contenu. Sans index, chaque requête
-- calcule le vecteur lexical des 6 800 documents, contenu compris — plusieurs
-- dizaines de mégaoctets de texte relus à chaque appel.
--
-- Choix : configuration « simple » plutôt que « french » ou « english ».
-- Motivation : le corpus est bilingue — 6 500 documents en anglais, 380 en
-- français. Une configuration à racinisation ne vaut que pour la langue qu'elle
-- connaît : « simple » ne racinise pas, mais traite les deux langues de la même
-- manière, ce qui est préférable à bien traiter l'une et mal l'autre.
-- Un index par langue, avec un prédicat sur `langue`, serait la suite logique
-- si la recherche devient un usage central.
--
-- Choix : index d'expression et non colonne matérialisée. Motivation : une
-- colonne tsvector devrait être maintenue à jour par le chargeur ou par un
-- déclencheur, donc pourrait diverger du contenu. L'expression est calculée par
-- le moteur : elle ne peut pas se désynchroniser.
--
-- L'expression doit être identique à celle que produit Django, sans quoi le
-- planificateur ne reconnaît pas l'index et retombe sur un balayage complet.
CREATE INDEX IF NOT EXISTS idx_document_recherche
    ON document
    USING gin (to_tsvector('simple', COALESCE(titre, '') || ' ' || COALESCE(contenu, '')));

COMMENT ON INDEX idx_document_recherche IS
    'Recherche plein texte sur titre et contenu, configuration « simple » pour traiter identiquement les documents anglais et français.';
