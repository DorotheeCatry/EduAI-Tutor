# 006 — Deux bases distinctes sur une seule instance PostgreSQL

**Date :** 26/08/2026
**Statut :** adoptée
**Compétences concernées :** C4 (E1), C17 (E4), C13 (E3)

## Contexte

L'application Django tournait sur SQLite, faiblesse relevée à l'état des lieux.
Le jeu de données du pipeline devait par ailleurs recevoir sa propre base. Trois
répartitions étaient possibles.

## Options

1. **Un schéma unique** dans une seule base. Le plus simple, mais le pipeline
   doit pouvoir purger et recharger son jeu de données : un `TRUNCATE` mal
   ciblé traverse les schémas d'une même base et atteindrait les comptes des
   apprenants.
2. **Deux instances PostgreSQL**. Isolation maximale, au prix d'un second
   conteneur, d'un second port, d'une seconde sauvegarde et d'une seconde
   configuration — pour un projet qui tient sur une machine.
3. **Une instance, deux bases.**

## Décision

Option 3. `eduai_app` porte l'application Django (C17), `eduai_data` porte le
jeu de données collecté (C4). Une base PostgreSQL ne permet pas de requête
inter-bases sans extension : l'isolation est structurelle, pas conventionnelle.

L'application migre donc aussi de SQLite vers PostgreSQL. Un PostgreSQL réservé
au pipeline pendant que l'application reste en SQLite donnerait l'impression
d'un ajout cosmétique pour l'examen.

## Conséquences

- `eduai_data` est créée par le conteneur à partir de `POSTGRES_DB` ;
  `eduai_app` l'est par `00_bases.sql`.
- Le schéma de `eduai_app` reste géré par les migrations Django, qui demeurent
  la source de vérité applicative. Les scripts de `data_pipeline/load/sql/` ne
  concernent que `eduai_data`.
- Les données actuelles de l'application — 19 utilisateurs, 4 cours, 5
  exercices, 22 salles de quiz — sont des données de test jetables. Aucune
  reprise n'est prévue.
- Une jointure entre un document du corpus et un exercice de l'application est
  impossible en SQL. Si le besoin apparaît, il devra passer par l'application,
  ce qui est le comportement voulu.
