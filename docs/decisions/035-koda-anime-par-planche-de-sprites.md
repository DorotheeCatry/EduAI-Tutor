# 035 — Koda animé par une planche de sprites, images composées comprises

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — accessibilité, poids ; C19 (E5) — provenance

## Contexte

Donner un visage au tuteur, à partir des illustrations de Camille Catry.

## Ce que l'inventaire a corrigé

Le chantier partait de « environ vingt planches d'une même pose ». Il y en a
**263, en cinq séquences distinctes**, en 1920×1080, pour 44 Mio — plus 100
frames dupliquées dans `theme/SLEEPING_TALKING/` et deux GIF égarés dans
`templates/` et `tests/`.

Surtout, **les cinq séquences ne partagent pas le même cadrage** : gros plan
avec bras levé, gros plan sans bras, buste, et deux séquences en pied.

## La mesure qui a décidé de la structure

Recalage des silhouettes, par recherche du meilleur décalage :

| Comparaison | Écart résiduel |
|---|---|
| Deux frames d'une **même** séquence | **0,0 %** |
| `NEUTRAL` contre `SLEEPING`, au meilleur décalage | **14,3 %** |

Les têtes n'ont ni la même taille ni la même inclinaison d'une séquence à
l'autre. **Deux séquences ne peuvent donc pas se succéder dans un même
emplacement sans un saut visible.** L'organisation en trois planches — gros
plan, buste, corps entier — n'est pas un rangement, c'est cette contrainte.

## Ce que la même mesure a rendu possible

Le registre étant parfait **à l'intérieur** d'une séquence, greffer la zone des
yeux d'une frame sur le corps d'une autre est invisible. Vérifié à
l'agrandissement.

Cela crée des images qui n'existent dans aucune séquence livrée :

| Image composée | Recette | Pourquoi elle manquait |
|---|---|---|
| Clignement au repos | corps #22 + yeux #16 | aucune frame n'a les yeux fermés **et** la bouche fermée |
| Attentif | corps #22 + yeux #19 | idem, paupières mi-closes |
| Clin d'œil | corps #22 + **un seul** œil de #16 | n'existe nulle part |

La zone des yeux n'a pas été choisie à l'œil : elle est obtenue en différenciant
une frame aux yeux ouverts et une frame aux yeux fermés, ce qui donne
exactement la région qui change.

## Technique d'animation

**Planche de sprites déplacée par `background-position`, pilotée en JavaScript.**

Deux options écartées :

- **`steps()` en CSS seul** : impose une cadence constante par état. Or le
  repos demande un clignement à intervalle **irrégulier** — un clignement
  métronomique donne un automate, pas un personnage. C'est le seul détail qui
  fait la différence entre « le tuteur est là » et « une image bouge ».
- **`<canvas>`** : même nombre de requêtes, mais retire l'image du flux du
  document, donc de la portée d'un lecteur d'écran, pour aucun gain ici.

Les durées vivent dans une table unique en tête du script, réglables sans
toucher au reste — comme le chantier l'exigeait.

## Poids, mesuré

| Planche | Images | Poids |
|---|---|---|
| Gros plan (toutes les pages) | 37 | **53 Kio** |
| Corps entier (accueil) | 48 | 178 Kio |
| Buste | 20 | 34 Kio |

Contre 3,4 Mio de GIF et 44 Mio de frames. Une requête par planche, et seule
celle du gros plan est servie sur toutes les pages.

**La réduction à 64 couleurs passe en mode palette**, ce qui ramène la
transparence de 247 niveaux à 18 : les bords anticrénelés durcissent.
**Ce choix tient à ce que l'application est sombre** — comparé à
l'agrandissement sur le fond du panneau, le durcissement est invisible, le
contour du dessin étant noir et le fond presque. Préserver l'alpha coûterait
91 Kio au lieu de 35. **Si un thème clair apparaît, les planches sont à
refaire.**

## Accessibilité

**`prefers-reduced-motion` coupe tout, et deux fois plutôt qu'une** : la
feuille de style fige le personnage même si le script tarde ou échoue, et le
script cesse en plus de parcourir la planche. L'une des deux suffirait en
régime normal — c'est bien pour cela qu'il en faut deux.

**Un réglage propre à l'application** s'ajoute à celui du système, sans le
remplacer : figer Koda ne doit pas obliger à changer un réglage qui vaut pour
tout l'ordinateur.

**Koda ne porte jamais seul une information.** « Le tuteur réfléchit… » et
« La réponse n'a pas pu être obtenue » restent dans le HTML, et un test échoue
si l'un des deux en disparaît.

**L'alternative textuelle ne décrit que les états qui signifient quelque
chose.** Le repos est `aria-hidden` : un lecteur d'écran ne doit pas annoncer
« Koda respire » toutes les deux secondes.

**Rien ne tourne dans le vide** : la boucle s'arrête si l'onglet passe en
arrière-plan ou si le panneau est replié.

## La séquence `ANGRY`, et pourquoi elle n'est pas branchée sur l'erreur

Elle ne montre pas un tuteur « contrarié » : elle montre un personnage **qui
crie, poings serrés, vapeur aux oreilles**. Sur une plateforme de formation
d'adultes, la servir quand un apprenant se trompe ferait dire au tuteur qu'il
est en colère **contre lui**.

Elle est donc assemblée et disponible, écourtée à vingt images, **mais n'est
branchée sur aucun événement** : elle est réservée au refus technique et au
quota atteint, et l'y brancher reste une décision à prendre.

## La règle enfreinte le jour même où elle a été écrite

Cette décision énonce plus haut : *deux séquences ne peuvent pas se succéder
dans un même emplacement sans un saut visible.* La planche en pied a pourtant
été assemblée en enchaînant `SALUTE` puis le repos de `JUMPING`, et posée sur la
page de connexion à la place du GIF.

Retour de l'autrice : « on dirait qu'il fait une crise d'épilepsie ».

Mesure faite après coup, avec le procédé qui avait servi à écrire la règle :

| Comparaison | Écart résiduel |
|---|---|
| Deux frames voisines du salut | **0,0 %** |
| Fin du salut → repos de `JUMPING`, au meilleur décalage | **30,2 %** |

Et ce meilleur décalage déplace le personnage de 60 px à droite et 70 px vers
le haut. Le saut n'était donc pas une impression : le geste se terminait par un
changement de pose **et** de position, suivi d'une boucle hachée.

**Le montage d'origine valait mieux qu'un remontage.** Le GIF est rétabli sur
la page de connexion. Ce qui est conservé de l'essai : un GIF s'anime quoi
qu'il arrive, il ignore `prefers-reduced-motion` — une image fixe de 18 Kio le
remplace donc pour qui a demandé à réduire les animations.

**Deux enseignements, et le second est le plus utile.** Écrire une règle ne
protège pas de l'enfreindre : elle était dans le même document, à trois
paragraphes de distance, et rédigée par la même main. Ce qui a rattrapé
l'erreur n'est pas la règle mais l'œil de quelqu'un devant l'écran — et la
mesure n'est venue qu'après, pour confirmer ce que le regard avait vu tout de
suite.

## Les planches inemployées ne sont plus livrées

Le corps entier et le buste sont retirés du dépôt : rien ne les affiche.

Ce projet a déjà payé le prix d'une ressource complète et inemployée — 465
lignes de consumer WebSocket qui laissaient croire à une fonctionnalité
existante (décision 031). Deux cent quatre-vingt-quinze kilooctets d'images
qu'aucune page ne charge racontent la même histoire, en plus discret. La table
d'états JavaScript qui les pilotait est retirée avec elles.

`python theme/koda/composer_planches.py --tout` les reconstruit le jour où
elles seront branchées — et il faudra alors **une planche par séquence**, pas
une par famille de cadrage : `SALUTE` et `JUMPING` ne sont pas plus recalées
entre elles que `NEUTRAL` et `SLEEPING`.

## Ce que ce choix laisse ouvert

**Le bras levé disparaît** en passant du gros plan `NEUTRAL` à `SLEEPING` : les
deux séquences ne sont pas raccordables, c'est le seul joint visible du
dispositif. Il survient après une longue inactivité, donc rarement sous les
yeux de quelqu'un.

**Les frames sources ne sont pas versionnées** (44 Mio) : les planches ne se
reconstruisent pas depuis un clone. Les cinq GIF, eux, le sont — ils
conservent la même suite d'images. Déclaré dans le manifeste de provenance
plutôt que subi.
