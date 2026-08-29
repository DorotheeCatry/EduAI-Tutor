# 019 — Deux plafonds de génération, décomptés au goulot des agents

**Date :** 29 août 2026
**Compétence visée :** C13 (épreuve E3) — maîtrise du coût en production
**Compétences concernées :** C4 (E1), C9 (E2), C17 (E4), C18 (E4)

## Contexte

L'application doit être mise en ligne pour la démonstration devant jury. Tant
qu'elle tourne en local, une génération de trop coûte une seconde d'attente ;
exposée, chaque visiteur déclenche des appels facturés au fournisseur de
modèles. Aucun plafond n'existait côté application — le service IA avait le
sien, en débit par clé, mais il ne borne pas un volume quotidien et ne couvre
pas les vues Django.

Sept points de dépense ont été relevés : les vues de génération de cours, de
chat, d'exercices (deux), de quiz (deux), et la génération de questions par
WebSocket.

## Options

### Où décompter

1. Un décorateur sur chacune des vues Django.
2. Un décompte dans l'orchestrateur, en tête des trois méthodes qui appellent
   le modèle.

### Quel compteur

3. Un compteur en mémoire de processus.
4. Un enregistrement horodaté par génération, permettant une fenêtre glissante
   de 24 heures.
5. Un compteur agrégé par personne et par jour, en base.

## Options retenues

**La deuxième et la cinquième.** Le décompte a lieu dans l'orchestrateur ; le
compteur est une ligne par personne et par jour dans `eduai_app`.

## Raisons

**Le décorateur laissait une façade sans protection.** Le service IA FastAPI
amorce Django et réutilise ces mêmes agents sans passer par aucune vue : un
contrôle posé sur les vues l'aurait ignoré. L'orchestrateur est le goulot par
lequel passent les deux façades. Il a un second mérite : une méthode qui
générerait sans décompter s'y verrait, alors qu'une vue oubliée dans une liste
de décorateurs ne se voit pas.

**Le compteur en mémoire ne vaut rien.** Il ne survit pas à un redémarrage, et
derrière plusieurs travailleurs chacun a le sien — le plafond réel devient le
plafond annoncé multiplié par leur nombre. Le monitorage du projet a déjà
montré ce que valent les mesures propres à un processus.

**L'enregistrement horodaté a été écarté pour une raison de RGPD, pas de
performance.** Il constituerait un journal nominatif de l'activité de chaque
apprenant, avec sa durée de conservation, son droit d'accès et son droit à
l'effacement à tenir. Le compteur agrégé répond à la même question — combien
aujourd'hui ? — sans conserver l'heure, le sujet ni l'ordre des demandes. La
minimisation est un critère explicite de C4.

**Limite assumée**, et il faut la dire plutôt que la découvrir à l'oral : sans
horodatage, la remise à zéro a lieu à minuit et non 24 heures après la première
génération. Une personne peut donc consommer son quota à 23 h 50 puis le
suivant à 00 h 10. Le plafond global, lui, reste borné par jour — et c'est lui
la protection du budget.

## Les deux plafonds

| Plafond | Variable | Défaut | Ce qu'il protège |
|---|---|---|---|
| Individuel | `EDUAI_QUOTA_GENERATIONS_PAR_JOUR` | 5 | Qu'une personne ne consomme pas tout |
| Global | `EDUAI_PLAFOND_GENERATIONS_PAR_JOUR` | 200 | Que cinquante inscriptions ne le fassent pas à sa place |

Le second est la protection réelle : le quota individuel ne borne rien tant que
le nombre de comptes n'est pas borné. Au-delà du plafond global, la génération
est refusée et la consultation reste ouverte — les cours, exercices et quiz
déjà enregistrés restent lisibles.

Les défauts sont bas, et une valeur absente, illisible ou négative y retombe
avec une entrée au journal. C'est la règle des défauts asymétriques déjà
appliquée aux secrets : un réglage oublié doit restreindre le service, jamais
l'ouvrir.

## Deux points de conception qui ne sautent pas aux yeux

**Le décompte est placé avant le `try` de chaque méthode.** Les trois méthodes
génératrices entourent leur corps d'un `except Exception` qui renvoie un
dictionnaire d'erreur. À l'intérieur du bloc, le refus serait devenu une panne
technique : l'apprenant aurait lu « une erreur est survenue » au lieu de
« vous avez utilisé vos générations du jour », et l'interface l'aurait invité à
réessayer sans fin. Deux vues d'exercices allaient plus loin : leur bloc de
repli **crée un exercice** en cas d'erreur, ce qui aurait produit du contenu
tout en masquant le refus. Un test dédié verrouille ce placement.

**Le service IA a son propre chemin de décompte.** `consommer_pour_le_service_ia()`
n'applique pas de quota individuel — ses consommateurs sont des programmes
porteurs d'une clé de service, il n'y a personne à qui imputer cinq générations
— mais il alimente le plafond global. Sans cela, l'API serait le trou par
lequel le budget se vide. Le drapeau `pour_service_ia` est explicite et n'est
pas déduit de l'absence d'utilisateur : cette absence peut aussi signifier
qu'une vue a oublié de transmettre l'apprenant, et les deux cas n'appellent pas
la même règle.

## Conséquences

- Nouvelle application `apps/quotas` : un modèle, un service, une migration.
- La génération de quiz par WebSocket appelait l'orchestrateur **sans
  utilisateur** : c'était le seul chemin de dépense non imputable du projet.
  Elle est désormais portée par le quota de l'hôte du salon, qui est bien celui
  qui la déclenche. Le même correctif traite un défaut voisin : `start_game`
  ignorait le résultat de la génération et lançait la partie même sans
  questions.
- 18 contrôles automatisés, dont le placement du décompte hors du bloc
  d'interception et le partage du plafond entre les deux façades.
- Le compteur est affiché **avant** la génération, sur les quatre pages qui en
  déclenchent une : génération de cours, chat, fenêtre de génération
  d'exercice, quiz. Un apprenant ne découvre donc pas le plafond au moment du
  refus, et le jury voit que le coût a été pensé. Le calcul est différé
  (`SimpleLazyObject`) : les pages qui n'affichent pas le compteur ne paient
  aucune requête.
- Au passage, `quiz_start.html` ne rendait nulle part le champ `error` que sa
  vue lui transmet : un quiz non généré donnait une page vide, sans
  explication. Le gabarit l'affiche désormais.
- **Réserve** : le quiz multijoueur par WebSocket a été protégé par le quota,
  mais aucun gabarit du projet n'ouvre de connexion WebSocket — c'est du code
  serveur sans client. Consigné dans `docs/reserves.md`, avec les autres écarts
  entre ce que le dépôt paraît faire et ce qu'il fait.
