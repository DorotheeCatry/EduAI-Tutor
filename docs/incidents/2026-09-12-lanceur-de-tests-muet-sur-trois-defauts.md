# Incident 021 — Une soumission correcte, trois tests en échec, et rien pour le dire

**Date :** 12 septembre 2026
**Composant :** `apps/exercises/security.py`, `apps/exercises/templates/exercises/exercise_detail.html`
**Gravité :** majeure — le dispositif d'évaluation des exercices rendait un verdict faux
**Statut :** résolu, vérifié par dix-huit tests
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — bac à sable ; C17 (E4) ; C18 (E4)

---

## 1. Déclenchement

Signalement de l'autrice, sur la page « Python Exercises », exercice
« Calcul de la somme des chiffres avec des boucles » :

> Ma solution est correcte (vérifiée à la main : 13 -> 55, 5 -> 15, 0 -> 0,
> -3 -> None), mais 3 tests sur 4 échouent avec « Obtenu : Aucune sortie ».

Le code soumis :

```python
def total_digit_sum(n):
    if n < 0:
        return None
    total = 0
    for nombre in range(1, n + 1):
        for chiffre in str(nombre):
            total += int(chiffre)
    return total
```

Le signalement portait déjà le raisonnement décisif : *« le seul test qui passe
(n = 0) est le seul où la boucle ne s'exécute pas »*.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Correction des exercices (C17) | Verdict faux sur toute solution employant `+=` |
| Cellule d'essai des pages de cours | Même bac à sable, même échec |
| Exercices attendant `None` | **Impossibles à réussir**, quel que soit le code |
| Diagnostic par l'apprenant | Aucun : la cause était affichée « Aucune sortie » |
| Données | Aucune perte. Des soumissions correctes ont pu être enregistrées comme échouées |

---

## 3. Diagnostic

Reproduit à l'identique avant toute modification. Trois défauts distincts, qui
se cumulaient.

### Défaut 1 — Une garde de RestrictedPython manquait

L'hypothèse initiale visait les builtins : `str` ou `int` absents de la liste
blanche. **Elle était fausse**, et le contrôle l'a montré en une commande —
`str`, `int`, `range`, `len` répondent tous.

Le nom manquant n'est pas un builtin mais une **garde** :

```
Execution error: name '_inplacevar_' is not defined
```

RestrictedPython réécrit `total += int(chiffre)` en
`total = _inplacevar_('+=', total, int(chiffre))`. Relevé sur la version 8.1
installée : `_inplacevar_` n'apparaît que dans `transformer.py`, à l'endroit qui
l'émet. Ni `Guards`, ni `Utilities`, ni `Eval` ne le définissent — la
bibliothèque laisse cette fonction à l'hôte.

Inventaire complet des gardes que cette version peut émettre, comparé à ce que
`security.py` définissait :

| Garde | Définie |
|---|---|
| `_apply_`, `_getattr_`, `_getitem_`, `_getiter_` | oui |
| `_iter_unpack_sequence_`, `_print_`, `_unpack_sequence_`, `_write_` | oui |
| `__metaclass__` | oui |
| **`_inplacevar_`** | **non** |

Neuf sur dix. Et les deux dernières — `__metaclass__`, `_apply_` — avaient déjà
été ajoutées après coup, chacune à l'occasion d'une panne. Le commentaire qui
les accompagne énonçait pourtant la bonne règle : « ce ne sont pas des options,
ce sont les fonctions que le code compilé appelle. » La règle était juste, la
liste incomplète.

### Défaut 2 — `None` confondu avec « pas de résultat »

Le code de test assemblé par le lanceur :

```python
result = total_digit_sum(-3)
if result is not None:
    print(result)
```

Une fonction qui rend `None` n'imprimait rien. Et le nettoyage de sortie
écartait explicitement les lignes valant `None` :

```python
if line and line != 'None':
```

Double verrou. **Un test attendant `None` ne pouvait pas passer**, quel que
soit le code de l'apprenant.

Un troisième effet, plus discret : la sortie retenue était « la première ligne
non vide ». Un exercice dont la fonction appelle `print` — fréquent, et
légitime — voyait sa propre trace comparée au résultat attendu.

### Défaut 3 — La cause était connue du serveur et jamais montrée

`run_tests` remplissait `test_result['error']` avec le message exact, puis
l'écrivait sur la sortie standard :

```python
test_result['error'] = error_msg
print(f"   Erreur: {execution_result['error']}")
```

Le gabarit, lui, ne lisait que `result.actual` :

```javascript
if (actualEl) actualEl.textContent = result.actual || 'Aucune sortie';
```

`result.error` n'apparaissait nulle part dans la boucle d'affichage. La cause
était donc **visible dans la console du serveur, invisible dans le navigateur**.

---

## 4. Correction

**Défaut 1.** `garde_affectation_augmentee` écrite à partir du module
`operator`, sur une table close de douze opérateurs arithmétiques et de
chaînes. Elle lève `ValueError` sur un symbole absent plutôt que de retomber sur
une valeur par défaut : un symbole inconnu signifie que la bibliothèque a
évolué, et le dire vaut mieux que produire un résultat faux.

La table emploie les formes **non mutantes** (`operator.add`, pas `iadd`) :
`@=` reste dehors, faute d'objet ici.

**Défaut 2.** Le résultat est imprimé sur une ligne marquée, **toujours** :

```python
eduai_resultat_du_test = total_digit_sum(-3)
print('__RESULT__=' + repr(eduai_resultat_du_test))
```

Le lanceur cherche cette ligne — la dernière, le code de l'apprenant s'exécutant
avant — et rend un couple `(valeur, trouvée)` plutôt qu'une chaîne vide : « la
fonction a rendu la chaîne vide » et « aucun résultat n'a été produit » sont
deux états, et les confondre était le défaut à corriger.

La comparaison se fait sur `repr`, avec repli sur le texte brut : les énoncés en
base écrivent `55`, pas `'55'`, et exiger le `repr` des deux côtés les aurait
tous fait échouer.

*Piège rencontré :* la variable s'appelait d'abord `__eduai_resultat__`.
RestrictedPython refuse à la compilation tout identifiant commençant par un
tiret bas — y compris dans le code que le lanceur assemble lui-même. Les tests
échouaient alors **tous**, sur un message parlant d'une variable que l'apprenant
n'a jamais écrite. Le préfixe est désormais `eduai_`.

**Défaut 3.** Le gabarit affiche `result.error` dans un élément dédié quand il
existe, et « aucun résultat » n'est plus un fourre-tout.

---

## 5. Vérification

Sur la soumission signalée, avant et après :

| Test | Avant | Après |
|---|---|---|
| `total_digit_sum(13)` | `''` — échec | `'55'` — réussi |
| `total_digit_sum(5)` | `''` — échec | `'15'` — réussi |
| `total_digit_sum(0)` | `'0'` — réussi | `'0'` — réussi |
| `total_digit_sum(-3)` | `''` — échec | `'None'` — réussi |

Cas limites éprouvés : chaîne rendue avec et sans guillemets dans l'énoncé,
liste, chaîne vide, booléen, flottant, `print` parasite dans la fonction,
fonction absente, division par zéro. Les deux derniers rendent désormais leur
message — `name 'g' is not defined`, `division by zero` — au lieu d'une case
vide.

`tests/test_lanceur_exercices.py`, dix-huit tests. Suite complète : **478 avant,
496 après, verte**.

---

## 6. Famille

**Famille A — vérifié dans un contexte, employé dans un autre**, pour le
défaut 3, et c'est le plus instructif des trois.

Le message d'erreur existait, était juste, et **était affiché** — sur la sortie
standard du serveur. Quiconque développait avec le serveur sous les yeux le
voyait. Il était donc vérifié dans le contexte de la console, et employé dans
celui du navigateur, où rien ne le rendait.

C'est la question de la famille A, posée sur une information plutôt que sur une
dépendance : **qu'est-ce que mon environnement affiche, que l'environnement de
l'utilisateur n'affichera pas ?** Un `print` de mise au point répond à la
question « le serveur sait-il ce qui a échoué ? » — jamais à « l'utilisateur
peut-il le savoir ? ».

Les deux autres défauts relèvent d'un motif voisin déjà nommé dans ce registre :
une règle juste énoncée dans un commentaire (« ce ne sont pas des options »)
appliquée à une liste incomplète, et une comparaison qui écarte `None` sans voir
qu'un test peut légitimement l'attendre.

---

## 7. Écart de comportement introduit par la correction

**L'affectation augmentée sur un conteneur mutable ne mute plus en place.**
C'est la conséquence directe du choix de la table : elle emploie les formes non
mutantes d'`operator` — `add`, pas `iadd`. Mesuré :

```
a = [1]; b = a; b += [2]

Python réel   →  a == [1, 2]   b == [1, 2]   a is b  →  True
Bac à sable   →  a == [1]      b == [1, 2]   a is b  →  False
```

L'écart vaut pour `+=` sur une liste, `|=` sur un dictionnaire ou un ensemble,
et toute affectation augmentée sur un objet mutable. Il ne vaut **pas** pour les
méthodes mutantes : `append` et `extend` modifient bien l'objet partagé, vérifié.

**Conséquence pour l'écriture des exercices.** Aucun exercice ne doit enseigner
ni éprouver l'aliasing par affectation augmentée : il donnerait ici une réponse
contraire à celle qu'un apprenant obtient dans son propre interpréteur,
c'est-à-dire qu'il enseignerait le faux. Pour montrer l'aliasing, employer
`append` ou `extend`.

L'écart est écrit à trois endroits, délibérément : dans le module qui le
produit (`OPERATEURS_AUGMENTES`, à côté du code), ici, et dans deux tests qui
l'épinglent — `test_l_ecart_d_aliasing_par_affectation_augmentee_est_documente`
fige le comportement actuel, et échouera le jour où l'implémentation changera ;
`test_l_ecart_d_aliasing_est_ecrit_dans_le_module` vérifie que le module
continue de le dire.

**Pourquoi ne pas employer `iadd` tout de suite.** Les formes mutantes modifient
un objet en place, ce qui pose une question distincte : qu'accepte-t-on de
laisser muter dans un bac à sable, et quelles sont les conséquences sur les
gardes d'accès ? Elle mérite d'être traitée pour elle-même, pas en marge d'un
correctif de lanceur de tests. L'écart est donc assumé, écrit, et surveillé.

---

## 8. Ce que la correction laisse en place

Le lanceur affiche toujours sur la sortie standard, en plus de renseigner le
résultat. Ces `print` ne sont pas retirés ici : ils servent au diagnostic côté
serveur et ne nuisent pas, dès lors que l'information atteint aussi
l'utilisateur. Ce qui était fautif n'était pas le `print`, c'était qu'il fût le
seul destinataire.

---

## 9. Note de numérotation

Le numéro 020 est employé deux fois dans ce registre — par le dossier du 25/08
(modèle retiré du catalogue) et par celui du 07/09 (hébergeur figé sur une
empreinte). Le présent dossier prend 021. Le doublon n'est pas corrigé ici :
renuméroter un dossier romprait les renvois qui le citent. Une note en tête de
`docs/motifs_incidents.md`, la porte d'entrée du registre, le signale aux
lecteurs.
