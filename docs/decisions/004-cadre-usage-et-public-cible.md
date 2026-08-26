# 004 — Cadre d'usage et public cible

**Date :** 26/08/2026
**Statut :** adoptée
**Compétences concernées :** C14 (E4) — analyse du besoin ; C4 (E1) — RGPD ;
C17 et C19 (E4) — accessibilité

## Contexte

L'application avait été développée sans cadre d'usage explicite. Cette absence
posait trois problèmes concrets, apparus lors de la conception de la base de
données :

1. Impossible de déterminer si des données de mineurs seraient traitées, donc
   impossible de fixer les obligations RGPD applicables.
2. Aucune partie prenante identifiable, alors que l'analyse du besoin attendue
   par C14 repose sur des acteurs nommés et des besoins exprimés.
3. Aucune justification du périmètre du corpus pédagogique.

Le cadre devait être arrêté avant l'écriture du modèle physique, les décisions
de pseudonymisation en dépendant directement.

## Options envisagées

**A — Logiciel interne d'établissement scolaire.**
Écartée. Le public inclurait des mineurs, ce qui impose en France le recueil du
consentement parental pour les moins de quinze ans (article 45 de la loi
Informatique et Libertés, transposant l'article 8 du RGPD). Ce mécanisme
suppose une chaîne complète — recueil, preuve, révocation, vérification de
l'âge — absente de l'application et non réalisable dans le délai disponible.
Retenir ce cadre aurait consisté à déclarer une conformité inexistante.

**B — Site d'auto-formation ouvert au grand public.**
Écartée pour deux raisons. La première reproduit le problème précédent : un
service ouvert accueille des mineurs sans qu'on puisse le prévenir, et
l'exclusion déclarative n'y est pas crédible. La seconde tient à l'analyse du
besoin : un service grand public n'a ni commanditaire ni partie prenante
identifiable, ce qui prive C14 de matière.

**C — Plateforme d'un organisme de formation professionnelle au développement.**
Retenue.

## Décision

EduAI Tutor s'adresse aux apprenants adultes d'un organisme de formation
professionnelle au développement — public en reconversion ou en montée en
compétences. **Le service est réservé aux personnes majeures**, mention à
porter dans les conditions générales d'utilisation et dans le registre des
traitements.

Le besoin adressé : un accompagnement disponible en dehors des heures
d'encadrement, adapté au niveau de chaque apprenant, sur un corpus aligné sur
le référentiel de la formation suivie.

Trois parties prenantes sont identifiées : les apprenants (utilisateurs
directs), les formateurs (prescripteurs du corpus et destinataires des signaux
de progression), la direction de l'organisme (responsable du traitement au sens
du RGPD).

## Conséquences

**Sur le RGPD.** Le consentement est recueilli directement auprès de personnes
majeures, sans intervention d'un tiers. Les données traitées restent néanmoins
des données à caractère personnel : compte, progression, soumissions de code.
Le principe de minimisation s'applique à la source S4 du pipeline, qui extrait
des soumissions d'exercices — aucun identifiant utilisateur, aucune adresse IP,
aucune adresse électronique ne doit être chargé dans la base `eduai_data`, et
la rétention y est fixée à quatre-vingt-dix jours (voir décision 003 et
`docs/rgpd_eduai_data.md`).

**Sur l'accessibilité.** Un organisme de formation accueille des apprenants en
situation de handicap et relève d'obligations légales d'accessibilité
numérique. Les objectifs WCAG 2.1 AA / RGAA cessent d'être une bonne pratique
pour devenir une exigence du cadre d'usage, intégrée aux critères
d'acceptation des développements.

**Sur le corpus.** Le périmètre thématique du corpus — Python, analyse de
données, SQL, apprentissage automatique, agents et modèles de langage, API web,
outils de développement, cloud, agilité — cesse d'être arbitraire : il
correspond au programme d'une formation au développement en intelligence
artificielle. L'autrice du projet en est elle-même une utilisatrice cible, ce
qui a permis une analyse du besoin de première main plutôt qu'une persona
construite.

**Sur l'architecture multi-agents.** Le cadre justifie la disponibilité
permanente et l'adaptation au niveau : un adulte en reconversion travaille
majoritairement en dehors des heures d'encadrement et se heurte à des blocages
qu'aucune documentation statique ne résout.

**Limite assumée.** L'ouverture au grand public, ou à un public scolaire, reste
une évolution envisageable. Elle imposerait la mise en place d'une chaîne de
vérification de l'âge et de recueil du consentement parental, ainsi qu'une
révision du registre des traitements. Elle est identifiée, non implémentée, et
documentée comme telle.
