/*
 * Insertion d'un mot-clé dans la nomenclature.
 *
 * Compétence visée : C4 (épreuve E1)
 *
 * OBJECTIF
 * Alimenter `mot_cle` avant de rattacher les documents, la table `description`
 * référençant cette nomenclature par clé étrangère.
 *
 * CHOIX
 * `ON CONFLICT DO NOTHING` et non `DO UPDATE` : la première catégorie
 * rencontrée fait foi. Motivation : un même libellé peut arriver comme
 * étiquette de source et comme nom de module — « python » est les deux. En
 * faire deux lignes est impossible, la clé primaire étant le libellé seul ;
 * le réécrire à chaque passage rendrait la catégorie dépendante de l'ordre de
 * chargement, donc instable d'une exécution à l'autre.
 *
 * La contrainte `mot_cle_minuscules` refuse toute majuscule : la mise en
 * minuscules est faite par la couche de transformation, et le moteur vérifie
 * qu'elle l'a bien été.
 */

INSERT INTO mot_cle (code_mot_cle, categorie)
VALUES (%(code_mot_cle)s, %(categorie)s)
ON CONFLICT (code_mot_cle) DO NOTHING
