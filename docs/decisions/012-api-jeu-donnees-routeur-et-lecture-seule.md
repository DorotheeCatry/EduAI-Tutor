# 012 — API du jeu de données : routeur de base, `managed = False`, lecture seule

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C5 (E1), C4 (E1), C13 (E3)

## Contexte

Le référentiel exige une API REST exposant le jeu de données (C5), distincte de
celle du service IA (C9). Django était configuré sur `eduai_app` ; le jeu de
données vit dans `eduai_data`, seconde base de la même instance (décision 006),
dont le schéma appartient aux scripts SQL du pipeline.

Trois questions à trancher : comment Django atteint une base qui n'est pas la
sienne, comment il décrit un schéma qu'il ne possède pas, et comment on garantit
qu'il n'y écrira jamais.

## Décision 1 — un routeur de base de données

`DATABASE_ROUTERS = ["apps.api_data.routeurs.RouteurJeuDonnees"]`.

Django ne sait pas nativement qu'un modèle vit ailleurs que dans `default`. Sans
routeur, toute requête de l'application `api_data` interrogerait `eduai_app`, où
les treize tables n'existent pas — l'erreur serait un « relation does not
exist » très éloigné de sa cause.

Le routeur porte quatre règles, dont deux sont symétriques et comptent autant
l'une que l'autre :

- `db_for_read` dirige `api_data` vers `eduai_data` ;
- `db_for_write` **lève une exception** plutôt que de renvoyer `None`, qui
  laisserait Django écrire dans `eduai_app` avec un message sans rapport ;
- `allow_migrate` interdit de migrer `api_data` où que ce soit ;
- `allow_migrate` interdit aussi de migrer **quoi que ce soit** dans
  `eduai_data`. Sans cette seconde règle, `migrate --database=eduai_data`
  créerait `django_migrations`, `auth_user` et le reste du schéma applicatif
  dans la base du jeu de données — mêlant exactement ce que la décision 006
  avait séparé.

## Décision 2 — `managed = False` sur les treize modèles

Le schéma de `eduai_data` est écrit, commenté et versionné dans
`data_pipeline/load/sql/`, où il constitue une preuve d'évaluation. Sans
`managed = False`, `makemigrations` proposerait de recréer les tables sous forme
de migrations, et le dépôt porterait deux définitions concurrentes du même
schéma — dont l'une, la migration, perdrait les contraintes nommées, les
déclencheurs, les vues et les commentaires SQL.

**Vérifié :** la migration `api_data/0001_initial` existe pour la cohérence de
l'état Django, et `sqlmigrate` n'émet que des `-- (no-op)`. Aucun DDL.

## Décision 3 — lecture seule garantie à trois niveaux

L'API expose le corpus, elle ne le modifie pas. Trois garde-fous, tenus par
trois acteurs différents :

| Garde-fou | Tenu par | Échoue si… |
|---|---|---|
| `ReadOnlyModelViewSet` | le routage HTTP | on écrit un `ModelViewSet` par distraction |
| `db_for_write` lève `EcritureInterdite` | le code Django | le routeur est mal configuré |
| Rôle `eduai_lecture`, `SELECT` seul | PostgreSQL | rien de ce qui précède |

Le troisième est celui qui compte : il tient même quand le code se trompe. La
démonstration est venue d'elle-même — `migrate --database=eduai_data` a été
refusé par PostgreSQL *avant* que le routeur ne soit consulté, Django créant sa
table de suivi des migrations sans passer par `allow_migrate`.

Le rôle est créé par `data_pipeline/load/sql/06_role_lecture.sql`, ne dispose
que du `CONNECT`, de l'`USAGE` sur le schéma et du `SELECT`, et n'a aucun droit
sur `eduai_app`.

## Décision 4 — le filtrage par licence vit dans le gestionnaire

`DocumentExposableManager` filtre sur
`licence__redistribution_autorisee = True`, et c'est le gestionnaire **par
défaut** du modèle `Document`.

Le placer dans chaque vue en ferait une consigne : il suffirait d'un point de
terminaison écrit un jour sans y penser pour diffuser les 82 documents
d'origine non vérifiée ou les productions d'apprenants. Placé ici, il s'applique
à toute requête écrite sur ce modèle — liste, détail, filtre, recherche,
statistiques — y compris celles qui n'existent pas encore.

Aucun gestionnaire non filtré n'est fourni. En ajouter un « pour les cas
particuliers » rendrait le contournement disponible, donc tôt ou tard utilisé.
Le pipeline, qui doit tout voir, n'utilise pas l'ORM.

**Une exception à surveiller.** Les agrégations traversant la relation inverse
`source → documents` n'appliquent pas le gestionnaire du modèle lié : le
décompte `nb_documents` de `/sources/` doit réécrire la condition. Elle est
donc isolée dans `condition_exposable_depuis_source()`, placée juste à côté
du gestionnaire pour que leur divergence soit visible.

**Vérifié sur les trois vecteurs.** Un document sous licence `A_VERIFIER`
présent en base : **404** en accès direct, **0** par filtre, **0** par recherche
plein texte sur son propre titre.

## Décision 5 — recherche plein texte, et un index pour la servir

`to_tsvector` PostgreSQL plutôt que le `SearchFilter` de DRF, qui produit une
suite de `ILIKE '%terme%'` incapable d'utiliser un index et relisant le contenu
entier de chaque document à chaque appel.

Un index GIN `idx_document_recherche` a été ajouté au schéma. Configuration
`simple` et non `french` ou `english` : le corpus est bilingue — environ
6 500 documents anglais et 380 français — et une configuration à racinisation ne
vaut que pour la langue qu'elle connaît. Traiter les deux également vaut mieux
que bien traiter l'une et mal l'autre.

**Vérifié :** `EXPLAIN` donne `Bitmap Index Scan on idx_document_recherche`.

## Conséquences

- Une variable d'environnement de plus, `EDUAI_DATA_PASSWORD`, sans valeur de
  repli : son absence interrompt le démarrage, comme pour les autres secrets.
- Le corpus exposé compte **6 754 documents** sur les 6 836 chargés. L'écart de
  82 est le filtrage par licence, et il est visible dans les décomptes de
  `/sources/` et de `/statistiques/` — annoncer 380 documents pour une source
  dont l'API n'en sert que 298 ferait passer un filtrage voulu pour une panne.
- La documentation OWASP API Top 10 vit dans `docs/securite_api_donnees.md`,
  propre à cette API. Celle du service IA (C9) aura la sienne : les deux n'ont
  ni les mêmes données, ni les mêmes risques, ni la même surface.
