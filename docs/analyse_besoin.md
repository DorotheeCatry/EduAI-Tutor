# Analyse du besoin et spécifications fonctionnelles

**Date :** 28 août 2026
**Compétence visée :** C14 (épreuve E4) — analyse du besoin et spécifications
fonctionnelles
**Compétences concernées :** C17 (E4) — application ; C4 (E1) — RGPD ; C19 (E4)

---

## 1. Le contexte

EduAI Tutor est la plateforme d'accompagnement d'un **organisme de formation
professionnelle au développement**. Son public est constitué d'adultes en
reconversion ou en montée en compétences, suivant un parcours structuré en onze
modules — de Python à l'agilité, en passant par SQL, l'apprentissage automatique
et les plateformes en nuage.

Ce cadre a été arrêté explicitement, et il n'est pas décoratif : il détermine le
périmètre RGPD applicable et l'ensemble des obligations qui en découlent. Deux
autres cadres ont été examinés puis écartés — logiciel interne d'établissement
scolaire, site d'auto-formation grand public — pour la même raison de fond : ils
accueilleraient des mineurs sans qu'on puisse le prévenir, ce qui imposerait une
chaîne de consentement parental absente de l'application et irréalisable dans le
délai. Retenir l'un des deux aurait consisté à déclarer une conformité
inexistante. Le détail de l'arbitrage est en décision 004.

**Le service est donc réservé aux personnes majeures.**

## 2. Les parties prenantes

| Partie prenante | Rôle | Ce qu'elle attend |
|---|---|---|
| **Les apprenants** | Utilisateurs directs | Un accompagnement disponible hors des heures d'encadrement, adapté à leur niveau, sur le corpus de leur formation |
| **Les formateurs** | Prescripteurs du corpus, destinataires des signaux de progression | Que le tuteur s'appuie sur *leur* corpus et non sur une culture générale du web ; et un retour sur là où leur groupe bloque |
| **La direction de l'organisme** | Responsable du traitement au sens du RGPD | Une conformité tenable et documentée, et un service qui ne crée pas d'obligation qu'elle ne peut honorer |

## 3. Le besoin, et d'où vient son analyse

### Le besoin exprimé

> Entre deux séances encadrées, un apprenant bloqué n'a que trois recours : la
> documentation officielle, qui suppose de savoir déjà ce qu'on cherche ; un
> forum généraliste, dont les réponses ne sont ni de son niveau ni alignées sur
> son parcours ; ou attendre. Le besoin est un interlocuteur disponible qui
> connaisse **le corpus de la formation suivie** et **le niveau de celui qui
> demande**.

### L'origine de l'analyse — une position de première main

Cette analyse n'a pas été construite à partir d'entretiens ni d'une persona
inventée. **Elle est de première main : l'autrice du projet a été apprenante
d'une formation au développement**, et le besoin décrit ci-dessus est celui
qu'elle a éprouvé, dans les conditions où il se présente — le soir, sur un
message d'erreur qu'on ne sait pas nommer, avec une documentation qui répond à
une question qu'on ne sait pas encore poser.

Il faut le présenter comme tel, et non le déguiser en étude d'usage, pour deux
raisons.

**Parce que c'est vrai**, et qu'une persona fabriquée aurait la forme d'une
analyse sans en avoir la substance. Un jury distingue les deux.

**Parce que la limite se voit alors**, au lieu d'être masquée : une analyse de
première main est riche sur le vécu d'**un** parcours et muette sur la variance
entre apprenants. Elle ne dit rien de ceux dont le rapport à l'écrit, au temps
ou à l'outillage diffère. Cette limite est réelle ; elle est énoncée au § 6
plutôt que compensée par des personas qui n'ajouteraient que de la fiction.

---

## 4. Les user stories

Chaque story porte ses critères d'acceptation. **Les objectifs d'accessibilité
figurent dans ces critères**, au même rang que les critères fonctionnels : une
fonction dont le clavier ne permet pas l'usage n'est pas une fonction livrée à
moitié, c'est une fonction indisponible pour qui n'a pas de souris.

Le référentiel visé est **WCAG 2.1 niveau AA / RGAA**. L'état réel de la
conformité est mesuré au § 6 — les critères ci-dessous énoncent la cible, non un
constat.

### US-1 — Obtenir un cours sur une notion

> **En tant qu'**apprenant, **je veux** demander un cours sur une notion de mon
> parcours, **afin de** disposer d'une explication alignée sur mon niveau sans
> attendre la prochaine séance.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | La demande accepte une notion en langage naturel, sans syntaxe imposée |
| 2 | Le cours produit s'appuie sur le corpus de la formation, et non sur la seule connaissance générale du modèle |
| 3 | Le cours comporte au moins un exemple de code exécutable |
| 4 | Le cours est rattaché à un module du parcours, et retrouvable ensuite dans « mes cours » |
| 5 | Un échec du service de génération affiche un message explicite, jamais une page d'erreur brute |
| 6 | **Accessibilité —** le cours est structuré par des titres hiérarchisés `h1`/`h2`/`h3` sans saut de niveau, exploitables par un lecteur d'écran pour naviguer |
| 7 | **Accessibilité —** les blocs de code portent une alternative textuelle indiquant le langage, et ne transmettent aucune information par la seule couleur |
| 8 | **Accessibilité —** le formulaire de demande a une étiquette liée à son champ, et l'envoi est possible au clavier seul |

### US-2 — Faire réexpliquer ce que je n'ai pas compris

> **En tant qu'**apprenant, **je veux** demander une autre explication de la
> même notion, **afin de** ne pas rester bloqué sur une formulation qui ne me
> parle pas.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | La réexplication part d'un angle différent de la première, et non d'une reformulation superficielle |
| 2 | L'explication précédente reste consultable : on compare, on ne remplace pas |
| 3 | **Accessibilité —** le passage d'une explication à l'autre est annoncé aux technologies d'assistance par une région de type `aria-live`, le contenu changeant sans rechargement de page |
| 4 | **Accessibilité —** le focus clavier se place sur la nouvelle explication, et n'est pas perdu en haut de page |

### US-3 — M'exercer et recevoir un retour sur mon code

> **En tant qu'**apprenant, **je veux** soumettre ma solution à un exercice,
> **afin de** savoir ce qui ne va pas sans qu'on me donne la réponse.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | Le retour distingue ce qui fonctionne de ce qui ne fonctionne pas |
| 2 | **Le retour ne contient pas la solution complète** : il donne une piste. C'est le critère le plus important de cette story — un tuteur qui corrige à la place de l'apprenant ne l'apprend pas |
| 3 | Le retour est rendu en moins de trois secondes en conditions normales |
| 4 | La soumission est conservée pour alimenter la progression |
| 5 | **Accessibilité —** l'éditeur de code est utilisable au clavier, avec une sortie de piège de tabulation documentée et annoncée |
| 6 | **Accessibilité —** les messages de retour sont associés au champ concerné et annoncés, non signalés par un simple encadré coloré |
| 7 | **Accessibilité —** le contraste du texte et du code respecte un rapport d'au moins 4,5:1 |

### US-4 — Suivre ma progression

> **En tant qu'**apprenant, **je veux** voir où j'en suis, **afin de** savoir
> quoi réviser.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | La progression est calculée sur des faits — exercices soumis, quiz passés — non sur du temps passé |
| 2 | Les modules non commencés se distinguent des modules commencés et abandonnés |
| 3 | **Accessibilité —** toute donnée présentée en graphique est **également** disponible sous forme de tableau à en-têtes. Un graphique seul n'est pas accessible, et la table n'est pas un pis-aller : c'est la source |
| 4 | **Accessibilité —** aucune information n'est portée par la seule couleur ; un état est aussi signalé par un texte ou une forme |

### US-5 — Réviser par cartes mémoire

> **En tant qu'**apprenant, **je veux** réviser une notion par cartes,
> **afin de** consolider sans relire un cours entier.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | Les cartes sont engendrées à partir d'un cours existant, pas d'un sujet libre |
| 2 | Le retournement d'une carte est réversible |
| 3 | **Accessibilité —** le retournement est déclenchable au clavier, et l'état recto/verso est annoncé par `aria-expanded` ou équivalent |
| 4 | **Accessibilité —** aucune animation essentielle à la compréhension ; `prefers-reduced-motion` est respecté |

### US-6 — Réviser à plusieurs par quiz

> **En tant qu'**apprenant, **je veux** rejoindre une salle de quiz avec
> d'autres, **afin de** réviser autrement que seul.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | Une salle se rejoint par un code court, sans compte supplémentaire |
| 2 | L'état de la salle est partagé en temps réel entre les participants |
| 3 | La déconnexion d'un participant n'interrompt pas la partie des autres |
| 4 | **Accessibilité —** le minuteur n'est pas la seule indication du temps restant, et une limite de temps stricte peut être désactivée — critère WCAG 2.2.1 |
| 5 | **Accessibilité —** les mises à jour temps réel sont annoncées sans voler le focus |

### US-7 — Prescrire le corpus *(formateur)*

> **En tant que** formateur, **je veux** que le tuteur s'appuie sur les supports
> de la formation, **afin que** les réponses soient cohérentes avec ce que
> j'enseigne.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | Le corpus indexé est constitué des supports fournis, et sa provenance est traçable document par document |
| 2 | Une réponse construite sur le corpus peut être rattachée aux fragments qui l'ont produite |
| 3 | Un document dont la licence interdit la redistribution n'est jamais servi — **par aucune porte**, ni l'API, ni le tuteur |

### US-8 — Maîtriser mes données *(apprenant, et direction)*

> **En tant qu'**apprenant, **je veux** savoir ce qui est conservé de moi et
> pouvoir le faire effacer, **afin d'**exercer mes droits.

**Critères d'acceptation**

| # | Critère |
|---|---|
| 1 | Les données conservées et leur durée sont documentées et accessibles |
| 2 | Une demande d'effacement est réalisable et son effet vérifiable |
| 3 | Aucune donnée personnelle n'est transmise à un tiers sans que l'utilisateur puisse le savoir |
| 4 | **Accessibilité —** l'information sur les données est rédigée en langage clair, structurée par des titres, et n'est pas enfouie dans un document unique de plusieurs pages |

**État réel :** la route d'effacement de compte **n'est pas implémentée**, et le
champ `ip_address` d'`ExerciseSubmission` reste à supprimer. Ce sont les deux
écarts RGPD ouverts du projet ; ils sont identifiés dans `rgpd_eduai_data.md` et
non résolus à la date de ce document.

---

## 5. Le périmètre

### 5.1 Dans la version livrée

| Fonction | État |
|---|---|
| Génération de cours et réexplication | Livrée |
| Exercices et retour sur code | Livrée |
| Cartes mémoire et révision | Livrée |
| Quiz collaboratif en salle | Livrée |
| Suivi de progression | Livrée |
| Tableau de bord | Livré |
| Recherche documentaire par RAG | Livrée, sur un corpus partiel — voir 5.2 |
| API de mise à disposition du jeu de données | Livrée |
| API du service d'IA | Livrée |

### 5.2 Hors périmètre, et pourquoi

| Écarté | Raison |
|---|---|
| **L'interaction adaptative sur les cours** — un cours qui se reconfigure au fil des réponses de l'apprenant | **Arbitrage de délai.** C'était la fonction la plus ambitieuse et la plus incertaine du projet. La livrer à moitié aurait consommé le temps de plusieurs compétences pour une fonction non démontrable |
| **L'extension du corpus RAG aux onze modules** | **Arbitrage de délai.** 11 modules sont présents, 3 index sont construits — Python, science des données, ressources |
| **L'extension du corpus documentaire au dump Stack Overflow complet** | **Décision 017.** Les 355 113 documents mesurés relèvent d'une preuve de passage à l'échelle, non d'un besoin. Les charger multiplierait le corpus par cinquante-trois et changerait le produit sans décision |
| **L'entraînement d'un modèle** | Hors du bloc de compétences visé, et hors des moyens matériels : la machine dispose d'un GPU de 4 Go |
| **La gestion d'utilisateurs mineurs** | **Décision 004.** Le service est réservé aux majeurs ; en accueillir supposerait une chaîne de consentement parental complète |
| **Le multilingue** | L'internationalisation Django est active mais une seule langue est servie. Traduire l'interface sans traduire le corpus donnerait un service incohérent |

L'arbitrage de délai est le même dans les deux premiers cas, et il mérite d'être
nommé : **la contrainte du projet est la couverture de vingt et une compétences,
pas la profondeur sur quelques-unes.** Une compétence couverte modestement vaut
mieux qu'une compétence brillante à côté d'une compétence absente. Les deux
fonctions écartées auraient enrichi une compétence déjà couverte.

---

## 6. Les limites de cette analyse

Elles sont énoncées ici plutôt que découvertes par le jury.

| Limite | Portée |
|---|---|
| **Analyse de première main, non corroborée** | Le besoin décrit est éprouvé, mais par une personne. Rien n'établit sa généralité, ni ne dit ce dont auraient besoin des apprenants au profil différent |
| **Aucun utilisateur réel n'a testé le service** | Le journal de monitorage contient 4 appels au modèle, tous issus de vérifications. Les critères d'acceptation n'ont donc pas été confrontés à un usage |
| **L'accessibilité est une cible, pas un constat** | Sur **28 gabarits**, **7** portent des attributs `aria-`, `alt=` ou `role=`, et **4** déclarent la langue du document. Aucun audit RGAA n'a été mené, aucun test avec lecteur d'écran. Les critères du § 4 énoncent ce qui est visé ; l'écart avec le réalisé est celui-là, et il est important |
| **Deux écarts RGPD ouverts** | Route d'effacement de compte absente, champ `ip_address` à supprimer |

Sur l'accessibilité, la formulation demande d'être précise, parce que c'est un
critère transversal du référentiel et qu'un jury le vérifiera : **le projet a
défini ses objectifs d'accessibilité et les a inscrits dans ses critères
d'acceptation ; il n'a pas établi sa conformité.** Ce sont deux choses
différentes, et annoncer la seconde à partir de la première serait exactement le
genre d'affirmation que ce projet documente comme un défaut.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `decisions/004-cadre-usage-et-public-cible.md` | L'arbitrage du cadre d'usage et les parties prenantes |
| `decisions/005-cadre-usage-public-adulte.md` | Les conséquences RGPD du public adulte |
| `decisions/017-mesure-echelle-nest-pas-extension-corpus.md` | Pourquoi le corpus n'est pas étendu |
| `rgpd_eduai_data.md` | Données conservées, durées, écarts ouverts |
| `cadre_technique.md` | Comment ces besoins sont réalisés |
