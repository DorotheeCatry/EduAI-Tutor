# Incident 022 — Tout `print` écrit dans une fonction était perdu

**Date :** 13 septembre 2026
**Composant :** `apps/exercises/security.py`
**Gravité :** majeure — le bac à sable perdait la sortie de la plupart des programmes
**Statut :** résolu, vérifié par huit tests
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — bac à sable ; C17 (E4) ; C18 (E4)

---

## 1. Déclenchement

Signalement de l'autrice, page « Carnet d'exercices ». Ce code affichait
« Exécuté sans rien afficher, pensez à print() » :

```python
def boucle_while_simple():
    i = 1
    while i <= 5:
        print(i)
        i += 1

boucle_while_simple()
```

Le signalement portait l'hypothèse exacte, et le protocole pour la vérifier :

> RestrictedPython crée un collecteur `_print` par portée de fonction, et le
> lanceur ne lit que celui du module. Vérifie d'abord avec `print("a")` au
> niveau module puis `print("b")` dans une fonction.

---

## 2. Ce que la vérification a montré

| Code | Sortie rendue |
|---|---|
| `print("a")` | `'a'` |
| `def f(): print("b")` puis `f()` | `''` |
| `print("a")` **et** `f()` qui imprime `"b"` | `'a'` — le `b` manque |
| `print` en fonction imbriquée | `''` |
| Le code signalé | `''` |

Hypothèse confirmée, et plus large qu'annoncé : les méthodes de classe et les
fonctions imbriquées sont touchées de la même façon.

---

## 3. Périmètre impacté

| Élément | Impact |
|---|---|
| Carnet d'exercices | Toute sortie écrite dans une fonction, perdue |
| Cellule d'essai des pages de cours | Idem — même exécuteur |
| Correction des exercices (`run_tests`) | Idem, **atténué** : le résultat passe par une ligne marquée imprimée au niveau module (incident 021), donc les tests fonctionnaient. Seules les traces de l'apprenant disparaissaient |
| Données | Aucune perte |

**C'est le défaut le plus large possible sur une plateforme d'apprentissage de
la programmation** : la première chose qu'on y écrit est une fonction qui
affiche.

---

## 4. Diagnostic

`RestrictedPython/transformer.py` appelle `inject_print_collector` à deux
endroits — sur le module (ligne 1204) et sur chaque définition de fonction
(ligne 1274). Il y insère :

```python
_print = _print_(_getattr_)
```

Et réécrit `print(x)` en `_print._call_print(x)`.

`_print_` valait `PrintCollector`, la classe elle-même. **Chaque portée
recevait donc une instance neuve**, et l'exécuteur lisait :

```python
collecte = safe_locals.get("_print")
```

c'est-à-dire la variable du seul espace de noms du module.

Deux conséquences, la seconde plus subtile. Les `print` d'une fonction
vivaient dans une variable locale que rien ne lisait. Et quand un code
n'imprime **que** depuis des fonctions, le module n'a même pas de `_print` — la
bibliothèque n'injecte le collecteur que dans les portées qui emploient
`print` : la lecture rendait alors `None` sur un programme qui avait tout
affiché.

---

## 5. Correction

Une seule instance, partagée par toutes les portées :

```python
collecteur = PrintCollector(safer_getattr)

globales.update({
    CLE_COLLECTEUR: collecteur,
    "_print_": lambda _getattr_=None: collecteur,
    ...
})
```

La fabrique rend toujours le même objet. Les portées imbriquées écrivent dans
le même tampon, dans l'ordre des appels, et l'exécuteur lit ce tampon par une
clé qu'il contrôle — `_collecteur_de_sorties_` — au lieu de la variable
`_print` d'un espace de noms particulier.

**La clé commence par un tiret bas, délibérément** : RestrictedPython refuse à
la compilation tout identifiant qui en porte un, si bien qu'aucun code
d'apprenant ne peut la désigner, ni la lire, ni l'écraser.

L'instance est créée à chaque appel de `_create_safe_globals`, donc à chaque
exécution : deux exécutions successives ne partagent rien.

---

## 6. Vérification

| Cas | Avant | Après |
|---|---|---|
| `print` au niveau module | `'a'` | `'a'` |
| `print` dans une fonction | `''` | `'b'` |
| module **puis** fonction | `'a'` | `'a\nb'` |
| fonction imbriquée | `''` | `'c'` |
| méthode de classe | `''` | `'d'` |
| deux appels de la même fonction | `''` | `'1\n2'` |
| **le code signalé** | `''` | `'1\n2\n3\n4\n5'` |

Un test tient par ailleurs sur le **mécanisme** et non sur ses effets : il
vérifie que la fabrique rend bien la même instance, et que deux exécutions
n'en partagent pas. Sans lui, un correctif futur pourrait rétablir une fabrique
qui rend une instance neuve sans qu'aucun cas ci-dessus ne le montre
nécessairement.

Un troisième test vérifie que **les trois pages** — Carnet, Python Exercises,
cellule des pages de cours — passent par le même exécuteur, et qu'aucune ne
fabrique son propre chemin d'exécution. Si l'une d'elles en avait un, elle
garderait le défaut après sa correction ailleurs, et rien ne le signalerait.

Suite complète : **498 avant, 506 après**.

---

## 7. Famille

**Famille B — l'instrument ne mesure pas ce qu'il prétend.**

Le message affiché à l'apprenant, « Exécuté sans rien afficher, pensez à
`print()` », est un diagnostic. Il était faux, et il était **accusatoire** : il
désignait une faute dans le code de l'apprenant là où la faute était dans
l'exécuteur. Un apprenant qui débute et à qui l'on dit d'ajouter un `print`
qu'il vient d'écrire n'a aucun moyen de s'en sortir.

C'est le troisième défaut de ce dépôt où un message destiné à aider oriente
vers une cause inexistante, après « Aucune sortie » qui masquait une erreur
d'exécution (incident 021) et la `NameError` sur un nom que l'apprenant n'avait
jamais écrit.

La question de la famille B se pose ici sur un message plutôt que sur un
nombre : **ce que cet écran affirme est-il établi, ou seulement déduit d'une
absence ?** Une sortie vide n'établit pas qu'on n'a rien imprimé ; elle établit
qu'on n'a rien *lu*.

---

## 8. Ce que cet incident laisse ouvert

L'énoncé engendré du Carnet affiche un bloc « Exemple attendu » vide de cinq
lignes. Signalé en même temps, non traité ici : c'est un défaut de génération
ou d'affichage de l'énoncé, sans rapport avec l'exécution. Il est à regarder
pour lui-même.
