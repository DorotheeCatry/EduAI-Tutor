/*
 * Spécialisation d'un document issu d'un service web (S1).
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Porter les attributs propres aux documents d'API : score communautaire,
 * nombre de réponses, nombre de vues, date de création du post.
 *
 * CHOIX DE MODÉLISATION
 * Ces colonnes vivent dans une table fille plutôt que dans `document` avec des
 * valeurs nulles pour les autres sources. Motivation : un `score` nul pour une
 * page de documentation Python ne signifie pas « score de zéro », il signifie
 * « notion sans objet ici ». La spécialisation dit cette différence, un NULL
 * dans la table mère la masquerait.
 *
 * La contrainte `document_api_rest_type` garantit qu'aucun document d'un autre
 * type ne peut atterrir ici, même par erreur de programmation.
 */

INSERT INTO document_api_rest (
    id_document, code_type_source, score, nombre_reponses, nombre_vues, cree_le
) VALUES (
    %(id_document)s, 'api_rest', %(score)s, %(nombre_reponses)s,
    %(nombre_vues)s, %(cree_le)s
)
ON CONFLICT (id_document) DO UPDATE SET
    score           = EXCLUDED.score,
    nombre_reponses = EXCLUDED.nombre_reponses,
    nombre_vues     = EXCLUDED.nombre_vues,
    cree_le         = EXCLUDED.cree_le
