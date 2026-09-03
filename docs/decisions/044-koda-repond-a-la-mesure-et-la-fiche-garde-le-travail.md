# 044 — Koda répond à la mesure, et la fiche ne garde que le travail

**Date :** 03/09/2026
**Compétences :** C10 (épreuve E3), C13 (E3), C17 (E4)

## Contexte

Dans une page de cours, écrire « ça va ? » à Koda produisait un cours entier
sur la compétence travaillée. La demande partait dans la recherche
documentaire, et l'invite ordonnait de répondre en s'appuyant sur les extraits
trouvés. Le modèle obéissait — il n'avait aucune raison de faire autrement.

Cette réponse était ensuite versée dans la fiche de l'apprenant, où elle
voisinait avec ses vraies questions.

Deux défauts distincts : la réponse n'était pas proportionnée à la demande, et
la fiche gardait tout.

## Options

1. **Demander au modèle de trier**, en lui faisant déclarer si l'échange mérite
   d'être conservé.
2. **Un second appel de classement** avant l'appel de réponse.
3. **Reconnaître les échanges courants dans l'application**, y répondre sans
   modèle, et n'enregistrer que le reste.

## Option retenue

La troisième, avec une consigne de longueur ajoutée à l'invite de fond.

`apps/chat/echange_courant.py` reconnaît une politesse à trois conditions
cumulées : le message est court, il ne porte aucun indice technique, et il
correspond **entièrement** à une tournure connue. La réponse est alors
assemblée localement, et rien n'est écrit dans la fiche.

## Raisons

**Répondre sans modèle ne coûte rien et ne peut pas dériver.** C'est déjà la
règle des salutations de Koda : une phrase assemblée ne peut pas partir dans un
cours au hasard, là où un modèle le peut. Et elle n'ouvre aucun chemin de
dépense non compté — le projet a déjà eu à en corriger deux.

**Faire trancher le modèle aurait coûté un appel pour décider s'il fallait
appeler.** Le quota compte quinze générations par jour : en dépenser une pour
savoir si « merci » mérite une réponse serait le contraire du but.

**La correspondance doit être entière, pas un simple début.** Mesuré : avec une
correspondance en début de ligne, « ça va marcher ? » passait pour un « ça
va ? » et « salut, ça déconne » pour un bonjour. Les deux sont de vraies
demandes. L'exigence de correspondance entière ramène le doute du bon côté.

**Le doute penche toujours vers la vraie question.** Se tromper dans un sens
coûte une politesse traitée comme une question — bénin. Se tromper dans l'autre
renvoie une vraie question d'un « ça marche ! » et ne l'enregistre jamais.

**Ce qui n'est pas conservé le dit.** Une mention discrète accompagne la
réponse. Sans elle, l'apprenant croirait que sa fiche garde tout, et
s'étonnerait plus tard de ne pas y retrouver une réponse.

## Limite connue

La reconnaissance est une liste de tournures françaises. Elle ne couvre ni les
autres langues, ni les formulations inattendues. C'est assumé : ce qu'elle ne
reconnaît pas est traité comme une vraie question, c'est-à-dire correctement
répondu et conservé. L'échec de cette heuristique est silencieux et sans
conséquence, ce qui est la seule forme d'échec acceptable pour une heuristique.
