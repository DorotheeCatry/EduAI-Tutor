# 037 — Koda fête ou boude à la fin d'une partie, et la phrase décide du sens

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C13 (E3) — accessibilité ; C21 (E5)

## Contexte

> un Koda content si tu gagnes et un Koda pas content quand on perd […] pour le
> perdant il dit des trucs rigolos genre « Mais j'avais parié avec les autres
> Koda que t'étais le best ! »

Cette demande **résout une question laissée ouverte** par la décision 035.

## La question qu'elle résout

La séquence `ANGRY_TALKING` avait été assemblée puis laissée débranchée, avec
cette réserve : elle ne montre pas un tuteur « contrarié », elle montre un
personnage **qui crie, poings serrés, vapeur aux oreilles**. Servie quand un
apprenant perd, elle lui dit que le tuteur est en colère contre lui — ce qui,
sur une plateforme de formation d'adultes, est exactement ce qu'il ne faut pas
faire.

La phrase proposée par l'autrice retourne l'image entièrement. **Koda n'est pas
fâché contre le perdant : il est fâché d'avoir perdu son pari — un pari qu'il
avait fait *sur* lui.** La même colère, adressée à soi-même, devient une
marque de confiance.

**C'est la phrase qui décide de ce que montre l'image.** Le dessin n'a pas
changé ; ce qui l'accompagne change ce qu'il veut dire. Un test interdit
désormais qu'une phrase de défaite désigne la performance de l'apprenant.

## Ce qui a été retenu

- Le vainqueur voit `JUMPING`, le perdant `ANGRY_TALKING`, chacune **en boucle
  entière et seule dans sa planche**. Les deux reviennent à leur pose de départ
  (0,0 % et 4,5 % d'écart entre première et dernière image) : elles bouclent
  d'elles-mêmes, sans enchaînement.
- Cinq phrases par issue, **tirées au hasard**, déclarées dans le gabarit et
  donc traduites. Une seule phrase serait vue deux fois et cesserait d'amuser.
- Un joueur seul dans sa salle est traité en vainqueur : il n'a perdu contre
  personne.

## Pourquoi les phrases ne sont pas engendrées par le modèle

Quinze générations par jour et par apprenant (décision 030). Une partie de quiz
n'a pas à en dépenser une pour faire une blague — et une liste fixe ne peut pas
produire une phrase malheureuse un jour de malchance.

## Accessibilité

Le personnage est `aria-hidden` : l'issue de la partie est portée par le
classement, le podium et la phrase, tous du texte. Koda accompagne, il ne dit
rien que l'écran ne dise déjà.

Le refus d'animation de l'apprenant voyage sur le corps du document : le Koda
de fin de partie est créé en JavaScript après le chargement, et n'a pas d'autre
moyen de connaître ce réglage.

## Ce que ce choix laisse ouvert

Le quiz solo n'a pas d'écran de fin animé. Rien n'empêche de l'y porter, mais
la notion de « perdant » y est moins nette : on ne perd pas contre quelqu'un,
on répond juste ou faux. La phrase devrait être écrite autrement, et c'est un
autre travail que de réemployer celles-ci.
