# 009 — Source big data : Spark SQL sur dump Stack Exchange

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C1 et C2 (E1) ; C4 (E1) — RGPD

## Contexte

Le référentiel exige cinq types de sources, dont un système big data, et deux
langages de requête distincts en C2. Les quatre premières sources étaient
couvertes ; il manquait le type big data, et le SQL PostgreSQL restait le seul
langage de requête du projet.

Le critère « big data » ne se satisfait pas d'un gros fichier lu en boucle : il
demande un traitement qui ne tiendrait pas en mémoire et un moteur qui le
distribue.

## Options

1. **Pandas sur le dump décompressé.** Écartée. 123 Mio passent en mémoire, mais
   les 22 Gio du dump Stack Overflow non — et c'est précisément le cas que le
   référentiel vise. Retenir pandas aurait consisté à appeler « big data » un
   traitement qui n'en est pas un.
2. **PySpark avec la seule API DataFrame.** Écartée. Le résultat serait
   identique, mais le second langage de requête de C2 ne serait pas démontré :
   l'API DataFrame est une bibliothèque Python, pas un langage de requête.
3. **PySpark, conversion en Parquet partitionné, puis Spark SQL.** Retenue.

## Décision

Le dump XML est converti en table Parquet partitionnée par année de création,
puis interrogé par des requêtes Spark SQL vivant dans des fichiers `.spark.sql`
dédiés. L'API DataFrame ne porte que la lecture, l'écriture et le plafond
d'essai ; aucune logique de sélection.

Le chemin du dump est un paramètre de ligne de commande. Le même traitement
s'exécute donc sur le dump Data Science (123 Mio) et sur celui de Stack
Overflow (environ 22 Gio), et la comparaison des durées mesure le volume, non
deux versions du code.

Le partitionnement se fait par année plutôt que par type de post : onze
partitions équilibrées sur le petit dump, davantage sur le grand, et un filtre
de fraîcheur qui élague avant toute lecture. Un partitionnement par type de
post n'aurait produit que deux répertoires, trop grossiers pour démontrer quoi
que ce soit.

## Conséquences RGPD

**Users.xml n'est jamais ouvert.** Le fichier ne contient que des données
personnelles — nom d'affichage, site web, localisation déclarée, biographie.
Aucune n'a d'utilité pédagogique. Un garde-fou dans le code refuse le
traitement, plutôt qu'une consigne qui ne vivrait que dans la documentation :
une règle non vérifiable ne survit pas à une modification distraite.

**Écarter Users.xml ne suffit pas.** `Posts.xml` porte lui-même des données
personnelles, comptées sur le dump du 07/04/2024 :

| Attribut | Occurrences |
|---|---|
| `OwnerUserId` | 78 448 |
| `LastEditorUserId` | 28 401 |
| `OwnerDisplayName` | 635 |
| `LastEditorDisplayName` | 184 |

La projection de `s5_conversion_parquet.spark.sql` ne les extrait pas. Sans
elle, 819 noms d'affichage en clair entreraient dans le corpus.

**`OwnerUserId` est une donnée à caractère personnel, malgré son apparence.**
C'est un entier, pas un nom — mais il identifie de façon persistante une
personne physique, et il suffit de l'accoler à l'URL du profil public Stack
Exchange pour retrouver le nom d'affichage. Au sens du considérant 26 du RGPD,
une donnée reste personnelle dès lors que la réidentification est possible par
des moyens raisonnablement susceptibles d'être utilisés. Le raisonnement est
exactement celui appliqué à la pseudonymisation de la source S4 au paragraphe 5
du document RGPD : un pseudonyme réduit l'exposition, il ne fait pas sortir du
champ du règlement. Présenter cette exclusion comme une anonymisation serait
une erreur — et c'est la question qu'un jury pose.

L'attribution exigée par CC BY-SA est assurée par l'URL du post, où Stack
Exchange crédite lui-même son auteur : l'obligation de licence est honorée sans
détenir la donnée, comme pour S1.

## Conséquences techniques

- Dépendances ajoutées : `pyspark` 3.5, et un JDK 17 sur la machine. Spark
  s'exécute en mode local avec tous les cœurs ; le passage à un cluster ne
  changerait qu'une ligne.
- Le Parquet et les dumps vivent hors du dépôt, sur la grande partition. Seuls
  le code et les requêtes sont versionnés.
- Conversion et sélection sont chronométrées séparément : la première est un
  balayage complet payé une fois, la seconde profite du partitionnement et se
  paie à chaque requête. Les confondre rendrait la comparaison entre dumps
  inexploitable.
- Le rapport de métriques est nommé d'après le dump traité, afin que les deux
  mesures coexistent au lieu de s'écraser.

## Mesure de référence

Dump Data Science du 07/04/2024, machine à 8 cœurs, mémoire pilote 4 Go :

| Étape | Durée |
|---|---|
| Conversion XML vers Parquet | 75,80 s |
| Requête de volumétrie | 4,86 s |
| Requête de sélection et écriture | 11,55 s |
| **Total** | **103,36 s** |

122,8 Mio de XML, 78 926 posts, 11 partitions annuelles, 49 Mio en Parquet.
4 948 documents retenus, 0 erreur. Chiffres repris du rapport
`s5_bigdata_stackexchange.datascience.metriques.json`, régénérable par
`--forcer-conversion`.

Deux exécutions successives ont donné 101,73 s et 103,36 s, soit moins de 2 %
d'écart : la mesure est stable, et l'écart attendu avec le dump Stack Overflow
se comptera en ordres de grandeur, pas en pourcents.

Relance sans `--forcer-conversion` : 42,33 s, conversion sautée, mêmes 4 948
documents. L'idempotence exigée par C1 est donc vérifiée, et le coût de la
conversion se paie bien une seule fois.

La mesure sur le dump Stack Overflow reste à faire, le téléchargement étant en
cours. C'est la comparaison des deux qui justifie le recours à un moteur
distribué — l'affirmer sans la mesurer ne prouverait rien.
