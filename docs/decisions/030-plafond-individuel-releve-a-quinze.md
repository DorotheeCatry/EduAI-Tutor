# 030 — Le plafond individuel passe de 5 à 15, parce que l'unité comptée a changé

**Date :** 31 août 2026
**Compétence visée :** C9 (épreuve E2) — quotas de l'API du service IA
**Compétences concernées :** C13 (E3) — maîtrise du coût ; C17 (E4)

## Contexte

Le plafond individuel de générations était de **5 par jour** (décision 019),
posé quand le produit générait des cours, des quiz et des exercices — des actes
délibérés, préparés, dont cinq par jour est un usage nourri.

Le tuteur est devenu contextuel : il est à portée sur chaque page, au lieu
d'occuper une page qu'il fallait aller ouvrir. Et une question au tuteur coûte
une génération.

**Trois questions sur un exercice épuisaient donc le plafond avant qu'aucun
cours n'ait été demandé.**

## Options

1. Garder 5, et assumer que le chat consomme le même budget.
2. **Relever le plafond individuel à 15.**
3. Tenir **deux compteurs** : générations de contenu d'un côté, questions de
   l'autre.
4. Pondérer : une question courte coûterait une fraction de génération.

## Option retenue

**La deuxième.** Un seul compteur, plafond individuel porté à 15.

## Raisons

**Garder 5 rendrait le tuteur inutilisable** le jour où il devient utile. Un
apprenant qui bloque pose trois questions d'affilée ; c'est le comportement que
le chantier cherche à rendre possible.

**Deux compteurs obligeraient l'apprenant à comprendre deux limites.** « Il vous
reste 3 générations et 12 questions » demande de savoir ce qui relève de l'une
ou de l'autre, au moment précis où l'on veut poser une question et non lire une
règle.

**La pondération suppose une comptabilité par jetons que le service de quotas
n'a pas.** Le monitorage la tient — jetons d'entrée, de sortie, coût estimé —
mais le quota compte des actes, pas des jetons. Les relier serait un chantier,
et un chantier dont le résultat serait un compteur dont l'apprenant ne pourrait
plus prévoir la consommation.

## Ce que ce relèvement n'est pas

**Ce n'est pas un plafond relevé parce qu'il gêne.** La distinction est la même
que pour le seuil de latence du monitorage la veille (décision 024) : on ne
règle pas un indicateur pour qu'il cesse de se déclencher, on le règle quand ce
qu'il mesure a changé de nature.

Ici, l'unité comptée est passée de « une génération de contenu » à « un appel au
modèle, quel qu'il soit ». Le nombre d'appels d'une session d'apprentissage
normale a augmenté d'autant, sans que l'usage devienne déraisonnable.

Le facteur trois n'est pas dérivé d'une mesure — il n'y a pas encore d'usage à
mesurer. Il est **posé**, et c'est dit : trois questions par exercice travaillé,
sur trois ou quatre activités dans une journée. Il sera à confronter aux
premières données réelles.

## Ce que le relèvement ne touche pas

**Le plafond global reste à 200.** C'est lui la protection financière : il borne
la dépense tous comptes confondus, et il est indépendant du nombre de comptes.
Le plafond individuel protège d'autre chose — d'un usage déséquilibré entre
apprenants, où l'un consommerait le budget de tous.

Relever l'un sans toucher l'autre est cohérent : on autorise un apprenant à
travailler davantage, on n'autorise pas le service à dépenser davantage.

## Conséquences

- `QUOTA_INDIVIDUEL_DEFAUT` passe de 5 à 15, avec le motif écrit sur place.
- `.env.example` porte la nouvelle valeur et la raison.
- **La variable doit être mise à jour chez l'hébergeur** : un défaut de code
  relevé ne relève pas un réglage déjà posé. Sans cela, le dépôt serait corrigé
  et le système ne le serait pas.
- Le panneau du tuteur affiche le quota restant après chaque réponse : un
  apprenant ne doit pas découvrir la limite en la heurtant.
- À confronter aux premières données réelles d'usage.
