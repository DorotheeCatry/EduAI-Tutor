# Incident 012 — Une partie jouée, comptée nulle part

**Date :** 1er septembre 2026
**Composant :** `apps/quiz/views.py`, `apps/agents/agent_watcher.py`, `apps/tracker/`, `apps/accueil/`
**Gravité :** moyenne — aucune partie multijoueur n'a jamais compté dans le suivi
**Statut :** résolu, vérifié, et rattrapé sur la partie déjà jouée
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C20 (E5) — données du suivi ; C17 (E4)

---

## 1. Déclenchement

L'autrice, après avoir joué une partie à deux navigateurs, a posé une question
de vérification :

> le quizz multi n'est pas enregistré dans cet onglet performance /
> référentiel, est-ce un choix ?

La question mérite d'être citée telle quelle, parce qu'elle **distingue deux
choses que le code confondait**.

## 2. Ce que la vérification a trouvé

Une partie de la réponse était bien un choix, déjà consigné : la **progression
par compétence** exclut les quiz, parce qu'un questionnaire mesure la
reconnaissance et non la production (décision 028). Ce point-là est intact.

L'autre partie n'en était pas un. La base disait :

```
Dodo | quiz | Manipuler les listes, dictionnaires et ensembles | score - | fin aucune
```

Une seule ligne, pour une partie à deux joueurs. Et elle est incomplète.

**Ce qui se passait :**

1. La génération du quiz ouvre une `LearningSession` — au nom de celui qui a
   demandé la génération, c'est-à-dire **l'hôte seul**. Les autres joueurs
   n'ont jamais eu de ligne du tout.
2. `end_session()` n'est appelée que depuis le quiz solo. En multijoueur, rien
   ne clôt cette session : ni `end_time`, ni `score`.
3. Le compteur de la page filtre sur `end_time__isnull=False,
   score__isnull=False`. La session existait donc, et ne comptait pas.

Résultat : deux joueuses venaient de terminer un quiz de cinq questions, et la
page leur annonçait **zéro quiz terminé**.

## 3. Famille du motif

**Famille B — l'instrument ne mesure pas ce qu'il annonce.**

Le compteur s'intitule « quiz terminés ». Il ne pouvait structurellement en
voir qu'une forme sur deux. Rien n'échouait, aucune erreur n'était levée : le
chiffre zéro est un résultat parfaitement valide, et c'est ce qui le rend
indétectable sans y regarder de près.

La variante est instructive : ici, **l'instrument était juste pour le solo**.
C'est en ajoutant une seconde voie vers la même mesure que le défaut est né,
sans que la première cesse de fonctionner. Un compteur correct pour un chemin
sur deux ne se signale nulle part.

## 4. Correction

Trois gestes, pas un.

**Une session par participant, ouverte et close ensemble** à la fin de la
partie (`cloturer_les_sessions_de_la_partie`), plutôt que la clôture de celle
de l'hôte — qui n'aurait rien réparé pour les invités.

**Le score retenu est le pourcentage de bonnes réponses, pas les points.** Les
points récompensent la vitesse ; la page affiche une moyenne que l'apprenant
lira comme une réussite. Les points sont conservés dans `metadata`, à leur
place.

**Un type distinct, `quiz_multijoueur`, lu partout où une lecture annonce
« quiz ».** La constante `TYPES_DE_QUIZ` vit auprès du modèle et sert au
tableau de la page Référentiel comme au bloc « dernière activité » de
l'accueil. Le type reste distinct en base — il dit d'où vient la session — mais
aucune lecture ne peut plus n'en voir qu'une moitié sans le décider
explicitement.

## 5. Rattrapage de la partie déjà jouée

La partie du 31 août était terminée : l'arbitrage ne repasse pas dessus. La
commande `cloturer_parties_terminees` crée les sessions manquantes à partir de
ce que la base contenait déjà — bonnes réponses, points, horodatages. Elle
**ne fabrique aucune donnée** : elle tire les conséquences d'un événement
réellement enregistré. Elle est idempotente et dispose d'un mode `--a-blanc`.

Résultat vérifié :

```
Dodo     | quiz_multijoueur | score 60.0 | Manipuler les listes, dictionnaires et ensembles
Caroline | quiz_multijoueur | score 20.0 | Manipuler les listes, dictionnaires et ensembles
```

Soit 3 bonnes réponses sur 5 et 1 sur 5 — ce que disaient déjà les six erreurs
enregistrées.

## 6. Ce que l'incident laisse derrière lui

La session ouverte par la **génération** du quiz reste ouverte en multijoueur :
personne ne la clôt, et le filtre l'ignore. Elle ne fausse aucun compteur, mais
c'est une ligne pendante. Consignée en réserve plutôt que corrigée : le solo
emprunte le même chemin et le clôt correctement, et modifier ce point toucherait
les deux formes de quiz à trois jours du rendu.

## 7. Ce qu'on en retient

**Ajouter une seconde voie vers une mesure existante, c'est risquer de rendre
la mesure fausse sans toucher à son code.** Le compteur n'a pas changé ; c'est
le monde qu'il mesurait qui s'est élargi sans lui.

La question de l'autrice — « est-ce un choix ? » — est la bonne forme. Elle
n'affirme pas un défaut : elle demande si l'absence est délibérée. Appliquée à
un chiffre nul, elle sépare en une phrase la décision assumée de l'oubli
silencieux.
