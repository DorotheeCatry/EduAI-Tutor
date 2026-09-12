# 050 — L'import de cours accepte plusieurs corpus, et lit les diaporamas

**Date :** 12/09/2026
**Compétences :** C17 (épreuve E4), C10 (E3), C21 (E5), C4 (E1)

## Contexte

La réserve 25 a établi que trois modules du référentiel sur quatre n'ont aucun
cours de référence : sept compétences sur vingt et une en portent un. La cause
immédiate est l'absence de matière — seul `01_python` contient des supports.

Mais deux verrous s'y ajoutaient, et ceux-là sont dans le code. Ils ont ceci de
particulier qu'ils **auraient survécu à l'arrivée de la matière** : déposer des
supports dans `02_data_analysis` n'aurait rien changé.

**Le rattachement ne déclarait qu'un seul corpus.**
`apps/courses/donnees/rattachement-cours.json` portait, à plat, un unique
couple :

```json
"index": "data/contents/index/python_index.json",
"repertoire": "data/contents/courses/01_python",
```

L'importeur lisait ces deux clés et rien d'autre. Un second module aurait exigé
une modification du code.

**Le seul support hors Python n'était pas lisible.**
`data/contents/courses/03_sql/relations entre les tables.pptx` — douze
diapositives sur les cardinalités et les relations entre tables — est versionné
depuis le début. `prepare_chroma` lit `.md`, `.ipynb`, `.pdf` et des images. Le
diaporama n'était donc ni indexé ni consultable par les agents.

## Options

1. **Attendre la matière** et lever les verrous quand elle arrivera.
2. **Lever les verrous maintenant**, sans créer de contenu.
3. **Convertir les supports manquants** depuis une source externe.

## Option retenue

La deuxième. Aucun cours n'est créé ; ce qui change est qu'un support déposé
sera désormais pris.

**Le fichier de rattachement déclare une liste `corpus`.** Chaque entrée porte
son index, son répertoire, ses `sous_modules`, et éventuellement ses
`exceptions` et ses `hors_parcours`. La forme à plat reste acceptée et vaut pour
un corpus unique — l'option `--rattachement` permet de passer un autre fichier,
et rien ne justifie de casser ceux qui existent.

**`prepare_chroma` lit le `.pptx`**, via `python-pptx`, une diapositive par
bloc, titrée `## Diapositive N`, tableaux compris.

## Raisons

**Les parties sont rassemblées par compétence AVANT publication, pas après.**
C'est le point de conception qui compte. `publier_le_cours` met de côté le
cours actif d'une compétence et en publie un neuf : publier corpus par corpus
aurait fait effacer, par le second, le cours que le premier venait de publier
sur une même compétence. Deux corpus peuvent légitimement l'alimenter.

**Tous les corpus sont vérifiés avant qu'aucun ne soit lu.** La règle d'origine
de cet import promet qu'« aucun cours n'a été publié » quand l'index et le
disque divergent. Vérifier au fil de l'eau aurait publié les premiers avant
d'échouer sur le dernier, et la promesse ne vaudrait plus. Les écarts de tous
les corpus sont rassemblés et rapportés d'un coup, comme ils l'étaient déjà à
l'intérieur d'un corpus.

**`python-pptx` plutôt que `UnstructuredPowerPointLoader`.** Ce dernier tire
`unstructured` et sa chaîne d'analyse documentaire, hors de proportion avec le
besoin : la seule chose demandée est le texte. `python-pptx` lit le format
directement.

**Le découpage par diapositive n'est pas cosmétique.** Un diaporama concaténé
d'un bloc perd sa structure, et le découpeur du RAG couperait au milieu d'une
notion. Le numéro de diapositive donne au fragment une adresse que l'apprenant
retrouve dans le fichier d'origine. Le texte des tableaux est repris cellule par
cellule : dans un support sur les relations entre tables, le tableau **est** le
contenu.

**Ce n'est pas une nouvelle fonctionnalité, c'est un verrou levé.** Le
dispositif de cours de référence existe, il fonctionne, et il était bridé à un
module par une donnée et par une liste d'extensions. Rien dans l'interface ne
change.

## Conséquences

`tests/test_couverture_multi_modules.py`, cinq tests : deux corpus alimentent
deux modules, deux corpus sur une même compétence s'additionnent au lieu de
s'écraser, un écart dans n'importe lequel arrête tout avant publication, la
forme à plat reste acceptée, et le diaporama SQL rend son texte structuré.

L'import réel est inchangé : sept compétences, mêmes volumétries, idempotent à
la relance.

## Limite connue

**La matière manque toujours.** Ces verrous levés, `02_data_analysis`,
`04_machine_learning` et les sept autres répertoires restent vides, et
`data_science_index.json` fait toujours zéro octet. La réserve 25 reste ouverte
et le restera tant que les supports n'existent pas — c'est le seul point qu'un
correctif ne résout pas.

Le diaporama SQL est désormais **indexable**, ce qui ne veut pas dire importé
comme cours : `importer_cours` lit des markdown et ne sait pas lire un `.pptx`.
Le faire entrer au catalogue des cours de référence demanderait d'étendre aussi
la lecture de l'import, et surtout un `sql_index.json` qui n'existe pas. Ce
n'est pas fait ici.
