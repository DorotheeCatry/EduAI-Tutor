# 010 — Source S4 : extraction de eduai_app sans identifiant, pas même pseudonyme

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C1, C2 et C4 (E1)

## Contexte

La source S4 est le quatrième type exigé par le référentiel : une base de
données. Elle extrait les productions d'apprenants de `eduai_app` vers le
corpus `eduai_data`.

Le paragraphe 5 du document RGPD avait posé une règle conditionnelle : un
identifiant pseudonyme ne serait retenu **que si** le lien entre plusieurs
soumissions d'un même apprenant était nécessaire au traitement. L'écriture de
l'extracteur obligeait à trancher cette condition.

## Options

1. **Un identifiant pseudonyme dans `eduai_data`.** Permettrait de rattacher
   plusieurs documents à un même apprenant, et donc d'honorer une demande
   d'effacement au titre de l'article 17 en supprimant les documents concernés.
   Coût : `eduai_data` cesse d'être une base sans données personnelles, avec
   tout ce que cela entraîne — base légale, durée, sécurité, registre.
2. **Aucun identifiant, et renoncer au rapprochement.** Chaque soumission
   devient un document isolé. On perd la paire « erreur puis correction », qui
   est le seul apport de cette source qu'aucune source externe ne fournit.
3. **Le rapprochement à la collecte, aucun identifiant au résultat.**

## Décision

Option 3. `user_id` est utilisé dans la jointure latérale de
`s4_soumissions_corrigees.sql`, et projeté nulle part.

Le raisonnement tient en une distinction : le besoin de lien porte sur la
**collecte**, pas sur le **résultat**. Constituer la paire exige de savoir que
deux soumissions viennent de la même personne. Une fois la paire constituée, le
document porte une erreur et sa correction — plus rien en aval n'a besoin de
savoir qui l'a écrite. La condition posée au paragraphe 5 n'est donc pas
remplie, et l'identifiant pseudonyme n'a pas lieu d'être.

## Conséquences

- **`eduai_data` ne contient aucune donnée à caractère personnel**, pour aucune
  de ses cinq sources. C'est le résultat recherché depuis le paragraphe 3 du
  document RGPD, non un effet de bord.
- **Une demande d'effacement est sans objet sur `eduai_data`** et s'exerce
  entièrement sur `eduai_app`. La contrepartie est assumée : un document déjà
  versé au corpus ne peut pas être retiré à la demande d'un apprenant, faute de
  pouvoir l'identifier. Il disparaît par la purge d'ancienneté — d'où la
  rétention de 90 jours, la plus courte du corpus.
- **Deux garanties tenues par le moteur, non par l'intention.** La connexion à
  `eduai_app` est ouverte en lecture seule : le pipeline ne peut pas écrire dans
  la base qui porte les comptes. Un garde-fou inspecte les colonnes retournées
  avant de lire la moindre ligne : ajouter `user_id`, un courriel ou une adresse
  IP à un fichier `.sql` interrompt l'extraction. Une règle qui ne vit que dans
  la documentation ne survit pas à une modification distraite — même
  raisonnement qu'en décision 009 pour le refus de `Users.xml`.
- **Un pseudonyme, s'il avait été retenu, serait resté une donnée personnelle**
  au sens du considérant 26 : la table de correspondance existe dans
  `eduai_app`. Le présenter comme une anonymisation aurait été une erreur.

## Choix techniques

- **Jointure latérale** plutôt qu'auto-jointure avec `DISTINCT ON` : pour chaque
  échec on veut la première réussite **postérieure**, et non la première
  réussite absolue. Vérifié sur jeu d'essai : un apprenant dont la seule
  réussite précède l'échec ne produit aucune paire, ce qu'un `DISTINCT ON`
  global aurait faussement apparié.
- **Deux requêtes distinctes** plutôt qu'une union : soumissions corrigées et
  méprises conceptuelles produisent des documents de nature différente. Les
  fondre imposerait des colonnes nulles de part et d'autre et rendrait
  illisibles les choix de jointure, que C2 demande de documenter séparément.
- **Fenêtre de collecte de 90 jours**, alignée sur la rétention de la source :
  collecter au-delà produirait des enregistrements que la purge supprimerait à
  l'exécution suivante.
- **Une base vide est un succès à zéro enregistrement.** Contrairement à S1, où
  l'absence de résultat signale une panne d'API, une base applicative sans
  soumission est l'état normal d'une base récemment créée. Faire échouer le
  pipeline pour cette raison serait une fausse alerte permanente.

## Vérification

Jeu d'essai posé dans `eduai_app` puis retiré : deux apprenants, un exercice,
quatre soumissions, une méprise. Résultat conforme — une paire produite pour
l'apprenant dont la réussite suit l'échec, aucune pour celui dont la réussite
la précède, un document de méprise. Recherche dans la sortie de `essai_a`,
`essai_b`, `@essai.test`, `192.0.2`, `user_id` et `ip_address` : aucune
occurrence. Garde-fou éprouvé sur cinq projections, dont `author_email`,
`submitter_ip_address` et `student_username` : toutes refusées.
