/*
 * Dénombrement des documents que la purge supprimerait.
 *
 * Compétence visée : C4 (épreuve E1)
 * Compétence concernée : C2 (E1)
 *
 * Même critère que `05_purge_conservation.sql`, sans écriture. Sert au mode
 * « à blanc » : une purge doit pouvoir être constatée avant d'être subie.
 *
 * Choix : deux fichiers plutôt qu'une requête paramétrée. Motivation : le
 * lecteur d'un fichier nommé « purge » doit voir un DELETE, et celui d'un
 * fichier nommé « dénombrement » un SELECT. Une requête qui supprime ou non
 * selon un drapeau se relit mal, et se relit surtout trop tard.
 */
SELECT s.code_source,
       s.nom,
       s.duree_conservation_jours,
       count(*) AS documents_echus,
       min(d.extrait_le) AS plus_ancien
FROM document d
JOIN source s ON s.code_source = d.code_source
WHERE s.duree_conservation_jours IS NOT NULL
  AND d.extrait_le < now() - (s.duree_conservation_jours || ' days')::interval
GROUP BY s.code_source, s.nom, s.duree_conservation_jours
ORDER BY s.code_source;
