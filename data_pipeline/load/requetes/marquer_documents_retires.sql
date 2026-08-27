/*
 * Marquage des documents disparus de leur source.
 *
 * Compétence visée : C4 (épreuve E1) — cohérence du jeu de données
 * Compétence visée : C1 (épreuve E1) — traçabilité de la collecte
 *
 * OBJECTIF
 * Repérer les documents que le chargement courant n'a pas revus, et consigner
 * la date de ce constat.
 *
 * Le cas est réel : une section de la documentation Python présente au
 * scraping du 26/08 avait disparu de celui du 27/08. Le chargeur, qui met à
 * jour et n'efface jamais, la laissait en base — et l'API annonçait 235
 * documents pour une source qui n'en fournissait plus que 234.
 *
 * CHOIX : MARQUER PLUTÔT QUE SUPPRIMER
 * Une section qui disparaît entre deux scrapings n'est pas une erreur du
 * pipeline, c'est une information sur la source : elle a été réorganisée,
 * fusionnée ou retirée. La supprimer effacerait cette information, et avec
 * elle les lignes de `collecte` qui attestent qu'elle avait bien été collectée
 * un jour. Le marquage conserve les deux, et corrige le décompte servi par
 * l'API, dont le gestionnaire par défaut exclut les documents retirés.
 *
 * CHOIX DE FILTRAGE
 * - `code_source = ANY(...)` : seules les sources effectivement présentes dans
 *   le corpus chargé sont balayées. Une source absente du corpus ne permet pas
 *   de distinguer « rien n'a été extrait cette fois » de « tout a disparu » ;
 *   dans le doute, on ne marque rien. Sans ce garde-fou, un chargement partiel
 *   — une seule source réextraite — retirerait tout le reste du corpus.
 * - `dernier_vu_le < :horodatage` : le document n'a pas été revu par ce
 *   chargement, qui a rafraîchi la date de tous ceux qu'il a vus.
 * - `retire_le IS NULL` : un document déjà marqué garde la date de son premier
 *   constat de disparition, plus significative que celle du dernier passage.
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Aucune sous-requête : la comparaison porte sur une colonne de la table
 *   elle-même, renseignée quelques instants plus tôt dans la même transaction.
 * - Aucun index ajouté pour ce prédicat : `retire_le IS NULL` est vrai pour
 *   la quasi-totalité des lignes — un seul document retiré sur 6 836. Un index
 *   partiel sur cette condition indexerait presque toute la table sans aider
 *   le planificateur, tout en coûtant à chaque écriture.
 *
 * NOTE DE FORME
 * Ce fichier est exécuté par psycopg avec des paramètres nommés. Le caractère
 * pour-cent y est donc réservé, y compris dans les commentaires : psycopg
 * analyse le texte entier avant de l'envoyer au serveur et prend un pour-cent
 * isolé pour un marqueur incomplet. Écrire « 99,9 pour-cent » en toutes
 * lettres évite d'avoir à le doubler, et reste lisible.
 * - `RETURNING` renvoie les documents marqués : le chargeur les consigne dans
 *   son rapport plutôt que d'annoncer un simple décompte.
 */

UPDATE document
   SET retire_le = %(horodatage)s
 WHERE code_source = ANY(%(sources_chargees)s)
   AND dernier_vu_le < %(horodatage)s
   AND retire_le IS NULL
RETURNING id_document, code_source, identifiant_source, titre
