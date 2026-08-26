/*
 * Contraintes non déclaratives et vues de contrôle de la base eduai_data.
 *
 * Compétence visée : C4 (épreuve E1) — contraintes d'intégrité
 *
 * Ce fichier ne contient que ce qui ne pouvait pas être exprimé de façon
 * déclarative dans 01_schema.sql. Tout le reste — clés, unicités, CHECK,
 * clés étrangères composites — y figure déjà, et c'est délibéré : une
 * contrainte portée par le moteur ne se contourne pas, une contrainte portée
 * par du code se contourne dès qu'un second programme écrit dans la base.
 *
 * Il ne reste ici qu'une règle : la **totalité** de la partition de document.
 */

-- ===========================================================================
-- 1. Totalité de la partition
-- ===========================================================================
--
-- Règle : tout document possède exactement une ligne dans la table fille
-- correspondant à son type de source.
--
-- L'exclusivité est déjà garantie de façon déclarative par la clé étrangère
-- composite (voir 01_schema.sql, section 4). La totalité ne l'est pas :
-- elle exigerait une assertion inter-tables, que la norme SQL prévoit mais
-- qu'aucun moteur courant n'implémente, PostgreSQL compris.
--
-- Choix : un déclencheur de contrainte DIFFÉRÉ. Motivation : la ligne mère est
-- nécessairement insérée avant sa fille, puisque la fille la référence. Un
-- contrôle immédiat échouerait donc systématiquement, y compris sur un
-- chargement parfaitement correct. Le report en fin de transaction est ce qui
-- rend la contrainte praticable.
--
-- Choix : un branchement explicite par type plutôt qu'une requête dynamique
-- construite à partir du nom de la table. Motivation : le SQL dynamique serait
-- plus court, mais il masquerait le fait qu'il existe cinq types de sources
-- distincts — ce que le référentiel demande précisément de démontrer. Et une
-- erreur de nom de table ne se verrait qu'à l'exécution.

CREATE OR REPLACE FUNCTION verifier_partition_document()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    fille_presente BOOLEAN;
BEGIN
    CASE NEW.code_type_source

        WHEN 'api_rest' THEN
            SELECT EXISTS (SELECT 1 FROM document_api_rest
                           WHERE id_document = NEW.id_document)
              INTO fille_presente;

        WHEN 'scraping' THEN
            SELECT EXISTS (SELECT 1 FROM document_web
                           WHERE id_document = NEW.id_document)
              INTO fille_presente;

        WHEN 'fichier' THEN
            SELECT EXISTS (SELECT 1 FROM document_fichier
                           WHERE id_document = NEW.id_document)
              INTO fille_presente;

        WHEN 'base_donnees' THEN
            SELECT EXISTS (SELECT 1 FROM document_base_donnees
                           WHERE id_document = NEW.id_document)
              INTO fille_presente;

        WHEN 'big_data' THEN
            SELECT EXISTS (SELECT 1 FROM document_big_data
                           WHERE id_document = NEW.id_document)
              INTO fille_presente;

        ELSE
            -- Inatteignable tant que code_type_source référence type_source,
            -- mais un ELSE muet transformerait une future sixième valeur en
            -- document sans sous-type, silencieusement accepté.
            RAISE EXCEPTION
                'Type de source inconnu « % » pour le document %.',
                NEW.code_type_source, NEW.id_document;
    END CASE;

    IF NOT fille_presente THEN
        RAISE EXCEPTION
            'Partition incomplète : le document % est de type « % » mais ne '
            'possède aucune ligne dans la table fille correspondante.',
            NEW.id_document, NEW.code_type_source
            USING HINT = 'Insérer la ligne fille dans la même transaction que la ligne mère.';
    END IF;

    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION verifier_partition_document() IS
    'Vérifie qu''un document possède la ligne fille correspondant à son type de source. Appelée en fin de transaction par le déclencheur document_partition_totale.';

CREATE CONSTRAINT TRIGGER document_partition_totale
    AFTER INSERT OR UPDATE OF code_type_source ON document
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION verifier_partition_document();


-- ===========================================================================
-- 2. Vues de contrôle
-- ===========================================================================
--
-- Le déclencheur garantit, ces vues documentent. Elles servent au rapport
-- d'exécution du pipeline, qu'un échec de transaction ne renseignerait pas :
-- une transaction annulée ne dit pas combien de lignes étaient correctes.
--
-- Elles sont aussi le repli prévu. Si le déclencheur complique le chargement
-- par lots au point de le ralentir, il est retiré et seules ces vues
-- subsistent : la garantie est alors plus faible, mais le contrôle demeure.

-- Contrôle arithmétique de la partition. Sur les données extraites à ce jour,
-- la somme attendue est 1 273 + 235 + 380 = 1 888.
CREATE VIEW controle_partition AS
SELECT
    (SELECT count(*) FROM document)              AS documents,
    (SELECT count(*) FROM document_api_rest)     AS api_rest,
    (SELECT count(*) FROM document_web)          AS scraping,
    (SELECT count(*) FROM document_fichier)      AS fichier,
    (SELECT count(*) FROM document_base_donnees) AS base_donnees,
    (SELECT count(*) FROM document_big_data)     AS big_data,
    (SELECT count(*) FROM document)
        - (SELECT count(*) FROM document_api_rest)
        - (SELECT count(*) FROM document_web)
        - (SELECT count(*) FROM document_fichier)
        - (SELECT count(*) FROM document_base_donnees)
        - (SELECT count(*) FROM document_big_data) AS ecart;

COMMENT ON VIEW controle_partition IS
    'Contrôle de la partition de document. La colonne ecart doit valoir zéro : toute autre valeur signale des documents sans sous-type.';


-- Couverture des cinq types de sources exigés par le référentiel. Sert de
-- preuve directe pour C1 : une seule requête montre où en est la couverture.
CREATE VIEW controle_couverture_sources AS
SELECT
    t.code_type_source,
    t.libelle,
    s.code_source,
    s.nom,
    count(d.id_document) AS documents
FROM type_source t
LEFT JOIN source   s ON s.code_type_source = t.code_type_source
LEFT JOIN document d ON d.code_source = s.code_source
GROUP BY t.code_type_source, t.libelle, s.code_source, s.nom
ORDER BY t.code_type_source;

COMMENT ON VIEW controle_couverture_sources IS
    'Un type de source par ligne, avec la source qui le couvre et sa volumétrie. Une ligne sans code_source est un type non encore couvert.';


-- Documents dont la redistribution n'est pas autorisée. Ils sont chargés en
-- base — pour être dénombrables et traçables — mais doivent être écartés de
-- l'indexation RAG : afficher un contenu à un utilisateur est une
-- redistribution.
CREATE VIEW documents_non_redistribuables AS
SELECT
    d.id_document,
    d.code_source,
    d.identifiant_source,
    d.titre,
    l.code_licence,
    l.libelle AS licence
FROM document d
JOIN licence l ON l.code_licence = d.code_licence
WHERE NOT l.redistribution_autorisee;

COMMENT ON VIEW documents_non_redistribuables IS
    'Documents à exclure de l''indexation RAG faute de droit de rediffusion. Les charger puis les écarter par requête permet de prouver qu''ils le sont, ce qu''un rejet silencieux à l''import ne permettrait pas.';


-- Documents indexables par le RAG : le complément de la vue précédente,
-- exprimé positivement pour être utilisé tel quel par le pipeline d'indexation.
CREATE VIEW documents_indexables AS
SELECT
    d.id_document,
    d.code_source,
    d.titre,
    d.contenu,
    d.url_source,
    d.langue,
    l.attribution_requise,
    l.mention_copyright
FROM document d
JOIN licence l ON l.code_licence = d.code_licence
WHERE l.redistribution_autorisee;

COMMENT ON VIEW documents_indexables IS
    'Corpus effectivement indexable, licences vérifiées. La mention de copyright et l''obligation d''attribution accompagnent chaque ligne pour que l''affichage puisse créditer la source.';
