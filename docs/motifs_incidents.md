# Motifs récurrents des incidents

**Date :** 31 août 2026
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C20 (E5) — monitorage ; C18 (E4) ; C13 (E3) ; C19 (E5)

---

## Pourquoi ce document

Onze incidents ont été documentés entre le 26 et le 31 août 2026. Pris un par
un, ce sont onze accidents. Regroupés, ce sont **trois familles** — et une
famille se prévient, là où un accident ne fait que se réparer.

Ce document ne remplace pas les dossiers d'incident : il dit ce qu'ils ont en
commun, et quelle question poser pour éviter la prochaine occurrence.

---

## Famille A — Vérifié dans un contexte, employé dans un autre

**Quatre occurrences en quatre jours.** C'est ce qui la qualifie de famille.

| # | Vérifié dans… | Employé dans… | Ce qui a échoué |
|---|---|---|---|
| 003, 28/08 | un script, contexte de l'import | une requête HTTP, fil ou tâche distincte | La sonde de monitorage n'attachait aucun rappel. **22 heures de traces perdues** |
| 007, 30/08 | le poste, `DEBUG=True` | l'intégration continue, `DEBUG=False` | Quatre tests échouaient sur une redirection HTTPS que le poste ne déclenche jamais |
| — , 31/08 | un poste encombré, `staticfiles/` hérité d'un ancien `collectstatic` | un clone vierge | Aucune page ne se rendait hors DEBUG, faute de manifeste de fichiers statiques |
| 011, 31/08 | une **maquette**, où une valeur d'attente est attendue | une page servie, où elle est crue | Sept foyers de données fabriquées, dont un taux de réussite et une page de révision entière |

### Le mécanisme commun

Dans les quatre cas, **l'objet était correct dans le contexte où il a été
écrit**. Ce qui différait était l'environnement : un contexte d'exécution, une
variable, le contenu d'un répertoire — ou, pour le quatrième, l'intention de
lecture. Une valeur d'attente est vraie dans une maquette et fausse dans une
page servie ; rien n'a changé en elle, tout a changé autour.

Ce déplacement est invisible par construction : on ne voit pas ce dont on
dispose sans y penser. Le poste de développement porte un fichier produit six
semaines plus tôt, une variable posée dans un `.env`, un contexte
d'import — autant de choses qu'aucune ligne de code ne mentionne.

### La question à poser

> **Qu'est-ce que mon environnement fournit, que l'environnement cible ne
> fournira pas ?**

Trois réponses possibles, dans l'ordre où elles ont été découvertes :

1. **Un contexte d'exécution** — fil, tâche, processus. Éprouver depuis un
   serveur, jamais depuis un script seul.
2. **Une variable d'environnement** — `DJANGO_DEBUG=False uv run pytest`
   reproduit les conditions de la chaîne et de l'hébergeur.
3. **Un fichier présent sans être versionné** — corpus, `staticfiles/`, base
   SQLite, `.env`. La seule parade est de rejouer **depuis un clone** :

```bash
git clone --branch <branche> . /tmp/clone-ci
cd /tmp/clone-ci && DJANGO_DEBUG=False uv run --project <depot> pytest
```

Le 31/08, les deux premières reproductions n'ont rien donné et la troisième a
trouvé en une exécution. L'ordre a son importance : la plus coûteuse est aussi
la plus complète.

### La contre-mesure, sous sa forme la plus utile

Les trois premières occurrences se préviennent en **rejouant dans le bon
contexte**. La quatrième ne le peut pas : on ne « rejoue » pas une maquette en
production, on l'y laisse par inadvertance.

D'où une contre-mesure d'une autre nature, et c'est la plus utile que ce projet
ait dégagée :

> **Une valeur d'attente doit échouer visiblement si elle survit.**

Un `0`, un `—`, un « non mesuré », un `LOREM` en capitales. Jamais un 85 %,
jamais une durée plausible, jamais un nom de sujet crédible. **Une maquette doit
avoir l'air d'une maquette.**

C'est ce qui distingue une valeur d'attente qui se signale d'une valeur d'attente
qui se fond : la première meurt à la première relecture, la seconde survit des
mois. Sept fois, ici.

Le corollaire est déjà appliqué : les états vides de la page d'accueil sont
écrits comme une fonctionnalité, avec leurs propres tests. **Un état vide soigné
est ce qui rend le remplissage inutile.**

### La variante qui recouvre au lieu de combler

Six des sept foyers inventaient une donnée là où il n'y en avait pas. Le
septième — un compteur JavaScript parti de 154 minutes — **écrasait une donnée
mesurée** : la barre d'état affichait la série réelle de l'apprenant, rendue par
le serveur, et une minute plus tard le script la remplaçait.

Cette variante est plus grave, et elle explique pourquoi le motif est resté
invisible si longtemps : **la page affichait bien la donnée juste**. Qui la
regardait au chargement voyait un système correct. Il fallait attendre une
minute, sur la même page, pour voir la mesure disparaître — et personne ne
regarde une barre d'état pendant une minute.

Une fabrication qui comble un vide se démasque en comparant à zéro. Une
fabrication qui recouvre une mesure ne se démasque qu'en observant dans la
durée.

### Ce qui est en place

- `docs/strategie_tests.md` porte les trois niveaux de reproduction.
- La chaîne d'intégration s'exécute sur **toute** branche, à chaque poussée :
  elle ne protège que le code qui lui parvient, ce que l'incident 007 a montré
  au prix de trente-sept commits retenus en local.

---

## Famille B — L'instrument ne mesure pas ce qu'il prétend

| # | L'instrument | Ce qu'il mesurait vraiment |
|---|---|---|
| 001, 27/08 | un chargeur annonçant 6 836 documents | le nombre de lignes **envoyées**, sur une base restée vide |
| 003, 28/08 | une sonde se déclarant branchée | son propre démarrage, jamais les appels |
| 006, 29/08 | une sonde de santé nommant une collection | une collection que la recherche n'interrogeait pas |
| 009, 31/08 | une empreinte de corpus | les octets d'un fichier que SQLite réécrit à la lecture |
| 011, 31/08 | un « taux de réussite » sur le tableau de bord | `60 + xp // 50` — l'expérience gagnée, sans rapport avec la réussite |
| 011, 31/08 | `success_rate`, `total_study_time`, « sujets étudiés » | des grandeurs dérivées d'autres grandeurs sans lien avec ce que leur étiquette annonce |
| 011, 31/08 | le champ `attempts_count` | les soumissions, y compris après la réussite — jamais les tentatives avant réussite, que son nom annonce |

### Le mécanisme commun

L'instrument **fonctionne**. Il produit une valeur, à l'heure, sans erreur — et
cette valeur est vraie. Elle répond simplement à une autre question que celle
qu'on lui pose.

C'est ce qui rend cette famille plus retorse que la première : rien n'échoue.
Un contrôle absent se remarque ; un contrôle qui répond toujours, jamais.

### Les deux questions à poser

> **De quoi cette valeur est-elle l'effet — et non l'intention ?**

Un chargeur doit compter ce que la base contient, pas ce qu'il a envoyé. Une
sonde doit compter des appels tracés, pas son propre démarrage.

> **Qu'est-ce qui doit rester constant pour que ce contrôle reste silencieux ?**

Si la réponse contient quoi que ce soit qui bouge sans que l'objet surveillé
change, le contrôle est à réécrire. C'est ce qui a condamné l'empreinte sur les
octets de SQLite — et ce qui a conduit, le même jour, à régler le seuil de
latence par environnement plutôt qu'à le relever pour faire taire l'alarme
(décision 024).

### L'incident 011 appartient aux deux familles, et c'est instructif

Ses sept foyers relèvent de la **famille A** par leur origine : des valeurs
d'attente écrites pour une maquette et survivant dans une page servie.

Mais deux d'entre eux relèvent aussi de la **famille B** par leur nature : un
« taux de réussite » calculé sur l'expérience gagnée ne mesure pas ce que son
étiquette annonce, et l'aurait mal mesuré même écrit intentionnellement.

La distinction commande le traitement. Ce qui relève de A se prévient en
rendant les valeurs d'attente **visiblement fausses** ; ce qui relève de B se
prévient en demandant **de quoi la valeur est l'effet**. Un remplissage bien
signalé n'aurait pas sauvé `60 + xp // 50`.

### La troisième question, ajoutée le 31/08

> **Le nom de ce champ décrit-il ce qu'il contient ?**

`attempts_count` compte exactement ce qu'il compte, sans erreur : les
soumissions. C'est son nom qui promet autre chose — les tentatives avant
réussite — et la promesse a été crue deux fois, par deux personnes, le même
jour. Aucune ligne de code n'était fausse ; la lecture l'était.

C'est la variante la plus discrète de cette famille, parce qu'elle ne laisse
aucune trace : un nom est une promesse, et personne ne relit une promesse
tenue.

### Le corollaire, énoncé le 31/08

**Une alarme qui se déclenche toujours est une alarme qu'on cesse de lire.** Un
contrôle dont l'alerte serait permanente est pire qu'un contrôle absent :
l'absence se remarque, tandis qu'une alarme permanente s'apprend, et finit par
être traitée comme le bruit de fond d'un système en bon état.

### La variante où la mesure devient fausse sans qu'on y touche — 01/09

L'incident 012 ajoute une forme que les précédentes n'avaient pas : **le
compteur était juste, et il l'est resté**.

Un compteur intitulé « quiz terminés » lisait les sessions closes de type
`quiz`. Il était exact tant qu'une seule forme de quiz existait. Le quiz
multijoueur en a ajouté une seconde, qui n'ouvrait de session que pour l'hôte
et n'en clôturait aucune. Le compteur affichait alors zéro pour deux joueuses
qui venaient de terminer une partie de cinq questions.

Personne n'a modifié l'instrument. **C'est le monde qu'il mesurait qui s'est
élargi sans lui**, et le chiffre zéro est un résultat parfaitement valide :
rien n'échoue, rien ne se signale.

### La quatrième question, ajoutée le 01/09

Aux trois questions de la famille B s'en ajoute une, qui se pose au moment
d'écrire une fonctionnalité et non au moment de vérifier un chiffre :

> **Cette nouvelle voie mène-t-elle à une mesure existante — et cette mesure
> sait-elle qu'elle existe ?**

La parade tient en une ligne de code : lorsqu'une seconde forme d'une même
chose apparaît, la liste des formes se nomme (`TYPES_DE_QUIZ`), vit auprès du
modèle, et toute lecture qui annonce la chose s'y réfère. Aucune lecture ne peut
alors n'en voir qu'une moitié sans l'avoir décidé.

### La forme de question qui a révélé l'incident

L'autrice n'a pas signalé un défaut. Elle a demandé :

> le quizz multi n'est pas enregistré dans cet onglet performance /
> référentiel, **est-ce un choix ?**

Appliquée à une absence — un chiffre nul, un bloc vide, une ligne manquante —
cette question sépare en une phrase la décision assumée de l'oubli silencieux.
Elle n'accuse pas, donc elle n'appelle pas de justification : elle appelle une
vérification. Ici, la réponse était « en partie » — l'exclusion des quiz de la
progression était bien une décision consignée, l'invisibilité du compteur n'en
était pas une.

### La variante où l'outil de mesure mesure autre chose — 02/09

Avant de collecter la sixième source, chaque cible a été vérifiée :
`robots.txt` accessible, accès autorisé pour notre agent. Deux cibles sont
ressorties **interdites** — `fastapi.tiangolo.com` et `git-scm.com`. Elles
allaient être écartées sur ce constat.

Le constat était faux. `urllib.robotparser` télécharge le `robots.txt` **avec
son propre agent**, `Python-urllib/3.x`, que ces sites refusent. Le refus
portait donc sur *le téléchargement du fichier de règles*, jamais sur les pages
que ces règles autorisent. Refait en récupérant le fichier avec l'agent du
projet, puis en le passant à `parse()` : les deux cibles sont autorisées.

**L'instrument ne mesurait pas ce qu'il annonçait.** Il annonçait « ce site
interdit-il notre agent ? » et répondait en réalité « ce site répond-il à
l'agent d'urllib ? ». Rien n'échouait : la fonction rendait `False`, une valeur
parfaitement valide, et `False` veut dire « n'y allez pas ».

Ce qui rend cette variante particulière : **le défaut poussait à la prudence.**
Une mesure fausse qui aurait poussé à collecter sans droit se serait vue tôt ou
tard ; celle-ci aurait fait renoncer à deux sources licites, et personne
n'aurait rien remarqué — un périmètre plus petit ne se signale pas.

### La cinquième question, ajoutée le 02/09

> **Quand un contrôle interdit quelque chose, l'outil a-t-il posé la question
> que je crois ?**

Un contrôle qui autorise se vérifie tout seul : on s'en aperçoit si l'accès
échoue. Un contrôle qui interdit ne se vérifie jamais, parce qu'on renonce.
**Un refus doit donc être vérifié aussi soigneusement qu'une autorisation** —
ici, en refaisant la mesure par un autre chemin.

---

## Famille C — Écrit, joignable, jamais appelé

Ouverte à deux occurrences le 31/08 au matin, **déclarée le soir même** par la
troisième, et élargie le 01/09 par une quatrième d'une autre nature.

| # | Ce qui était écrit | Ce qui manquait |
|---|---|---|
| — , 31/08 | `language_preference`, choisi et enregistré | rien ne le lisait pour l'interface ; seul l'orchestrateur d'agents le consultait, pour la langue des quiz générés |
| — , 31/08 | `LANGUAGE_CODE = 'en'` avec un unique catalogue `fr` | aucune traduction n'était jamais appliquée |
| 010, 31/08 | route, vue, orchestrateur, agent — la chaîne entière d'enregistrement d'un quiz | **aucun appel depuis le navigateur** |
| — , 01/09 | un consumer WebSocket de 465 lignes, boucle de jeu complète | **une seconde implémentation, par sondage HTTP, faisait déjà le travail** |

### Le mécanisme commun

Un élément est écrit, correct, atteignable — et personne ne s'en sert. Rien
n'échoue, puisque rien ne s'exécute.

L'incident 010 en donne la forme la plus coûteuse : **le code mort ne signale
pas ses défauts, il les conserve.** Les tests écrits pour brancher cette chaîne
ont révélé qu'elle aurait échoué de trois façons si elle avait été appelée un
jour — dont une comparaison de dates qui n'a jamais pu aboutir depuis que la
méthode existe.

### La variante où le code mort ment sur le produit

La quatrième occurrence est d'une autre nature, et elle mérite d'être
distinguée.

Les trois premières étaient des **chemins oubliés** : quelque chose d'écrit que
personne n'appelait, et dont l'absence d'effet finissait par se constater. La
quatrième est un **doublon** : le quiz multijoueur avait deux implémentations
parallèles, un consumer WebSocket et un sondage HTTP. La seconde tournait ; la
première dormait.

Or c'est la première qui attirait le regard — un consumer moderne, une boucle
de jeu complète, un routage déclaré dans `asgi.py`. **Un lecteur du dépôt en
aurait conclu que le multijoueur fonctionne en temps réel.** Il fonctionne,
mais autrement, et par le chemin le moins flatteur.

C'est ce qui rend cette variante plus grave : **le code mort ne ment plus
seulement sur ce que le dépôt contient, il ment sur ce que le produit fait.**
Un chemin oublié laisse une fonctionnalité absente — on finit par s'en
apercevoir en l'utilisant. Un doublon dormant laisse une fonctionnalité
présente, décrite par le mauvais code, et rien dans l'usage ne le révèle : le
jeu marche.

Un jury lisant ce dépôt aurait été trompé sans qu'aucune ligne soit fausse.

La parade est la même, appliquée dans l'autre sens : après avoir demandé qui
appelle un code, demander **si quelque chose d'autre fait déjà ce travail**.

### La question à poser

> **Qui appelle ce code, et par quel chemin l'utilisateur y arrive-t-il ?**

Si la réponse est « la fonction est là », ce n'est pas une réponse.

> **Et quelque chose d'autre fait-il déjà ce travail ?**

Deux réponses à la première question valent pire qu'aucune.

### La parade

Un test qui **part de ce que l'utilisateur fait** — une requête sur l'URL réelle
— et qui vérifie **l'effet sur les données**, pas la présence d'une fonction.
Une couverture par fonction aurait atteint `submit_quiz_results` avec des
données fabriquées et serait passée au vert sur les trois défauts.

C'est la même discipline que pour un réglage : vérifier l'effet sur ce que
l'utilisateur reçoit, jamais la valeur en base. Un test affirmant « la
préférence est bien enregistrée » serait resté vert pendant toute la durée du
défaut.

---

## Ce que les trois familles partagent

Une action et son effet ne coïncident pas sans qu'on aille le constater.

La famille A porte sur **où** l'on constate, la famille B sur **quoi**, la
famille C sur **si** quelque chose s'exécute. Les trois se traitent par la même
discipline, et c'est la seule règle générale que ce projet retire de ses onze
incidents et de leurs répliques :

> Vérifier l'effet, dans les conditions où il se produira.

### Une occurrence qui vaut pour toutes : connaître le motif ne suffit pas

Le 31/08, en rédigeant la réserve 14 sur les exemptions CSRF, ce document a
écrit noir sur blanc : « aucun autre `@csrf_exempt` ne subsiste dans le projet
— vérifié le 31/08 ».

**La vérification a été faite après l'affirmation, et l'a démentie.** Une
troisième exemption attendait dans `apps/exercises`, sur la vue qui enregistre
les soumissions de code.

C'est-à-dire : le motif que ce document décrit — annoncer un état sans l'avoir
constaté — a été reproduit **dans le paragraphe même qui le décrivait**, par
quelqu'un qui venait d'en documenter dix occurrences.

Le paragraphe fautif est conservé dans la réserve 14, non réécrit. Il établit
ce qu'aucune des dix autres occurrences ne montrait aussi nettement :
**connaître un motif ne prémunit pas contre lui.** Seule la vérification
prémunit, et elle doit précéder l'affirmation, pas la suivre.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `incidents/` | Les onze dossiers, un par incident |
| `strategie_tests.md` | Les trois niveaux de reproduction d'un échec d'intégration |
| `decisions/024-seuil-de-latence-par-environnement.md` | Régler un indicateur juste dont le contexte a changé |
| `reserves.md`, réserve 9 | Un contrôle qui repose sur une convention d'exécution |
