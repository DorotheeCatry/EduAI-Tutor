# Note — l'architecture du contenu : corpus de formation et corpus documentaire

Note de préparation à l'oral et matière pour les rapports E1 et E4. Explique
comment le contenu pédagogique est organisé, d'où il vient, ce que les licences
autorisent, et pourquoi cette architecture rend la plateforme transposable à
n'importe quelle formation.

**Compétences concernées :** C1 à C5 (E1), C14 et C15 (E4), C10 (E3)

---

## 1. Le principe : deux corpus, deux rôles

Le contenu de la plateforme n'est pas un bloc. Il se répartit en deux ensembles
qui n'ont ni la même origine, ni le même statut juridique, ni le même usage.

| | Corpus de formation | Corpus documentaire |
|---|---|---|
| **Ce que c'est** | Les cours de l'organisme | Des ressources externes |
| **Source** | S3 — fichiers de l'organisme | S1, S2, S5 — API, scraping, big data |
| **Qui l'écrit** | L'organisme de formation | Des communautés et éditeurs tiers |
| **Licence** | Propriétaire de l'organisme | CC BY-SA, PSF — libres, avec attribution |
| **Rôle** | Porte le cours et structure le parcours | Enrichit, approfondit, illustre |
| **Collection** | `eduai_knowledge_base` | `eduai_corpus_documentaire` |
| **Volume actuel** | 387 fragments | 21 189 fragments |

Deux collections vectorielles distinctes, et non une seule filtrée : une purge
de l'une n'emporte pas l'autre, et une réindexation du corpus documentaire ne
touche pas aux cours.

---

## 2. Pourquoi cette séparation, et pas un corpus unique

### Un cours et une ressource ne répondent pas à la même question

Un cours **ordonne** : il dit dans quel ordre apprendre, à quel niveau, avec
quelles dépendances entre notions. Une ressource **répond** : elle traite un cas
précis, une erreur, une exception.

Stack Overflow ne sait pas qu'il faut comprendre les listes avant les
compréhensions de liste. Le corpus de formation le sait, parce qu'un pédagogue
l'a écrit.

### Les licences n'autorisent pas les mêmes usages

C'est la raison la plus contraignante, et elle est structurelle.

| Source | Licence | Ce qu'elle impose |
|---|---|---|
| Stack Overflow (S1, S5) | CC BY-SA 4.0 et 3.0 | Attribution obligatoire, partage aux mêmes conditions |
| Documentation Python (S2) | PSF License Agreement | Conservation de la notice de copyright |
| Corpus de l'organisme (S3) | Propriétaire | Droits détenus par l'organisme |
| Productions d'apprenants (S4) | Non redistribuable | Usage interne seulement |

Un cours assemblé sans distinction depuis les quatre mélangerait du contenu
librement redistribuable avec du contenu qui ne l'est pas, sans qu'on puisse
démêler l'un de l'autre après coup.

La séparation garde cette distinction opérante : le cours reste ce que
l'organisme possède, l'enrichissement puise dans ce qui est librement
utilisable, et chaque fragment documentaire porte son URL d'attribution.

### La mesure a tranché en faveur du documentaire pour la recherche

Sur la même requête, les distances retournées :

| Collection | Distances des trois meilleurs résultats |
|---|---|
| `eduai_corpus_documentaire` (21 189) | 0,286 — 0,290 — 0,293 |
| `eduai_knowledge_base` (387) | 0,600 — 0,606 — 0,633 |

Le corpus collecté répond nettement mieux à une question ponctuelle. Ce n'est
pas une surprise : il est fait de questions et de réponses, quand le corpus de
formation est fait de cours suivis.

C'est aussi ce qui confirme la répartition des rôles : la recherche documentaire
interroge le corpus collecté, la génération pédagogique s'appuie sur les cours.

---

## 3. La conformité aux licences, en pratique

Le respect des licences n'est pas une déclaration : il est porté par le schéma
de la base et par le code.

**Un manifeste de provenance** (`data/contents/provenance.json`) déclare
l'origine et la licence de chaque fichier du corpus de formation. Les fichiers
non déclarés sont chargés avec la licence « non documentée » — visibles, plutôt
que silencieusement assimilés.

**Une contrainte de base** lie licence et attribution : si la licence exige
l'attribution, l'URL de la source devient obligatoire. La règle est vérifiée par
le moteur, pas par la discipline du développeur.

**Un gestionnaire d'exposition** exclut du service tout document dont la
redistribution n'est pas autorisée. Éprouvé sur ses trois chemins d'accès :
liste, accès direct par identifiant, recherche plein texte. Un document non
redistribuable est introuvable par les trois.

**Une conséquence assumée** : les documents dont la licence n'est pas vérifiée
sont chargés en base — pour la traçabilité — mais jamais servis. Afficher un
contenu à un utilisateur est une forme de redistribution.

**Le corpus documentaire ne peut pas être remplacé par un contexte long.**
L'attribution CC BY-SA impose de citer la source de chaque passage affiché ; une
fenêtre de contexte, si vaste soit-elle, ne trace pas l'origine d'un fragment.
La récupération est donc une obligation juridique autant qu'un choix technique.

---

## 4. Ce que la minimisation retire, source par source

Aucune des cinq sources ne charge de donnée personnelle, et ce n'est pas un
effet du hasard.

| Source | Ce qui était disponible | Ce qui est collecté |
|---|---|---|
| S1 — Stack Overflow | Objet `owner` : pseudonyme, identifiant persistant, photographie | Rien. L'attribution passe par l'URL, où le site crédite lui-même l'auteur |
| S5 — dump Stack Exchange | 819 noms d'affichage en clair et 106 849 identifiants dans `Posts.xml` | Rien. Ces quatre attributs ne sont pas projetés, et `Users.xml` n'est jamais lu |
| S4 — productions d'apprenants | Identifiant, adresse IP, adresse électronique | Rien. L'identifiant sert à la jointure et n'est projeté nulle part |

Le cas de S4 mérite d'être détaillé : le lien entre plusieurs soumissions d'un
même apprenant est **nécessaire à la collecte** — rapprocher un échec de sa
correction — mais **pas au résultat**. Une fois la paire formée, le document
porte une erreur et sa correction ; rien en aval n'a besoin de savoir qui l'a
écrite.

Un garde-fou inspecte les colonnes retournées avant de lire une seule ligne :
ajouter une colonne personnelle à une requête arrête le traitement au lieu de
remplir le corpus en silence.

---

## 5. Ce qui rend la plateforme transposable

C'est le point à faire valoir en soutenance, et il repose sur trois éléments
configurables — pas sur une intention.

### Le corpus de formation est une donnée d'entrée

Un autre organisme dépose ses propres fichiers et relance l'orchestrateur.
Aucune ligne de code ne change. Le pipeline traite indifféremment n'importe quel
corpus : c'est ce que garantit le contrat de données commun aux cinq
extracteurs.

### Le référentiel de compétences est importable

Modules, compétences et niveaux vivent en base et se chargent depuis un fichier.
**Aucun libellé de compétence n'est écrit en dur** dans un gabarit ou une
constante. Le référentiel livré par défaut porte sur les modules du corpus, et
non sur celui d'un organisme tiers dont le contenu ne nous appartient pas.

### Le corpus documentaire est indépendant du domaine

Les extracteurs collectent selon des tags et des URL configurables. Changer de
domaine revient à changer les tags recherchés, pas la logique d'extraction.

### La formulation pour l'oral

> L'architecture est indépendante du domaine enseigné. Le corpus de formation et
> le référentiel de compétences sont des données d'entrée, pas des constantes du
> code. Déployer sur un autre programme pédagogique demande de charger deux
> fichiers, pas de réécrire l'application.

**Précaution :** l'énoncer comme une propriété de conception, pas comme un
résultat mesuré. La plateforme n'a jamais été déployée sur un second corpus.
Et ne pas l'annoncer avant d'avoir démontré que ça fonctionne sur le premier —
un jury qui entend « ça marche pour tout » avant d'avoir vu que ça marche pour
quelque chose entend « ça ne marche nulle part ».

---

## 6. Les limites, à énoncer avant qu'on les trouve

| Limite | Ce qu'il faut dire |
|---|---|
| **Un module rempli sur onze** | Le corpus de formation couvre le module Python. Ce n'est pas une limite du système mais un arbitrage de délai : écrire dix modules de cours demande plusieurs jours de rédaction, et le pipeline les ingérerait sans modification |
| **82 fichiers à la licence non vérifiée** | Chargés pour la traçabilité, exclus du service. Le manifeste les signale, il ne les invente pas |
| **Le corpus n'est pas traduit** | L'interface est bilingue, le contenu reste dans sa langue d'origine : un RAG cite ses sources telles qu'elles existent |
| **Deux PDF sans couche texte** | `ai__spacy_cheat_sheet.pdf` et `sql__window_functions_cheat_sheet.pdf` sont des images. Signalés à l'extraction plutôt qu'ignorés en silence. Aucun OCR : il produirait un texte approximatif présenté comme fiable |
| **Le corpus documentaire n'a pas de structure pédagogique** | C'est un ensemble de réponses, pas un cours. Il enrichit, il n'ordonne pas |

---

## 7. L'évolution conçue et non implémentée : le cours enrichissable

À présenter comme une conception aboutie, écartée par arbitrage de délai — pas
comme une idée vague.

**Le principe.** L'apprenant part d'un cours de base issu du corpus de
formation, l'enrichit là où il bloque en puisant dans le corpus documentaire, et
enregistre le résultat comme sa propre fiche de révision.

**Ce que ça change.** L'intelligence artificielle ne produit plus le contenu :
elle produit **la version personnelle** d'un contenu existant. Un cours généré
entre en concurrence avec une documentation officielle qui sera toujours
meilleure ; une fiche construite en butant sur des difficultés précises n'a
aucun équivalent, parce qu'elle n'existe nulle part ailleurs.

**Ce que ça demande de résoudre.** L'attribution doit suivre l'enrichissement :
si un passage vient d'une source sous CC BY-SA, la fiche personnelle doit
continuer de la citer. C'est faisable — chaque document porte son
`url_source` — mais c'est à concevoir, pas à improviser.

**Pourquoi ce n'est pas dans cette version.** Le chantier suppose d'écrire le
contenu de base **et** de construire le mécanisme d'enrichissement. Plusieurs
jours, quand le délai en offrait quatre.

---

## 8. Les questions probables, et les réponses

**« D'où vient le contenu de vos cours ? »**
Du corpus de l'organisme de formation, source S3 du pipeline. Les autres sources
n'écrivent pas les cours : elles fournissent des ressources d'enrichissement.

**« Avez-vous le droit d'utiliser ces données ? »**
Oui, et c'est vérifié plutôt que supposé. Stack Overflow est sous CC BY-SA,
la documentation Python sous licence PSF — deux licences qui autorisent la
redistribution avec attribution. L'attribution est portée par une contrainte de
base : une licence qui l'exige rend l'URL de source obligatoire. Les fichiers
dont l'origine n'est pas établie sont chargés mais jamais servis.

**« Pourquoi ne pas tout mettre dans un seul corpus ? »**
Trois raisons. Les licences ne permettent pas les mêmes usages. Un cours ordonne
là où une ressource répond. Et la mesure montre que le corpus documentaire
répond deux fois mieux à une question ponctuelle, quand le corpus de formation
porte la progression.

**« Comment adapteriez-vous cette plateforme à une autre formation ? »**
En chargeant deux fichiers : le corpus de cours et le référentiel de
compétences. Aucun libellé de compétence n'est dans le code, et le pipeline
traite n'importe quel corpus. C'est une propriété de conception, non encore
éprouvée sur un second déploiement.

**« Le RAG ne pourrait-il pas être remplacé par une fenêtre de contexte
longue ? »**
Non, et pour une raison juridique avant d'être technique. L'attribution CC BY-SA
impose de citer la source de chaque passage affiché ; un contexte long ne trace
pas l'origine d'un fragment. La récupération est ici une obligation.
