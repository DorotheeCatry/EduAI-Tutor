# 049 — Le ménage du code mort, et ce qui a été gardé

**Date :** 12/09/2026
**Compétences :** C18 (épreuve E4), C1 (E1), C3 (E1), C4 (E1), C10 (E3), C17 (E4)

## Contexte

Après le nettoyage de la couche agents (décision 048), relevé systématique du
code mort sur l'ensemble du dépôt : analyse syntaxique des définitions jamais
référencées, modules jamais importés, gabarits jamais rendus, noms d'URL jamais
atteints.

Le code mort n'est pas seulement encombrant. **Il ment** : il décrit un
dispositif qui n'existe pas, et personne ne le corrige puisque personne ne
l'exécute. Deux des trouvailles ci-dessous le montrent — un script qui ne
s'importait plus depuis deux semaines, et un contrat qui avait dérivé de la
réalité sans que rien ne puisse le signaler.

## Ce qui a été trouvé, et ce qui en a été fait

### Retiré

**Deux points d'API sans appelant.** `get_modules_api` et `get_sections_api`
dans `apps/courses/views.py`, avec leurs deux entrées d'URL. Aucun gabarit,
aucun script ne les atteignait — ni par nom d'URL, ni par chemin en dur.

*Nuance importante* : le premier relevé avait signalé tout le module
`apps/rag/module_loader.py` comme mort. C'était faux. La classe `ModuleLoader`
n'est référencée nulle part, mais l'instance `module_loader` l'est en onze
endroits — le générateur de cours s'en sert. Seules les deux vues sont mortes.

**Deux vues rendant des pages blanches.** `quiz_result` et `revision.review`
rendaient `quiz/quiz_result.html` et `revision/review.html`, deux gabarits
d'une seule ligne : `{% load i18n %}`. Rien n'y redirigeait, mais les deux URL
étaient atteignables par quiconque tapait l'adresse.

**`contexte_general()`** dans `apps/chat/contexte.py`. Elle rendait la
structure vide du « contexte des pages qui n'en ont pas », et n'était appelée
par personne : `templates/components/tuteur.html` porte déjà ce défaut en
JavaScript, comme valeur initiale de sa variable `contexte`, et c'est
celui-là qui s'exécute. Deux formulations du même défaut, dont une seule
vivante, finissent par diverger — ce que l'en-tête de ce module cherche
précisément à éviter.

**`redirect_to_login`** dans `eduai_project/urls.py`.

**Le modèle `CourseSection`.** Reliquat d'avant la refonte en trois couches
(référence / fiche / ajouts), où le découpage du cours est porté par
`PartieDeCours`. Sa table était vide — vérifié, 0 ligne — et `course.sections`
n'apparaissait dans aucune vue ni aucun gabarit. Migration
`0006_retire_coursesection`, appliquée. Un modèle Django non employé n'est pas
inerte : il crée une table, une clé étrangère et une contrainte d'unicité qui
décrivent un dispositif inexistant.

### Réparé

**`apps/rag/scripts/prepare_chroma.py` ne s'importait plus.** Il importait
`apps.rag.module_index_map`, un module de compatibilité supprimé le 30/08/2026
avec le remplacement de la liste blanche maison par RestrictedPython. Le script
levait `ModuleNotFoundError` avant d'exécuter une ligne, et rien ne l'a signalé
pendant deux semaines puisque rien ne l'importe.

Ce n'est pas un script accessoire : c'est lui qui construit la collection
pédagogique `eduai_knowledge_base`, celle que lisent le Chercheur et le
Pédagogue. Sans lui, elle n'était plus reconstructible. Il est branché
directement sur `module_loader`, sa source réelle, au lieu de passer par un
relais.

### Branché

**La sixième source était absente du point de lancement.** La table `SOURCES`
de `data_pipeline/orchestrator.py` portait S1 à S5. S6 avait pourtant sa
décision (039), sa réserve (20), son extracteur de 22 Ko, et le transformeur
comme le chargeur savaient la traiter — un commentaire de `transformer.py`
explique même comment le rattachement d'un document à sa source a été corrigé
*pour elle*.

La conséquence n'était pas théorique : `data/raw/` contient
`s6_documentation_bibliotheques.jsonl` et ses 1 005 enregistrements, qui
entrent dans le corpus transformé puis en base. L'extraction avait donc été
lancée à la main. **Le point de lancement unique ne savait pas reproduire le
jeu de données qu'il avait chargé** — ce qui vide de son sens la propriété de
rejouabilité que le référentiel demande de démontrer.

S6 est un second scraping : six sources, cinq types. Elle n'ajoute pas un type,
elle confirme que deux sources peuvent partager le même.

**Le contrat de transformation est devenu un contrat.**
`DocumentTransforme` était écrit, documenté, présenté en en-tête comme « le
contrat de sortie de la couche de transformation » — et importé par personne.
`transformer.py` écrivait des dictionnaires, `chargeur.py` en lisait.

Il avait d'ailleurs déjà dérivé : le champ `code_source`, ajouté au corpus réel
lors de l'arrivée de S6, n'y figurait pas. Personne ne pouvait le voir,
puisque rien ne comparait les deux.

Le champ manquant est ajouté, une méthode `depuis_dict` vérifie et construit,
et `_ecrire_corpus` l'appelle sur chaque document **avant d'ouvrir le fichier**.
Les 7 868 documents du corpus réel valident, et la transformation rejouée
produit les mêmes volumétries qu'auparavant.

### Gardé, avec la raison écrite

**Les cinq modèles de détail de `apps/api_data/models.py`** —
`DocumentApiRest`, `DocumentWeb`, `DocumentFichier`, `DocumentBigData`,
`DocumentBaseDonnees`. Le relevé les signale comme des classes que rien ne
référence, ce qui est exact.

Ils reflètent, dans l'ORM, les cinq tables de détail du schéma physique de
`eduai_data`, une par type de source collecté. `managed = False` : ils ne
créent rien, le schéma reste géré par `data_pipeline/load/sql/`. Les exposer
demanderait cinq sérialiseurs, cinq vues et cinq entrées d'OpenAPI — une
fonctionnalité que rien ne réclame. Un bloc de commentaire dit désormais tout
cela sur place, pour qu'un prochain relevé ne repose pas la question.

## Raisons

**Un dispositif que rien n'atteint finit par mentir sur ce qui existe.** Les
deux vues à page blanche et les deux points d'API donnaient l'impression d'une
surface fonctionnelle qui n'en était pas une.

**Ce qui n'est pas exécuté n'est pas corrigé.** `prepare_chroma` était cassé
depuis deux semaines. Le contrat de transformation avait dérivé d'un champ. Les
deux étaient invisibles pour la même raison : aucun chemin vivant ne passait par
eux. C'est l'argument le plus fort pour ne pas garder du code mort « au cas
où ».

**Un contrat qui n'est pas appliqué n'est pas un contrat**, c'est un
commentaire dans un fichier à part. La vérification a lieu au point d'écriture,
et elle lève : le chargeur écrit dans une base contrainte, et un corpus hors
contrat l'y ferait échouer une ligne à la fois, après en avoir déjà écrit
d'autres.

**Une table de sources est une preuve seulement si elle est complète.** Son
commentaire disait déjà qu'une découverte dynamique « masquerait une source
silencieusement retirée » ; la table explicite en masquait une silencieusement
oubliée.

**Vérifier avant de supprimer, y compris son propre relevé.** `module_loader`
aurait été supprimé sur la foi d'une analyse syntaxique qui avait raison sur la
classe et tort sur l'instance. Le relevé automatique désigne des candidats, il
ne tranche pas.

## Conséquences

`tests/test_code_mort.py`, onze tests : les quatre URL retirées lèvent
`NoReverseMatch`, les deux symboles retirés ont disparu, `prepare_chroma`
s'importe et sa carte d'index est peuplée, les six sources sont branchées avec
six classes distinctes, le contrat est importé et appelé, un document hors
contrat lève, et le corpus réel valide.

## Limite connue

`prepare_chroma` fonctionne, et son périmètre est partiel : `data_science_index.json`
fait zéro octet, et la carte d'index ne couvre que `python`.

**Cette limite était d'abord écrite ici comme un problème d'étiquetage de
sections.** Elle est plus large que cela, et la vérification faite après coup l'a
montré : sur les quatre modules du référentiel, un seul dispose de supports de
cours. Sept compétences sur vingt et une ont un cours de référence, quatorze
n'en ont aucun. Ce n'est pas un défaut de code et aucun correctif ne le résout —
c'est de la matière pédagogique qui manque. Consigné en **réserve 25**, à sa
place.
