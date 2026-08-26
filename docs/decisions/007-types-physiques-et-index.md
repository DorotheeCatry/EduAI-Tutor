# 007 — Types physiques et stratégie d'indexation de `eduai_data`

**Date :** 26/08/2026
**Statut :** adoptée
**Compétences concernées :** C4 (E1), C2 (E1)

## Contexte

Le critère C4 attend « des types PostgreSQL adaptés, pas du TEXT par défaut
partout » et « des index justifiés par les requêtes prévues, pas posés au
hasard ». Deux choix en découlent.

## Décision sur les types

Les domaines fermés et stables deviennent des `ENUM` natifs : `statut_extraction`,
`langue_document`, `format_fichier`, `categorie_mot_cle`. Ils sont compacts et
vérifiés par le moteur ; leur seul défaut — un `ALTER TYPE` pour ajouter une
valeur — est sans portée sur des domaines qui ne bougeront pas.

`type_source` fait exception et devient une **table de référence** : ses cinq
valeurs sont fixées par le référentiel, mais elles portent un libellé et une
définition qu'un `ENUM` ne sait pas transporter.

Les tailles numériques sont fixées sur les données réelles, pas au jugé :

| Colonne | Type | Motif |
|---|---|---|
| `score` | `INTEGER` | Maximum observé 13 135, mais les questions les plus consultées de Stack Overflow dépassent la borne de 32 767 d'un `SMALLINT` |
| `nombre_vues` | `INTEGER` | Maximum observé 8 105 583 : `SMALLINT` impossible |
| `nombre_reponses` | `SMALLINT` | Maximum observé 69 |
| `index_section` | `SMALLINT` | Maximum observé 53 |
| `contenu` | `TEXT` | Sans longueur maximale, avec contrainte de non-vacuité. Maximum observé 149 083 caractères |
| `duree_secondes` | `NUMERIC(10,2)` | Durée d'exécution, pas de flottant : la valeur figure dans un rapport |

## Décision sur les index

Sept index, chacun appelé par une requête prévue ou par une contrainte
référentielle. Le fait déterminant : **PostgreSQL crée un index pour une clé
primaire et pour une contrainte `UNIQUE`, mais jamais pour une clé étrangère.**
Une suppression dans la table référencée parcourt alors intégralement la table
référençante.

Le fichier `02_index.sql` documente aussi les index **non créés** — recherche
plein texte sur `contenu`, index sur `extrait_le`, index sur les tables de
référence — avec leur motif de rejet. Renoncer à un index est une décision au
même titre que d'en créer un : un index inutile ralentit chaque écriture.

## Conséquence

Les mesures `EXPLAIN ANALYZE` ne figurent pas ici : elles relèvent des requêtes
de C2, écrites après le chargement. On ne mesure pas un plan d'exécution sur
une base vide.
