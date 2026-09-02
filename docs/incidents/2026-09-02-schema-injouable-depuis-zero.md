# Incident 015 — Un schéma qui ne se rejoue plus, et des tests verts qui ne le voyaient pas

**Date :** 2 septembre 2026
**Composant :** `data_pipeline/load/sql/01_schema.sql`, `04_donnees_reference.sql`
**Gravité :** majeure — le schéma du jeu de données n'était plus créable depuis zéro
**Statut :** résolu et vérifié en rejouant le schéma dans une base neuve
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C4 (E1) ; C18 (E4) ; C1 (E1)

---

## 1. Déclenchement

La chaîne d'intégration a échoué après la fusion dans `main`, à l'étape
« Créer le schéma du jeu de données ». **Les 253 tests passaient en local**, et
`ruff` était propre — vérifiés juste avant de pousser.

C'est la famille A : vérifié dans un contexte, employé dans un autre. En local,
la base `eduai_data` existe depuis une semaine ; la chaîne, elle, **la crée
depuis zéro à chaque exécution**. Aucun test local ne rejoue le schéma.

## 2. Deux défauts, dont un que j'ai introduit et un que j'ai révélé

### Le premier : une insertion au milieu d'un commentaire

L'ajout de la nomenclature de la sixième source cherchait la fin de
l'instruction `INSERT INTO licence` par le premier point-virgule qui la suit.
**Un commentaire SQL en contenait un.** Les quatre nouvelles licences ont donc
été insérées au milieu d'une phrase explicative, coupant en deux le commentaire
de CC BY-SA 3.0 et orphelinant la ligne qu'il documentait :

```
-- CC BY-SA 3.0 et 4.0 sont deux licences distinctes ,
    ('BSD-3-CLAUSE',
```

PostgreSQL s'arrêtait alors sur `ERROR: syntax error at or near "les"` — le
reste du commentaire, devenu du code.

**Le repère était mal choisi.** Un point-virgule n'est pas une fin
d'instruction en SQL : c'en est une *hors* commentaire et *hors* chaîne. La
correction prend pour ancre `ON CONFLICT (code_licence) DO NOTHING;`, qui ne
figure qu'une fois et ne peut pas apparaître dans un commentaire par accident.

### Le second : le schéma comptait cinq sources

Une fois la syntaxe réparée, l'insertion de `s6` était rejetée :

```
ERROR: new row for relation "source" violates check constraint "source_code_valide"
```

La contrainte imposait `code_source ~ '^s[1-5]$'`.

**Elle confondait deux comptes.** C1 exige cinq *types* de source ; le schéma en
a fait une borne sur le nombre de *sources*. La sixième est un second scraping —
un type déjà couvert — et le schéma la refusait au motif qu'il y avait déjà
cinq sources. Ce n'est pas un défaut d'écriture : c'est une exigence du
référentiel transcrite une case trop loin.

Le motif devient `'^s[1-9]$'`. Il reste borné à un chiffre plutôt qu'ouvert à
n'importe quelle chaîne : une contrainte qui n'exclut plus rien ne contraint
plus rien.

## 3. Pourquoi les tests ne l'ont pas vu

Ils n'avaient pas à le voir : **aucun test ne rejoue le schéma**. C'est la
chaîne qui le fait, et elle le fait pour cette raison — son commentaire le dit
depuis le début : *« un schéma qui ne se crée plus depuis zéro n'est pas
reproductible, et le jury doit pouvoir monter le projet à partir du seul
dépôt »*.

**Le dispositif a fonctionné.** Le défaut a été introduit, poussé, et arrêté par
le seul contrôle qui pouvait le voir — au prix d'une chaîne rouge sur `main`
pendant une dizaine de minutes.

## 4. Correction et vérification

Le fichier a été **restauré depuis le commit qui précède l'insertion**, puis
l'insertion refaite sur les deux ancres de fin d'instruction. Le schéma a
ensuite été rejoué dans une base neuve, exactement comme le fait la chaîne :

```
ok  01_schema.sql      ok  02_index.sql
ok  03_contraintes.sql ok  04_donnees_reference.sql
sources : s1 s2 s3 s4 s5 s6
```

Les dix codes de licence sont présents, dont les quatre nouveaux.

## 5. Ce qu'il reste à faire au chargement

La base `eduai_data` existante porte encore l'ancienne contrainte : elle a été
créée avant ce correctif, et rejouer le schéma ne la modifie pas. **Le
chargement de S6 devra l'altérer d'abord**, faute de quoi il butera sur la même
erreur — cette fois sur la base réelle. Consigné ici plutôt que découvert ce
soir-là.

## 6. Ce qu'on en retient

**Un point-virgule ne délimite pas une instruction SQL.** Il la délimite hors
commentaire et hors chaîne de caractères. Écrire dans un fichier SQL par
recherche de séparateur demande une ancre qui ne puisse pas exister dans un
commentaire — ici, la clause finale de l'instruction elle-même.

Et l'observation plus large : **la contrainte qui a bloqué la sixième source
était juste au moment où elle a été écrite.** Elle transcrivait une exigence
réelle. Ce qui a changé, c'est le projet — pas la contrainte. Une règle qui
encode un nombre issu du référentiel doit dire lequel des deux comptes elle
borne, sans quoi elle finit par interdire ce que le référentiel autorise.
