# 011 — Couche de transformation : ordre des traitements et clés de déduplication

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C3 (E1), C4 (E1)

## Contexte

Les cinq extracteurs produisent 6 876 enregistrements en JSON Lines, chacun
dans le vocabulaire de sa source. Avant tout chargement en base, il fallait
décider où vit le nettoyage, dans quel ordre il s'applique, et sur quoi repose
la déduplication.

## Décision 1 — une couche distincte, en amont du chargement

`data_pipeline/transform/` est une étape à part entière. Le chargeur lit
`data_pipeline/data/processed/corpus.jsonl` et **jamais** `data_pipeline/data/raw/`.

Brancher le chargement sur le brut ferait de la transformation une étape
facultative, que rien n'obligerait à rejouer après modification d'un
extracteur. La couche brute reste intacte et rejouable ; la couche transformée
est la seule entrée du chargement.

## Décision 2 — trois modules, pas une fonction de nettoyage

Le référentiel évalue nommément trois opérations : déduplication,
normalisation des dates, homogénéisation des formats. Elles reposent sur des
règles différentes et échouent pour des raisons différentes. Les fondre en une
passe unique rendrait chacune invérifiable.

## Décision 3 — l'ordre n'est pas interchangeable

    1. normalisation des dates
    2. homogénéisation des formats
    3. déduplication

La déduplication compare des contenus. Placée en premier, elle tiendrait pour
distinctes deux copies d'un même texte ne différant que par une espace en fin
de ligne ou une forme Unicode. Elle vient donc en dernier, sur des documents
déjà canoniques.

## Décision 4 — déduplication sur l'identifiant et le contenu, jamais sur l'URL

C'est la décision la plus lourde de conséquences, et la moins évidente. État
mesuré sur le corpus brut :

| Collision | Excédents | Verdict |
|---|---|---|
| Identifiant identique | 40 | **vrais doublons** |
| Contenu strictement identique | 40 | les mêmes 40 |
| URL source identique | 359 | **faux doublons** |
| Titre identique, contenu différent | 34 | **faux doublons** |

Les 40 doublons viennent tous de S1 : la même question Stack Overflow
rapatriée sous plusieurs tags de recherche. `so_16476924` est arrivé par
`python` puis par `pandas`.

Les 359 excédents d'URL sont le piège. Ils viennent en majorité de S3, où un
fichier Markdown est découpé en sections : les dix-neuf sections de
`itertools-module.md` partagent l'URL du fichier et ont dix-neuf contenus
différents. **Dédupliquer sur l'URL aurait supprimé dix-huit sections sur
dix-neuf**, et le corpus aurait paru plus propre pour cette raison même.

Les 34 collisions de titre sont de même nature : des sections homonymes.

Seuls l'identifiant et l'empreinte SHA-256 du contenu normalisé font donc foi.

## Décision 5 — fusionner les doublons plutôt que les supprimer

Les deux copies de `so_16476924` ne diffèrent que par `tag_recherche`. Jeter la
seconde ferait perdre l'information que la question a été trouvée par deux
chemins de collecte, alors que C1 exige la traçabilité de l'extraction. Le
document conservé porte les deux tags, et la date d'extraction la plus ancienne.

## Décision 6 — signaler les licences inconnues, ne pas les rattacher

`code_licence` vaut `None` quand le libellé n'a pas de correspondance dans la
nomenclature, et le rapport les dénombre. Rattacher d'office `CC BY-SA 3.0` à
`CC-BY-SA-4.0` ferait redistribuer 1 663 documents sous des conditions qui ne
sont pas les leurs. Une licence mal identifiée engage la redistribution du
corpus : mieux vaut une source non reconnue et comptée qu'une source rattachée
par erreur.

## Conséquence à traiter avant le chargement

**La nomenclature `licence` de `eduai_data` ne contient pas `CC-BY-SA-3.0`,
alors que 1 663 documents la portent.** Les quatre codes existants sont
`CC-BY-SA-4.0`, `PSF`, `PROPRIETAIRE` et `A_VERIFIER`. La source S4 est dans
le même cas : sa licence « Production des apprenants » n'a pas de code.

Le chargement ne pourra pas insérer ces documents sans violer la clé étrangère
vers `licence` — ce qui est le comportement voulu du schéma, et la preuve que
la contrainte travaille. Deux entrées de nomenclature sont à ajouter avant
C4.

## Vérification

Exécution sur les cinq sorties d'extraction : 6 876 entrants, 40 doublons
retirés, 6 836 sortants, 4,53 s, aucune date perdue, aucune ligne illisible.
Les dix-neuf sections de `itertools-module.md` sont intactes, vingt titres
restent partagés par plusieurs documents, et `so_16476924` porte bien ses deux
tags de recherche. Les époques Unix de S1 sont converties : `1224800471`
devient `2008-10-23T22:21:11+00:00`. 615 documents restent sans date de
création — les 235 pages scrapées et les 380 fichiers du corpus local, dont les
sources n'en fournissent pas.
