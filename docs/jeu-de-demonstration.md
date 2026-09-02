# Jeu de démonstration — six comptes et leur parcours

Six comptes fictifs destinés à peupler la plateforme pour la démonstration du
14 septembre, et à éprouver le quiz multijoueur.

**À lire avant de commencer :** ces comptes sont fictifs, mais l'activité qu'ils
produisent est réelle — de vrais exercices, de vrais quiz, de vrais appels au
modèle. C'est la distinction qui compte. Le projet a retiré sept foyers de
données factices ; celui-ci n'en est pas un, à condition d'être **documenté
comme jeu de démonstration** et non présenté comme une population d'apprenants.

---

## Les six comptes

| Prénom | Adresse | Mot de passe | Rôle dans la démonstration |
|---|---|---|---|
| Dorothée | *compte existant* | *inchangé* | Parcours le plus avancé — niveau 2 atteint |
| Oumar | `oumar@exemple-eduai.fr` | `Parcours2026!` | Apprenant régulier, progression nette |
| Hany | `hany@exemple-eduai.fr` | `Revision2026!` | Apprenant qui bute — alimente « à revoir » |
| Johan | `johan@exemple-eduai.fr` | `Quiz2026!Test` | Fait surtout des quiz, peu d'exercices |
| Caroline | `caroline@exemple-eduai.fr` | `Partie2026!` | Partenaire de quiz multijoueur |
| Sat | `sat@exemple-eduai.fr` | `Nouveau2026!` | **Compte neuf, laissé vide** |

**Le domaine `exemple-eduai.fr` n'existe pas** — c'est délibéré. Aucune de ces
adresses ne peut appartenir à une personne réelle, et rien ne sera envoyé par
erreur à un tiers.

**Sat reste vide.** C'est le compte à montrer au jury pour démontrer les états
vides de la page d'accueil : le premier écran de toute nouvelle personne. Ne rien
faire avec, jamais.

---

## Ce que chacun doit produire

### Dorothée — le parcours de référence

C'est le compte à montrer en premier. Il doit afficher les quatre blocs remplis.

| Compétence | Ce qu'il faut faire |
|---|---|
| Manipuler les listes, dictionnaires et ensembles | **3 exercices réussis.** Sur l'un des trois, échouer 2 ou 3 fois avant de réussir — un `pass` suffit à faire échouer |
| Écrire et appeler des fonctions | **1 exercice réussi du premier coup** |
| Gérer les erreurs et les exceptions | **1 exercice généré et laissé non réussi** |
| — | **1 quiz terminé**, avec 2 ou 3 réponses fausses volontaires |
| — | **1 cours généré** |

Résultat attendu : niveau 2 sur la première compétence, niveau 1 sur la
deuxième, une compétence entamée sans niveau sur la troisième, un bloc « à
revoir » alimenté, et une dernière activité.

⚠️ **Le quiz doit aller jusqu'au dernier écran.** C'est l'envoi du résultat qui
enregistre, et rien avant.

### Oumar — progression régulière

| Compétence | Ce qu'il faut faire |
|---|---|
| Manipuler les types de base et les variables | 2 exercices réussis |
| Écrire et appeler des fonctions | 1 exercice réussi |
| — | 1 quiz terminé, majoritairement juste |

Sert à montrer un parcours en cours, distinct de celui de Dorothée.

### Hany — celui qui bute

C'est le compte qui donne du contenu au bloc « à revoir ».

| Compétence | Ce qu'il faut faire |
|---|---|
| Manipuler les listes | 1 exercice, **4 ou 5 tentatives** avant de réussir |
| Gérer les erreurs | 1 exercice, 3 tentatives, laissé non réussi |
| — | 1 quiz terminé avec **beaucoup de réponses fausses** |

Résultat attendu : un bloc « à revoir » bien fourni, classé par nombre de
tentatives.

### Johan — la reconnaissance sans la production

| Ce qu'il faut faire |
|---|
| 2 quiz terminés, sur des compétences différentes |
| Aucun exercice |

Ce compte démontre une décision d'architecture : **les quiz ne font progresser
aucun niveau**. Johan aura des erreurs dans « à revoir » et zéro compétence
acquise. C'est voulu, et c'est ce qu'il faut expliquer au jury si la question
vient — un QCM mesure la reconnaissance, pas la production.

### Caroline — le multijoueur

Elle sert d'adversaire. Une partie de quiz multijoueur avec Dorothée, en suivant
le protocole ci-dessous.

### Sat — rien

Aucune action. Jamais.

---

## Le protocole du quiz multijoueur

À faire une seule fois, en deux navigateurs — une fenêtre normale pour Dorothée,
une fenêtre privée pour Caroline.

**Trois comportements à vérifier :**

1. **Le classement.** Répondre très vite d'un côté, lentement de l'autre.
   L'écart de points doit refléter l'écart réel de temps.
2. **Le départ en cours de partie.** Fermer la fenêtre de Caroline au milieu
   d'une question sans répondre. La partie doit avancer dès que Dorothée a
   répondu, et non attendre indéfiniment.
3. **Le retour.** Rouvrir la fenêtre de Caroline sur l'adresse de la partie. Elle
   doit retrouver la question en cours, et non un refus d'accès.

⚠️ **Chaque lancement de partie consomme une génération** sur le quota de l'hôte
— 15 par jour. Deux ou trois parties suffisent : ne pas les enchaîner.

---

## Ce qu'il faut vérifier après, et non supposer

Le projet a documenté un incident où un chargement s'est annoncé réussi sur une
base restée vide, et un autre où un quiz n'avait jamais rien enregistré depuis
l'origine.

**Après avoir produit les données, demander le relevé en base** — comptes,
exercices engendrés, exercices rattachés à une compétence, soumissions,
soumissions réussies, sessions de quiz, **sessions terminées**.

Un quiz joué n'est pas un quiz enregistré tant que le relevé ne le montre pas.

---

## Deux points à ne pas oublier

**Documenter ce jeu comme jeu de démonstration.** Une ligne dans les livrables et
dans la base suffit : ces six comptes ne sont pas des apprenants réels. Sans
cette mention, un jury pourrait croire à une population d'usage — et ce serait
exactement le reproche que le projet s'est fait à lui-même sept fois.

**Le mot de passe et l'adresse de chaque compte n'ont pas à être secrets**, mais
ils ne doivent pas non plus traîner dans le dépôt. Cette note reste hors de Git,
ou les mots de passe en sont retirés avant commit.

---

## Ordre recommandé

1. Créer les cinq comptes.
2. Dorothée d'abord — c'est le parcours de référence, et celui qui révélera un
   éventuel défaut avant que les autres ne le reproduisent.
3. Le relevé en base, pour vérifier que tout est bien arrivé.
4. Oumar, Hany, Johan.
5. La partie multijoueur avec Caroline.
6. Un second relevé.
7. Sat : ne rien faire.

Compter environ une heure et demie. Le quota global est de 200 générations par
jour, celui de chaque compte de 15 — largement suffisant pour ce protocole.
