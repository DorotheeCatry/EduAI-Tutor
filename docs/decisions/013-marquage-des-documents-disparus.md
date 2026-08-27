# 013 — Documents disparus d'une source : marquer plutôt que purger

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C4 (E1), C5 (E1), C1 (E1)

## Contexte

Le scraping de la documentation Python a ramené 235 sections le 26 août et 234
le 27. Une section — `pydoc_3_tutorial_modules.html_packages-in-multiple-directories`
— avait disparu entre les deux.

Le chargeur met à jour et n'efface jamais. La section restait donc en base, et
l'API annonçait 235 documents pour une source qui n'en fournissait plus que
234. Le décompte servi contredisait le corpus servi.

## Options

1. **Purger.** Supprimer les documents absents du corpus courant. Simple, et le
   décompte redevient exact. Mais la suppression emporte en cascade les lignes
   de `collecte` qui attestent que ce document avait bien été collecté, et avec
   elles toute trace de son passage.
2. **Ne rien faire.** Le décompte reste faux, et l'écart grandit à chaque
   réorganisation d'une source.
3. **Marquer.**

## Décision

Option 3. Deux colonnes sur `document` :

| Colonne | Rôle |
|---|---|
| `dernier_vu_le` | chargement qui a retrouvé le document dans le corpus |
| `retire_le` | date du constat de sa disparition, `NULL` s'il est toujours observé |

Une section qui disparaît entre deux scrapings **n'est pas une erreur du
pipeline, c'est une information sur la source** : elle a été réorganisée,
fusionnée ou retirée. La purger effacerait cette information. Le marquage la
conserve et corrige le décompte.

Le document reste en base, consultable par requête directe, avec ses lignes de
`collecte`. Il sort en revanche du corpus servi par l'API : il ne fait plus
partie de ce que la source fournit aujourd'hui.

## Où vit la trace

La trace détaillée vit dans `collecte`, qui dit **campagne par campagne** quels
documents ont été vus. `retire_le` n'en est que la conclusion, dénormalisée
pour que le filtrage de l'API tienne en un prédicat plutôt qu'en une
sous-requête sur l'historique.

C'est aussi ce qui rend acceptable le fait qu'un document réapparu voie son
`retire_le` remis à `NULL` : la conclusion change, l'historique ne bouge pas.

## Le garde-fou qui compte

Le balayage ne porte que sur **les sources présentes dans le corpus chargé**.

Une source absente du corpus ne permet pas de distinguer « rien n'a été extrait
cette fois » de « tout a disparu ». Sans ce garde-fou, recharger après avoir
réextrait une seule source retirerait tout le reste du corpus — un effacement
de masse déclenché par une commande anodine.

**Éprouvé :** un chargement limité aux 380 documents de la source S3 n'a rien
retiré des 6 455 autres.

## Conséquences

- Le gestionnaire Django par défaut est renommé `DocumentExposableManager` et
  porte deux critères : licence redistribuable **et** document non retiré. Les
  deux vivent au même endroit, hors des vues — une exigence qu'on peut oublier
  vue par vue n'est pas une garantie.
- `condition_exposable_depuis_source()` reprend les deux critères pour les
  agrégations traversant la relation inverse, que le gestionnaire n'atteint pas.
- Aucun index n'est ajouté pour `retire_le IS NULL` : la condition est vraie
  pour la quasi-totalité des lignes. Un index partiel indexerait presque toute
  la table sans aider le planificateur, tout en coûtant à chaque écriture.
- Une contrainte `document_retrait_posterieur` interdit un retrait antérieur à
  la dernière observation : cet ordre-là signalerait une erreur de chronologie
  du chargeur, pas une donnée légitime.

## Vérification

| Contrôle | Résultat |
|---|---|
| Documents marqués | **1**, celui attendu |
| Décompte S2 dans `/sources/` | 235 → **234** |
| Document retiré, encore en base | oui |
| Document retiré, servi par l'API | **non** |
| Relance du chargement complet | 0 retiré de plus, date du premier constat conservée |
| Chargement partiel (S3 seule) | 0 retiré, les 6 455 autres intacts |

## Note de forme rencontrée en chemin

Un caractère pour-cent isolé dans un **commentaire** du fichier SQL faisait
échouer psycopg, qui analyse le texte entier avant de l'envoyer au serveur et y
voit un marqueur de paramètre incomplet. Écrit en toutes lettres plutôt que
doublé — la raison est notée dans le fichier concerné, le piège n'étant pas
évident.
