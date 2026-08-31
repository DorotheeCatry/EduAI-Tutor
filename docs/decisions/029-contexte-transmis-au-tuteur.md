# 029 — Ce que le tuteur reçoit, et ce qu'il ne recevra jamais

**Date :** 31 août 2026
**Compétence visée :** C10 (épreuve E3) — intégration du modèle
**Compétences concernées :** C17 (E4) ; C13 (E3) ; C9 (E2) ; C21 (E5)

## Contexte

Le chat vivait dans sa propre page. Pour l'utiliser, l'apprenant devait quitter
ce sur quoi il travaillait — c'est-à-dire précisément ce qui motivait sa
question. Il devait ensuite réexpliquer par écrit un contexte que
l'application connaissait déjà.

Déplacer le chat dans un panneau latéral ne suffisait pas : un chat sans
contexte reste un chat, où qu'il soit affiché. Ce qui fait la valeur du
chantier est que le tuteur **sache sur quoi l'apprenant travaille**.

## Ce qui est transmis, par page

| Page | Transmis | Borne |
|---|---|---|
| **Cours** | Titre du cours, intitulé de la section lue, corps de **cette section seule** | 2 000 caractères |
| **Exercice** | Énoncé, code actuellement saisi, dernier message d'erreur | 800 / 2 000 / 500 |
| **Quiz** | Énoncé de la question courante, options, réponse donnée | 1 000 |
| **Accueil, profil, autres** | Rien — le tuteur reste général | — |
| **Toutes** | Les **2 derniers échanges** de la conversation | 500 par échange |

**La section, jamais le cours entier.** C'est l'unité sur laquelle on bloque, et
transporter le cours complet saturerait la fenêtre du modèle pour du texte que
l'apprenant ne regarde pas — à chaque question, et à chaque appel facturé.

**Toute troncature est signalée** par un « … » visible. Une coupure silencieuse
ferait croire à l'apprenant que le tuteur a tout lu.

**L'historique n'est pas persisté.** Il vit dans la page et disparaît en la
quittant : `apps/chat/models.py` est vide, et le reste — un historique de
conversation serait un chantier à part, avec ses conséquences RGPD.

## Le refus qui fonde cette décision

> **La bonne réponse d'un quiz n'est jamais transmise.**

`quiz_data` porte `correct_answer` et `explanation` : le navigateur en a besoin
pour afficher la correction après chaque question. **Le tuteur, non.**

Un tuteur qui connaît la réponse attendue **la donne**. Ce n'est pas un risque,
c'est ce qu'on lui demande de faire : aider. Et le quiz cesse alors de mesurer
quoi que ce soit.

La conséquence dépasse le quiz. Toute la progression du produit repose sur des
résultats mesurés — un exercice réussi, un quiz passé (décision 028). **Une
seule fuite ici les rendrait tous douteux**, et personne ne saurait dire à
partir de quand.

`explanation` est écartée pour la même raison : elle contient l'explication de
la bonne réponse, donc la bonne réponse.

**La solution attendue d'un exercice est écartée pareillement**, et pour le même
motif.

### L'expurgation a lieu côté serveur

C'est le point qui rend le refus tenable. La version destinée au tuteur est
composée dans la vue, avant d'être écrite dans la page : elle ne contient jamais
la réponse, **pas même dans le navigateur**.

Confier ce refus à du JavaScript reviendrait à le confier à ce qu'une refonte
d'interface réécrit en premier.

### Et un test le garde

Trois tests échouent si `correct_answer` reparaît : dans le contexte composé,
dans l'invite envoyée au modèle, et dans le bloc que la page contient. C'est le
genre de garantie qui se perd à la première refonte, et qu'un test seul retient.

## Qui produit le contexte, et par quel chemin

La règle du chantier appliquée : **un panneau qui recevrait un contexte que rien
ne lui transmet serait la quatrième occurrence de la famille C.**

La parade tient en une phrase : **la bannière et la requête lisent la même
source.** Chaque page qui a un contexte l'écrit dans un bloc JSON rendu par
Django ; le panneau le lit deux fois — pour afficher « le tuteur voit : … » et
pour composer sa requête.

Si rien n'est écrit, la bannière affiche « aucun contexte — question
générale ». **L'absence se voit à l'écran**, au lieu de manquer en silence.

| Page | Ce qui écrit le contexte |
|---|---|
| Cours | `courses.views.course_detail` |
| Exercice | `exercises.views.exercise_detail` |
| Quiz | `quiz.views.quiz_start`, expurgé |
| Autres | Rien — le panneau annonce l'absence |

## Ce qui est montré à l'apprenant

Transmettre le code de quelqu'un à un modèle sans le lui dire n'est pas
acceptable. La bannière énumère ce qui part : « Exercice : … · Votre code : tel
qu'il est actuellement saisi · Dernière erreur : … ».

L'afficher sert aussi à autre chose : quand la réponse porte sur autre chose que
ce que l'apprenant croyait, la bannière explique pourquoi.

## Les actions contextuelles

Quatre sous une section de cours, deux sur un exercice, une pendant un quiz.
Chacune envoie une invite préformée avec le contexte courant — **aucune capacité
nouvelle du modèle**, seulement du câblage entre des agents qui existent déjà.

Les invites sont rassemblées dans `apps/chat/actions.py` plutôt que dispersées
dans les gabarits : c'est ce qui permet de les relire toutes d'un coup. Un test
vérifie qu'aucune, sur un exercice ou un quiz, ne demande au tuteur de donner la
solution — « Un indice sans la solution » le lui dit explicitement.

## Conséquences

- `apps/chat/contexte.py` : la composition, les bornes, et les refus.
- `apps/chat/actions.py` : les invites, relisibles d'un coup.
- `templates/components/tuteur.html` : le panneau, inclus dans le gabarit de
  base pour toute personne connectée.
- Le contexte du quiz est expurgé dans la vue, jamais dans le navigateur.
- Quatorze tests, dont trois sur le seul refus.
