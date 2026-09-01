# 036 — Koda s'adresse à l'apprenant, et n'invente rien

**Date :** 1er septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C20 (E5) — données du suivi ; C13 (E3) ; C21 (E5)

## Contexte

> J'aimerais qu'il ait une super personnalité solaire et très vivant !! […]
> qu'il connaisse le pseudo de l'apprenant et qu'il construise une relation.

Une mascotte qui salue par le prénom et se souvient de la dernière séance n'est
pas un ornement : c'est ce qui sépare un bouton d'aide de quelqu'un qu'on
retrouve.

## Options pour composer la phrase

1. **Assemblée côté serveur** à partir de la base.
2. **Engendrée par le modèle**, à qui l'on décrirait l'apprenant.
3. **Fixe**, la même pour tout le monde.

## Option retenue

**La première.**

## Raisons

**Le quota.** Quinze générations par jour et par apprenant (décision 030). En
dépenser une pour dire bonjour serait absurde, et rendrait l'accueil dépendant
d'un service distant dont la latence médiane est de plusieurs secondes.

**La fiabilité, qui pèse plus lourd.** Une phrase assemblée ne peut pas
inventer une séance qui n'a pas eu lieu. Un modèle à qui l'on décrit un
apprenant produira volontiers « tu progresses bien ces derniers jours » à
quelqu'un qui ne s'est pas connecté depuis trois semaines.

**L'option 3 ne construit rien.** « Bonjour, comment puis-je vous aider » est
exactement ce que la demande écartait.

## La règle, et pourquoi elle a failli être enfreinte

**Koda ne dit que ce que la base contient.**

| Employé | Source | Garantie |
|---|---|---|
| Pseudonyme | `user.username` | toujours vrai |
| Dernière venue | séance close, exercice, cours, **erreur enregistrée** | incident 010 |
| Notion laissée de côté | `UserExerciseProgress`, `UserMistake` | décision 028 |

**Écarté : `current_streak`.** Le champ existe, il est lu ailleurs pour
accorder un bonus d'expérience, et **rien ne l'écrit jamais** — il vaut zéro
pour tout le monde (réserve 19).

C'est le point à retenir de cette décision. « Trois jours d'affilée, bravo ! »
était la phrase la plus naturelle à écrire, la plus chaleureuse, celle qui
donne l'impression d'un produit attentif. Elle aurait été **fausse pour chaque
apprenant, sur toutes les pages**. Une mascotte est précisément l'endroit où
l'on réintroduit du faux sans y penser, parce que ça sonne bien. Un test
interdit désormais l'emploi de ce champ dans la salutation.

**Un test a d'ailleurs trouvé une incohérence que la relecture avait manquée :**
Koda citait une notion tirée des erreurs à quelqu'un qu'il venait de déclarer
jamais vu. La branche était inatteignable pour un apprenant n'ayant fait que
des quiz. Une erreur enregistrée compte désormais comme une venue.

## Le personnage comme interface

**La poignée du chat est Koda lui-même.** Une mascotte posée à côté d'une
pastille verte est un ornement ; une mascotte sur laquelle on appuie est
l'interlocuteur. L'élément reste un `button` avec son nom accessible, son
`aria-expanded` et son `aria-controls` ; Koda y est `aria-hidden`, et le
libellé textuel reste affiché — le personnage seul ne dirait pas à quoi il sert.

**Il s'assoupit et s'endort** après inactivité, et se réveille à l'ouverture du
panneau. **Un clignement sur cinq devient un clin d'œil** : c'est peu de chose,
et c'est ce qui sépare un personnage d'une image qui bat des paupières.

## Le GIF de la page de connexion, remplacé

Le salut d'accueil était un GIF de 470 Kio. **Un GIF s'anime quoi qu'il
arrive** : il ignore `prefers-reduced-motion`, et c'était la première image que
voyait un visiteur — dont celui qui a demandé à son système de réduire les
animations. La planche de sprites se fige, et pèse 261 Kio.

## Conséquences

- Un processeur de contexte paresseux : les pages qui ne rendent pas le tuteur
  ne paient aucune requête, comme pour le compteur de quota.
- Aucune exception ne remonte : une salutation qui ne se calcule pas ne doit
  pas faire tomber une page qui, sans elle, fonctionne.
- Cinq tests fixent la règle, dont un qui échoue si Koda affirme quelque chose
  à un compte sans activité.

## Ce que ce choix laisse ouvert

La salutation est calculée à chaque page, alors qu'elle ne change qu'une fois
par séance. Aucune mesure ne dit aujourd'hui que cela coûte quelque chose ; la
mesurer viendrait avant de la mettre en cache.

Koda ne dit rien à la fin d'une séance, ni après une réussite. Les états
existent — la réjouissance est assemblée — mais rien ne les déclenche encore.
