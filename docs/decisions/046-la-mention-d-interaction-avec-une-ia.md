# 046 — La mention d'interaction avec une intelligence artificielle

**Date :** 4 septembre 2026
**Compétence visée :** C6 (épreuve E2) — impact concret de la veille réglementaire
**Compétences concernées :** C17 (E4) — interface ; C13 (E3) — accessibilité ; C21 (E5)

## Le contexte

La session de veille réglementaire du 28 août 2026
(`docs/veille/2026-08-28-ai-act-education.md`) établit deux choses. D'abord que
le tuteur ne relève **pas** du haut risque de l'annexe III du règlement (UE)
2024/1689 : il n'intervient ni dans l'accès à un établissement ni dans
l'évaluation des apprenants, et ne produit aucune décision opposable. Ensuite
qu'il est un **agent conversationnel**, donc à **risque limité**, et qu'à ce
titre l'**article 50** lui impose d'informer la personne qu'elle interagit avec
un système d'intelligence artificielle, au plus tard lors de la première
interaction.

Cette obligation est applicable depuis le **2 août 2026**. Le règlement
modificatif (UE) 2026/1744, entré en vigueur le 27 juillet 2026, reporte les
obligations du haut risque au 2 décembre 2027 mais **maintient** celles de
transparence : la partie qui concerne ce projet n'a pas été reportée.

La note de veille en tirait une action, notée « à implémenter ». Elle ne l'avait
pas été. La relecture du rapport E2 du 4 septembre a mis l'écart au jour : le
rapport décrivait la mention comme un impact produit par la veille, alors
qu'aucun gabarit de l'application ne la portait. C'est un motif que ce dépôt
documente déjà par ailleurs — **une action et son effet qui ne coïncident
pas** — cette fois entre un document et le produit qu'il décrit.

## Les options

1. **Une phrase dans le message d'accueil du tuteur.** Écartée : la salutation
   est poussée hors de l'écran dès la deuxième question. Une information qui
   cesse d'être visible ne tient pas une obligation qui, elle, ne cesse pas.
2. **Une mention dans les conditions d'utilisation ou une page dédiée.**
   Écartée : l'article 50 demande d'informer au moment de l'interaction, pas
   de rendre l'information disponible quelque part.
3. **Un bandeau permanent en tête de chaque surface de conversation.** Retenue.

## Ce qui a été fait

Un fragment unique, `templates/components/mention_ia.html`, inclus par les
**deux** surfaces où l'apprenant s'adresse au modèle : le panneau flottant
(`templates/components/tuteur.html`) et la colonne « Demander à Koda » de la
page de cours (`apps/courses/templates/courses/page_de_cours.html`). Les deux
s'excluent l'une l'autre — `koda_dans_la_page` efface la poignée flottante là
où le chat est déjà dans la page — et ne couvrir que la première aurait laissé
sans mention la page où l'apprenant passe le plus de temps.

**Un fragment plutôt que deux copies.** Deux copies, c'est accepter qu'un jour
l'une soit modifiée et pas l'autre ; c'est aussi deux entrées dans le catalogue
de traduction pour une seule phrase.

**Aucune condition autour de l'inclusion.** Un affichage que l'on peut
désactiver n'est pas une information, c'est une option. Le réglage de compte
qui coupe l'animation du personnage ne touche pas la mention, et un test le
vérifie.

**Une icône et un texte**, comme le bandeau du cours provisoire : le
pictogramme est `aria-hidden`, la phrase est du texte lisible par un lecteur
d'écran comme par quelqu'un qui ne connaît pas l'icône.

**La phrase est traduite** en anglais dans `locale/en/`. Une mention servie en
français à qui a choisi l'anglais informe moins bien qu'elle ne le prétend.

## La portée, et ce qui n'est pas couvert

La mention couvre l'**interaction conversationnelle**. Le **contenu engendré**
était déjà signalé de son côté : un cours provisoire porte en tête, en toutes
lettres, qu'il est « engendré par le modèle en attendant celui de votre
formateur » et qu'il n'a été relu par personne.

Ce qui reste vrai et doit le rester : **la qualification en risque limité tient
à ce que le système ne produit aucune décision opposable.** Si le coach
alimentait un jour une décision de validation, ou si le score de progression
conditionnait l'accès à un module obligatoire, la qualification basculerait en
haut risque et les obligations changeraient de nature — documentation
technique, supervision humaine, enregistrement dans la base européenne. C'est
écrit ici pour que la limite soit opposable au produit futur.

## Le contrôle de non-régression

`tests/test_mention_ia.py`, six tests : la mention est dans la page servie et
pas seulement dans un gabarit ; elle est traduite pour un compte anglophone ;
elle survit à la coupure des animations ; les deux surfaces l'incluent ; aucune
condition ne l'entoure ; elle porte un texte et pas seulement un pictogramme.

Une obligation réglementaire tenue par une seule ligne de gabarit est une
obligation qu'un remaniement d'interface peut faire disparaître sans que rien
ne le signale.
