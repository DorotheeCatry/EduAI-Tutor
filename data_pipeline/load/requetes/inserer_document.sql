/*
 * Insertion d'un document dans la table mère.
 *
 * Compétence visée : C4 (épreuve E1) — chargement dans la base
 *
 * OBJECTIF
 * Verser un document du corpus transformé dans `document`, table mère de la
 * spécialisation par type de source.
 *
 * CHOIX D'IDEMPOTENCE
 * `ON CONFLICT ... DO UPDATE` sur la clé naturelle (code_source,
 * identifiant_source) et non `DO NOTHING`. Motivation : relancer le
 * chargement après une nouvelle extraction doit rafraîchir le contenu d'un
 * document dont la source a changé — un post Stack Exchange édité, une page
 * de documentation mise à jour. `DO NOTHING` figerait le corpus à sa première
 * version sans que rien ne le signale.
 *
 * `RETURNING id_document` fonctionne dans les deux branches, insertion comme
 * mise à jour : l'appelant obtient l'identifiant technique sans requête
 * supplémentaire, ce qui lui permet d'enchaîner sur la table fille.
 *
 * CONTRAINTES QUE CETTE INSERTION DOIT SATISFAIRE
 * - `document_source_fk` : le couple (code_source, code_type_source) doit
 *   exister dans `source`. C'est ce qui a révélé l'absence de s4 et s5.
 * - `document_licence_fk` : le couple (code_licence, attribution_requise) doit
 *   exister dans `licence`. L'appelant lit donc `attribution_requise` depuis la
 *   nomenclature au lieu de le supposer — une valeur inventée ferait échouer
 *   la clé étrangère composite, et c'est exactement son rôle.
 * - `document_attribution_url` : une licence exigeant l'attribution impose une
 *   URL non nulle. Vérifié sur le corpus avant chargement : aucun cas en
 *   défaut.
 * - `document_partition_totale` : déclencheur différé exigeant qu'un document
 *   ait une ligne dans exactement une table fille. D'où le chargement du
 *   document et de sa spécialisation dans la même transaction.
 */

INSERT INTO document (
    code_source, code_type_source, identifiant_source,
    code_licence, attribution_requise,
    titre, contenu, url_source, langue, extrait_le
) VALUES (
    %(code_source)s, %(code_type_source)s, %(identifiant_source)s,
    %(code_licence)s, %(attribution_requise)s,
    %(titre)s, %(contenu)s, %(url_source)s, %(langue)s, %(extrait_le)s
)
ON CONFLICT (code_source, identifiant_source) DO UPDATE SET
    code_licence        = EXCLUDED.code_licence,
    attribution_requise = EXCLUDED.attribution_requise,
    titre               = EXCLUDED.titre,
    contenu             = EXCLUDED.contenu,
    url_source          = EXCLUDED.url_source,
    langue              = EXCLUDED.langue,
    extrait_le          = EXCLUDED.extrait_le
RETURNING id_document
