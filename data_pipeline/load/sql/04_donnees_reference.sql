/*
 * Données de référence de la base eduai_data.
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * Ces lignes ne sont pas des données collectées : ce sont les nomenclatures
 * sans lesquelles aucun document ne peut être chargé. Les charger ici, dans le
 * script d'initialisation, garantit qu'une base fraîchement créée est
 * immédiatement utilisable — et que la couverture des cinq types de sources
 * est lisible dès le premier démarrage, avant toute extraction.
 *
 * Toutes les insertions sont idempotentes (ON CONFLICT DO NOTHING) : rejouer
 * ce script sur une base déjà peuplée ne produit ni doublon ni erreur.
 */

-- ===========================================================================
-- 1. Types de source
-- ===========================================================================
-- Les cinq types exigés par le référentiel RNCP 37827. Cette table est la
-- preuve, en une requête, que le modèle couvre l'exigence — indépendamment de
-- l'état d'avancement des extracteurs.

INSERT INTO type_source (code_type_source, libelle, description) VALUES
    ('api_rest', 'Service web',
     'Source interrogée par une API REST, sous quota et conditions d''utilisation du fournisseur.'),
    ('scraping', 'Scraping',
     'Source extraite du HTML d''un site, sous réserve du robots.txt et des conditions du site.'),
    ('fichier', 'Fichier de données',
     'Source lue dans des fichiers locaux : Markdown, PDF, notebooks.'),
    ('base_donnees', 'Base de données',
     'Source interrogée en SQL dans une base relationnelle.'),
    ('big_data', 'Système big data',
     'Source volumineuse traitée par un moteur distribué, Spark SQL sur Parquet partitionné.')
ON CONFLICT (code_type_source) DO NOTHING;


-- ===========================================================================
-- 2. Licences
-- ===========================================================================
-- redistribution_autorisee et attribution_requise ne documentent pas : ils
-- filtrent. C'est par eux que le pipeline d'indexation décide ce qui peut être
-- présenté à un utilisateur.

INSERT INTO licence (code_licence, libelle, url_texte,
                     redistribution_autorisee, attribution_requise,
                     mention_copyright) VALUES

    ('CC-BY-SA-4.0',
     'Creative Commons Attribution - Partage dans les mêmes conditions 4.0 International',
     'https://creativecommons.org/licenses/by-sa/4.0/',
     TRUE, TRUE, NULL),

    -- Ajoutée après coup : la couche de transformation a révélé que 1 663
    -- documents du corpus la portent, sans qu'aucun code ne leur corresponde.
    -- CC BY-SA 3.0 et 4.0 sont deux licences distinctes ; les confondre
    -- ferait redistribuer ces documents sous des conditions qui ne sont pas
    -- les leurs. Les posts Stack Exchange antérieurs à mai 2018 relèvent de
    -- la 3.0, ceux publiés ensuite de la 4.0 — l'attribut ContentLicense de
    -- chaque post fait foi.
    ('CC-BY-SA-3.0',
     'Creative Commons Attribution - Partage dans les mêmes conditions 3.0 non transposé',
     'https://creativecommons.org/licenses/by-sa/3.0/',
     TRUE, TRUE, NULL),

    ('PSF',
     'Python Software Foundation License Agreement',
     'https://docs.python.org/3/license.html',
     TRUE, TRUE, 'Copyright (c) 2001-2026 Python Software Foundation'),

    -- Productions des apprenants (source S4). Redistribution INTERDITE : ces
    -- documents naissent du travail d'apprenants identifiés dans eduai_app.
    -- Ils entrent dans le corpus dépouillés de tout identifiant (décision 010),
    -- ce qui les rend exploitables par le tuteur en interne, mais ne confère
    -- aucun droit de les publier. Attribution non requise, et de toute façon
    -- impossible : le corpus ne sait plus qui les a écrits — c'est voulu.
    ('PRODUCTION-APPRENANT',
     'Production d''apprenant — usage interne à l''organisme de formation',
     NULL,
     FALSE, FALSE, NULL),

    ('PROPRIETAIRE',
     'Contenu produit par l''autrice du projet, droits détenus',
     NULL,
     TRUE, FALSE, NULL),

    -- Redistribution interdite par précaution, et non par constat : l'origine
    -- du fichier n'est pas tranchée. Le doute se règle en n'affichant pas.
    ('A_VERIFIER',
     'Origine non déterminée, redistribution suspendue jusqu''à vérification',
     NULL,
     FALSE, FALSE, NULL)

ON CONFLICT (code_licence) DO NOTHING;


-- ===========================================================================
-- 3. Sources
-- ===========================================================================
-- Seules les trois sources dont l'extracteur existe sont déclarées. S4 et S5
-- seront insérées par leurs propres scripts, avec les durées de conservation
-- déjà arrêtées : 90 jours pour S4, 365 pour S5.
--
-- Ne pas les préinscrire est délibéré : une ligne de source sans extracteur
-- laisserait croire à une couverture qui n'existe pas. La vue
-- controle_couverture_sources les fera apparaître comme non couvertes, ce qui
-- est l'état réel du projet.

INSERT INTO source (code_source, nom, code_type_source, url_racine,
                    contraintes_acces, duree_conservation_jours) VALUES

    ('s1', 'Stack Overflow', 'api_rest',
     'https://api.stackexchange.com/2.3/',
     'Quota de 300 requêtes par jour sans clé applicative, 10 000 avec. '
     'Champ backoff de l''API respecté. Pause d''une seconde avant chaque '
     'appel. Contenu sous licence CC BY-SA 4.0, attribution par l''URL de la '
     'question. Conditions : https://api.stackexchange.com/docs',
     365),

    ('s2', 'Documentation Python officielle', 'scraping',
     'https://docs.python.org/3/',
     'robots.txt lu par urllib.robotparser et interrogé avant chaque URL ; '
     'extraction annulée si le fichier est inaccessible. User-Agent '
     'identifiant le projet. Pause de deux secondes entre requêtes. Contenu '
     'sous licence PSF, qui autorise explicitement la redistribution.',
     365),

    ('s3', 'Corpus pédagogique EduAI Tutor', 'fichier',
     NULL,
     'Fichiers locaux du dossier data/contents. Aucune contrainte d''accès '
     'externe. La licence de chaque fichier provient du manifeste '
     'data/contents/provenance.json ; les fichiers non déclarés sont chargés '
     'sous la licence A_VERIFIER plutôt qu''une valeur implicite.',
     NULL),

    ('s4', 'Productions des apprenants EduAI Tutor', 'base_donnees',
     NULL,
     'Base applicative eduai_app, interrogée en lecture seule. Aucun '
     'identifiant de personne n''est projeté : user_id sert à la jointure et '
     'jamais au résultat, et un garde-fou interrompt l''extraction si une '
     'colonne à caractère personnel apparaît dans une projection. Users, '
     'adresses IP et adresses électroniques ne sont jamais lus. '
     'Voir docs/decisions/010.',
     90),

    ('s5', 'Dumps Stack Exchange', 'big_data',
     'https://archive.org/details/stackexchange',
     'Dumps publiés par Stack Exchange sur archive.org, téléchargés puis '
     'traités hors ligne : aucun accès réseau à l''exécution. Seul Posts.xml '
     'est lu ; Users.xml, qui ne contient que des données personnelles, est '
     'refusé par le code. Les attributs OwnerUserId, LastEditorUserId, '
     'OwnerDisplayName et LastEditorDisplayName ne sont pas projetés. '
     'Contenu sous CC BY-SA 3.0 ou 4.0 selon la date du post, attribution '
     'par l''URL. Voir docs/decisions/009.',
     365)

ON CONFLICT (code_source) DO NOTHING;

-- Durée de conservation : 365 jours sur les sources externes, sans terme sur
-- le corpus local dont les droits sont détenus.
--
-- Le motif n'est pas juridique — CC BY-SA et PSF sont irrévocables, un retrait
-- de la source ne retire pas le droit d'usage acquis. Le motif est la
-- fraîcheur : une réponse Stack Overflow de plus d'un an peut décrire une API
-- obsolète, et un tuteur qui la cite induit l'apprenant en erreur. Le coût de
-- la réextraction est négligeable, S1 ayant consommé 15 requêtes sur 300 pour
-- produire 1 313 documents.
