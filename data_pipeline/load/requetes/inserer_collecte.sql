/*
 * Rattachement d'un document à la campagne qui l'a ramené.
 *
 * Compétence visée : C4 (épreuve E1) — traçabilité de la collecte
 * Compétence visée : C1 (épreuve E1)
 *
 * OBJECTIF
 * Répondre à la question « par quel chemin ce document est-il arrivé ? ». La
 * réponse n'est pas toujours unique : la question Stack Overflow so_16476924 a
 * été trouvée deux fois, par le tag « python » puis par le tag « pandas ». La
 * couche de transformation a fusionné les deux exemplaires en conservant les
 * deux critères ; cette table les matérialise en deux lignes.
 *
 * CHOIX DE MODÉLISATION
 * La clé d'unicité porte sur le triplet (campagne, document, critère) et non
 * sur le couple (campagne, document). Motivation : sans le critère, les deux
 * chemins de collecte de so_16476924 se réduiraient à un seul, et la
 * traçabilité que la fusion avait pris soin de préserver serait perdue au
 * chargement — après avoir été sauvée à la transformation.
 *
 * CHOIX D'IDEMPOTENCE
 * `ON CONFLICT DO NOTHING` sur ce triplet : recharger le même corpus ne
 * multiplie pas les lignes.
 *
 * `vu_le` porte la date à laquelle le document a été vu par cette campagne,
 * distincte de `horodatage_debut` de la campagne elle-même : une extraction
 * longue voit ses premiers documents bien avant ses derniers.
 */

INSERT INTO collecte (id_extraction, id_document, critere_collecte, vu_le)
VALUES (%(id_extraction)s, %(id_document)s, %(critere_collecte)s, %(vu_le)s)
ON CONFLICT (id_extraction, id_document, critere_collecte) DO NOTHING
