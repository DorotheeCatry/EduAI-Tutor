# Incident 018 — Une liste blanche maison, contournée par une concaténation

**Date :** 2 septembre 2026
**Composant :** `apps/exercises/security.py`
**Gravité :** majeure — exécution de code arbitraire côté serveur
**Statut :** résolu, vérifié par sept tests d'évasion
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — sécurité ; C17 (E4)

---

## 1. Déclenchement

L'autrice, après un inventaire du code mort qui signalait `restrictedpython`
déclarée en dépendance et jamais importée :

> je ne suis pas trop pour la liste blanche maison, c'est bien mais j'aimerais
> quelque chose de sûr et de pro ?

Avant de remplacer un mécanisme qui semblait fonctionner, il fallait établir
qu'il ne fonctionnait pas.

## 2. Ce que la vérification a montré

Cinq tentatives d'évasion, sur l'exécuteur alors en service :

| Tentative | Résultat |
|---|---|
| `import os` | bloqué |
| `open('/etc/hostname')` | bloqué |
| `().__class__.__base__.__subclasses__()` avec `open` | bloqué |
| **`__import__('o' + 's').getcwd()`** | **passé** — a rendu le chemin du serveur |
| **`(1).__class__.__base__.__subclasses__()[0]`** | **passé** |

**Le filtre lisait le TEXTE du code**, ligne par ligne, à la recherche de
« import os » et de mots comme `open` ou `exec`. Un nom de module écrit
`'o' + 's'` ne s'y trouve pas : il n'est assemblé qu'à l'exécution, quand le
filtre a déjà donné son accord.

La seconde évasion est la chaîne classique — remonter de n'importe quel objet à
`object`, puis à ses sous-classes, pour y trouver de quoi lancer un processus.
Rien n'encadrait l'accès aux attributs.

## 3. Ce qui rendait ce défaut difficile à voir

**Le filtre bloquait tout ce à quoi son auteur avait pensé.** Les trois
premières lignes du tableau échouent proprement, avec un message clair. Un
essai rapide donne donc l'impression d'une protection qui tient.

C'est la limite structurelle de l'approche, plus que ce défaut-là :
**une liste blanche écrite à la main n'est éprouvée que par les contournements
auxquels son auteur a pensé.** Elle ne peut pas être meilleure que
l'imagination d'une personne, un après-midi.

## 4. Correction

`RestrictedPython`, de la Zope Foundation — déjà déclarée en dépendance, jamais
importée. Elle **réécrit l'arbre syntaxique avant compilation** et fait passer
chaque accès d'attribut, chaque indexation, chaque itération par une garde.

Deux points de conception valent d'être notés.

**Le filtre porte désormais sur le nom du module, pas sur le texte du code.**
`_importateur_sur` remplace `__import__` et reçoit le nom **déjà assemblé** :
`'o' + 's'` y arrive comme `os`. Il n'y a plus rien à contourner.

**Le filtre textuel est retiré, pas doublé.** Le conserver aurait laissé croire
à une défense supplémentaire là où il n'apportait rien — et les deux listes qui
le servaient sont supprimées avec lui. Un test échoue si elles reparaissent.

Un troisième point, découvert en vérifiant : RestrictedPython remplace `print`
par un collecteur qui n'écrit pas sur la sortie standard. Sans lire ce
collecteur, **tout code s'exécutait en affichant un résultat vide**. La
bibliothèque le signalait par un avertissement, que rien ne regardait.

## 5. Vérification

Les sept évasions sont refusées, et à des étages différents :

```
import os              → Module non autorisé : os
__import__('o' + 's')  → Code refusé : "__import__" is an invalid variable name
open(...)              → name 'open' is not defined
__subclasses__         → Code refusé : "__subclasses__" is an invalid attribute
__class__              → Code refusé : "__class__" is an invalid attribute
exec / eval            → refusés à la compilation
```

Et le code ordinaire passe : dictionnaires, compréhensions, fonctions, `math`.
Quatorze tests couvrent les deux versants, dans `tests/test_execution_de_code.py`.

## 6. Ce qu'on en retient

**Une protection qu'on écrit soi-même se teste par ce qu'on n'a pas prévu, pas
par ce qu'on a prévu.** Les trois blocages qui fonctionnaient donnaient
confiance ; ce sont les deux qui manquaient qui décidaient de la sécurité.

Et un signal était disponible depuis le début : **la dépendance
`restrictedpython` était déclarée et jamais importée**. Quelqu'un l'avait
choisie, puis avait écrit autre chose. Une dépendance inutilisée n'est pas
seulement du poids mort — elle peut être la trace d'une décision abandonnée en
route.
