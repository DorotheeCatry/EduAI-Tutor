/*
 * Spécialisation des types sans attribut propre : big data (S5) et base de
 * données (S4).
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Rattacher le document à sa table fille alors que celle-ci ne porte aucune
 * colonne supplémentaire.
 *
 * CHOIX
 * Ces deux tables existent malgré leur vacuité apparente. Motivation : la
 * spécialisation est TOTALE — le déclencheur `document_partition_totale` exige
 * qu'un document ait une ligne dans exactement une table fille. Sans ces
 * tables, les documents big data et base de données seraient des orphelins,
 * et la contrainte de totalité devrait être abandonnée pour tout le modèle.
 *
 * Elles constituent par ailleurs le point d'accroche des attributs que ces
 * sources acquerront : rien n'oblige à ce que la table reste vide.
 *
 * Le nom de la table ne peut pas être un paramètre : il est injecté par
 * l'appelant depuis une liste fermée de noms, jamais depuis une donnée.
 */

INSERT INTO {table} (id_document, code_type_source)
VALUES (%(id_document)s, %(code_type_source)s)
ON CONFLICT (id_document) DO NOTHING
