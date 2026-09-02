# 039 — Une sixième source : la documentation officielle des bibliothèques

**Date :** 2 septembre 2026
**Compétence visée :** C1 (épreuve E1) — collecte de données
**Compétences concernées :** C2 (E1) ; C4 (E1) — licence et attribution ; C21 (E5)

## Ce que S6 apporte, et ce qu'elle n'apporte pas

**S6 ne débloque aucun critère.** C1 exige cinq types de sources — service web,
scraping, fichier, base de données, système big data — et les cinq sont couverts
depuis S1 à S5. S6 est un **second scraping** : elle n'ajoute aucun type.

Ce qu'elle apporte est ailleurs. Le corpus couvre Python et la science des
données par les questions-réponses de Stack Overflow, mais ne contient **aucune
documentation de référence** sur les bibliothèques que le programme enseigne.
Un apprenant qui cherche la signature exacte d'une fonction pandas ne la trouve
pas. C'est un enrichissement du produit, pas une couverture de référentiel, et
il ne doit pas être présenté autrement.

## Le périmètre retenu

Six modules couverts, par des pages de départ explicites — jamais un parcours
automatique du site.

| Module | Cible | Pages | Fragments mesurés |
|---|---|---|---|
| 02 — Analyse de données | pandas, guide utilisateur | 9 | ~720 |
| 03 — SQL | PostgreSQL, tutoriel et requêtes | 10 | 157 |
| 04 — Apprentissage automatique | scikit-learn, modules | 10 | 667 |
| 05 — Apprentissage profond | PyTorch 2.13 | 5 | 234 |
| 06 — Vision par ordinateur | OpenCV, tutoriels Python | 39 | 309 |
| 08 — API web | DRF (10) et FastAPI (8) | 18 | 364 |

Le module 01 est déjà couvert par S2, qui scrape `docs.python.org`.

## Le volume, mesuré avant de lancer et non constaté après

**~2 450 fragments, soit +11,6 % du corpus (21 189), et environ deux heures
d'indexation** à vingt fragments par minute. À lancer hors session de travail.

Cette mesure a demandé une correction. Une première estimation comptait les
**unités d'extraction** — sections Sphinx, titres — et donnait 1 360 fragments.
Or l'indexation **redécoupe tout document** à 1 000 caractères avec 200 de
chevauchement (`apps/rag/splitter.py`) : le nombre de fragments ne dépend pas du
découpage à l'extraction, mais du volume de texte. Recomptée en caractères sur
les 58 pages, l'addition était **presque double**.

**`pandas/io.html` est écarté** : 251 230 caractères, 314 fragments à lui seul —
plus que le module 03 tout entier. C'est la référence exhaustive des entrées et
sorties, c'est-à-dire précisément ce que le cadrage exclut. Les neuf autres
pages du guide pandas sont conservées.

## Les licences, vérifiées à la source

Aucune n'est reprise d'un tableau : chacune a été relevée sur le dépôt du projet.

| Cible | Licence constatée |
|---|---|
| pandas, scikit-learn, PyTorch, DRF | BSD 3-Clause |
| PostgreSQL | Licence PostgreSQL |
| OpenCV | Apache 2.0 |
| FastAPI | MIT |

## Les quatre cibles écartées

**Git — écartée pour une raison de licence, et il faut la dire exactement.** La
documentation de Git est en **GPL v2**. Ce n'est pas une licence refusée : c'est
une licence dont les obligations sont d'une **autre nature** que celles des BSD,
MIT et Apache retenues ici. Elle impose d'attacher la licence et d'offrir la
source, ce qui demande un traitement propre — un mécanisme de redistribution que
ce corpus n'a pas et qu'il n'y a pas le temps de concevoir. **Ce n'est donc pas
un oubli, ni une cible de moindre qualité : c'est une obligation qui dépasse le
cadre de ce corpus.** Le module 09 rejoint les non couverts.

**LangChain — écartée sur le `robots.txt`.** Il répond 200 **avec du HTML** : ce
n'est pas un fichier de règles exploitable. Le socle prescrit d'annuler quand le
`robots.txt` n'est pas lisible, plutôt que de décider soi-même que l'absence de
règles vaut permission.

**Documentation Docker — écartée sur la structure, pas sur la licence** (Apache
2.0, vérifiée). Son conteneur de contenu ne s'identifie que par des classes
utilitaires — `min-w-0 flex-[2_2_0%]`. Un sélecteur bâti là-dessus casserait au
prochain remaniement du site **en produisant du contenu tronqué que rien ne
signalerait**. Le cadrage l'interdisait explicitement ; s'y tenir coûte le
module 09, déjà perdu par ailleurs.

**Modules 10 et 11 — non couverts, faute de sources libres.** Les documentations
AWS et Azure restreignent la reproduction ; l'agilité n'a pas de documentation
technique officielle. C'est une limite du domaine, pas du dispositif : le
pipeline ingérerait ces contenus sans difficulté si des sources libres
existaient.

## Ce que la vérification a corrigé du cadrage initial

**Deux cibles ont failli être écartées sur un artefact d'outil.**
`urllib.robotparser` télécharge le `robots.txt` avec son propre agent, refusé
par plusieurs de ces sites : le refus portait sur le fichier de règles, pas sur
les pages. FastAPI et Git étaient donnés interdits et ne le sont pas. Consigné
au registre des motifs, famille B.

**PyTorch n'est pas joignable à l'URL attendue.** `/docs/stable/` sert une page
de redirection JavaScript de quarante-cinq caractères. Le périmètre vise une URL
versionnée, ce qui crée une péremption silencieuse — réserve 20.

**Le sélecteur de S2 ne vaut que pour deux cibles.** Seules pandas et
scikit-learn produisent des balises `<section>`. Les autres ont chacune leur
conteneur, tous relevés : `div.sect1` pour PostgreSQL, `div.textblock` pour
OpenCV, `div.md-main__inner` pour DRF et FastAPI. Le découpage s'y fera par
titres `h2`/`h3`, présents partout.

## Conséquences

- Chaque document portera en métadonnée **le module du référentiel** auquel il
  se rattache : gratuit à l'extraction, coûteux à reconstituer après coup.
- La langue est `en` pour les six cibles.
- Pause de deux secondes entre requêtes, `User-Agent` identifiant le projet.
  Avec 91 pages, la collecte prendra une demi-heure — ce n'est pas une raison
  d'accélérer : ces sites sont des services gratuits.
- Nomenclature `s6` et licences à ajouter dans `04_donnees_reference.sql` avant
  chargement, faute de quoi le chargeur bute sur la clé étrangère — comportement
  voulu.
