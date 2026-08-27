/*
 * Enregistrement d'une campagne d'extraction.
 *
 * Compétence visée : C4 (épreuve E1) — traçabilité en base
 * Compétence visée : C1 (épreuve E1) — trace de l'exécution
 *
 * OBJECTIF
 * Consigner ce qu'une exécution d'extracteur a réellement fait : quand, combien
 * de temps, avec quel statut, combien d'enregistrements et combien d'erreurs.
 * C'est la table qui permet de détecter une source qui se dégrade — un volume
 * qui s'effondre, une durée qui dérive, un taux d'erreur qui monte.
 *
 * CHOIX DE SÉLECTION DES VALEURS
 * Toutes proviennent du bilan écrit par l'extracteur lui-même, jamais
 * reconstituées depuis le corpus. Le chargeur pourrait compter les documents,
 * mais il ignore la durée réelle, les erreurs rencontrées et les
 * enregistrements écartés en chemin. Les inventer serait fabriquer une mesure.
 *
 * CHOIX D'IDEMPOTENCE
 * `ON CONFLICT (code_source, horodatage_debut) DO UPDATE` : une campagne est
 * identifiée par sa source et son instant de départ. Recharger le même bilan
 * met à jour la ligne au lieu d'en créer une seconde, et deux exécutions
 * distinctes de la même source restent deux lignes — c'est ce qui rend
 * l'historique exploitable.
 *
 * CONTRAINTES QUE CETTE INSERTION DOIT SATISFAIRE
 * - `extraction_succes_non_vide` : le statut « succes » exige au moins un
 *   enregistrement. Contrainte née de l'incident S1 du 26/08, dont le bilan
 *   annonçait « succes, 0 enregistrement ».
 * - `extraction_vide_sans_donnees` : réciproquement, le statut « vide » exige
 *   zéro enregistrement, faute de quoi il deviendrait un moyen commode de
 *   contourner la contrainte précédente.
 */

INSERT INTO extraction (
    code_source, horodatage_debut, duree_secondes,
    statut, nb_enregistrements, nb_erreurs, fichier_sortie
) VALUES (
    %(code_source)s, %(horodatage_debut)s, %(duree_secondes)s,
    %(statut)s, %(nb_enregistrements)s, %(nb_erreurs)s, %(fichier_sortie)s
)
ON CONFLICT (code_source, horodatage_debut) DO UPDATE SET
    duree_secondes     = EXCLUDED.duree_secondes,
    statut             = EXCLUDED.statut,
    nb_enregistrements = EXCLUDED.nb_enregistrements,
    nb_erreurs         = EXCLUDED.nb_erreurs,
    fichier_sortie     = EXCLUDED.fichier_sortie
RETURNING id_extraction
