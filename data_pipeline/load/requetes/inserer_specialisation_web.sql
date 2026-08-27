/*
 * Spécialisation d'un document issu du scraping (S2).
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Conserver la page d'origine et, le cas échéant, l'ancre de la section
 * extraite — sans quoi un document scrapé n'est pas re-localisable dans la
 * page dont il provient.
 *
 * `ancre_section` est la seule colonne nullable de cette table : toutes les
 * pages n'exposent pas d'ancre, et l'absence d'ancre est une information
 * légitime, pas une donnée manquante.
 */

INSERT INTO document_web (id_document, code_type_source, page, ancre_section)
VALUES (%(id_document)s, 'scraping', %(page)s, %(ancre_section)s)
ON CONFLICT (id_document) DO UPDATE SET
    page          = EXCLUDED.page,
    ancre_section = EXCLUDED.ancre_section
