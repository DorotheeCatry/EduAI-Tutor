/*
 * Rattachement d'un mot-clé à un document.
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Peupler l'association plusieurs-à-plusieurs entre documents et mots-clés,
 * qui rend le corpus interrogeable par thème indépendamment de sa source.
 *
 * CHOIX
 * `ON CONFLICT DO NOTHING` sur la clé primaire composite : rattacher deux fois
 * le même mot-clé au même document est sans effet, ce qui rend le chargement
 * rejouable.
 *
 * La clé étrangère vers `mot_cle` est en `ON DELETE RESTRICT` : supprimer un
 * mot-clé encore utilisé est refusé. C'est voulu — un mot-clé qui disparaît
 * emporterait silencieusement les rattachements qui en dépendent.
 */

INSERT INTO description (id_document, code_mot_cle)
VALUES (%(id_document)s, %(code_mot_cle)s)
ON CONFLICT (id_document, code_mot_cle) DO NOTHING
