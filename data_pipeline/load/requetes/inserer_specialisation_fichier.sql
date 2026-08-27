/*
 * Spécialisation d'un document issu d'un fichier local (S3).
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Conserver le chemin, le format, le module pédagogique de rattachement,
 * l'index de la section dans le fichier et l'origine déclarée du contenu.
 *
 * CHOIX
 * `origine_declaree` est non nulle et vaut « A VERIFIER » quand le manifeste
 * de provenance ne tranche pas. Motivation : une origine inconnue doit se voir
 * dans la donnée, pas être représentée par un NULL qu'on lit comme une
 * absence de problème.
 *
 * `index_section` distingue les sections d'un même fichier — les dix-neuf
 * sections d'`itertools-module.md` partagent chemin et module, et ne se
 * différencient que par cet index. C'est aussi pourquoi la déduplication ne
 * porte pas sur l'URL (voir docs/decisions/011).
 */

INSERT INTO document_fichier (
    id_document, code_type_source, chemin_fichier, format,
    module_pedagogique, index_section, origine_declaree
) VALUES (
    %(id_document)s, 'fichier', %(chemin_fichier)s, %(format)s,
    %(module_pedagogique)s, %(index_section)s, %(origine_declaree)s
)
ON CONFLICT (id_document) DO UPDATE SET
    chemin_fichier     = EXCLUDED.chemin_fichier,
    format             = EXCLUDED.format,
    module_pedagogique = EXCLUDED.module_pedagogique,
    index_section      = EXCLUDED.index_section,
    origine_declaree   = EXCLUDED.origine_declaree
