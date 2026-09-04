/*
 * Purge des documents dont la durée de conservation est échue.
 *
 * Compétence visée : C4 (épreuve E1) — durée de conservation, RGPD
 * Compétence concernée : C2 (E1) — requête de traitement
 *
 * Objectif : supprimer les documents dont l'ancienneté dépasse la durée que
 * leur source déclare. La durée est portée par `source.duree_conservation_jours` ;
 * `NULL` signifie « sans terme » et exclut la source de la purge.
 *
 * Choix : la durée vit sur la SOURCE et non sur le document. Motivation : elle
 * relève d'une politique — combien de temps ce projet garde ce qui vient de là
 * — et non d'une propriété du document. La porter sur chaque ligne obligerait
 * à toutes les réécrire pour changer d'avis.
 *
 * Choix : l'ancienneté est mesurée sur `extrait_le`, la date de collecte, et
 * non sur la date de création du document. Motivation : la conservation est un
 * engagement sur ce que NOUS gardons, à partir du moment où nous l'avons pris.
 * Un document de 2012 collecté hier n'est pas conservé depuis quatorze ans.
 *
 * Jointure sur `source` pour lire la durée. La suppression se propage aux
 * tables filles — spécialisations, collecte, description — par les
 * `ON DELETE CASCADE` déclarés au schéma : aucune ligne orpheline ne subsiste,
 * et le nettoyage est garanti par le moteur plutôt que par l'ordre des
 * instructions.
 *
 * La clause RETURNING rend ce qui a été supprimé : la commande compte ce que
 * la base a réellement fait, jamais ce qu'elle croyait faire — c'est la leçon
 * de l'incident 001.
 */
DELETE FROM document d
USING source s
WHERE d.code_source = s.code_source
  AND s.duree_conservation_jours IS NOT NULL
  AND d.extrait_le < now() - (s.duree_conservation_jours || ' days')::interval
RETURNING d.id_document, d.code_source, d.extrait_le;
