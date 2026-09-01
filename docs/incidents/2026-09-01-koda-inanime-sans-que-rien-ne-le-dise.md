# Incident 014 — Un personnage immobile a l'air d'un personnage

**Date :** 1er septembre 2026
**Composant :** `static/js/koda.js`
**Gravité :** moyenne — aucune animation de Koda ne fonctionnait, sur toutes les pages
**Statut :** résolu et vérifié en navigateur
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétence concernée :** C17 (E4)

---

## 1. Déclenchement

L'autrice, à l'usage :

> actuellement il ne parle plus quand il répond et il ne s'endort pas non plus.

## 2. Deux défauts, dont un que je croyais tenir

**Le premier se lisait dans le code.** `tourner()` appelait `arreter()`, qui
annulait *deux* minuteurs : celui du battement de l'état courant, et celui du
compte à rebours vers le sommeil. Comme `tourner()` est rappelée à chaque
image, le compte à rebours repartait de zéro à chaque clignement. **Koda ne
pouvait structurellement jamais s'endormir.**

**Le second n'était visible qu'à l'exécution, et il était bien pire.** En
retirant la planche du corps entier, la suppression a emporté le bloc voisin
qui déclarait trois constantes — `IMAGE_FIXE`, `CHANCE_DE_CLIN`,
`ETATS_EVEILLES` — dont les emplois, eux, sont restés.

Relevé en navigateur :

```
Uncaught ReferenceError: ETATS_EVEILLES is not defined  @koda.js:182
elements_dans_le_dom: 2      instances: 0
```

`Koda.brancher()` levait **au chargement de chaque page**. Aucun élément n'était
attaché à l'animateur. Ni la parole, ni l'écoute, ni l'assoupissement, ni le
clin d'œil : rien ne fonctionnait, nulle part, depuis le commit qui a retiré la
planche.

## 3. Pourquoi personne ne l'a vu, moi le premier

**Une planche de sprites qui ne bouge pas affiche sa première image.** Koda
était donc à sa place, bien dessiné, au bon endroit, à la bonne taille — et
parfaitement inanimé. Rien ne manquait à l'écran : il manquait du mouvement,
c'est-à-dire une absence.

C'est la famille C sous une forme nouvelle : **non pas du code jamais appelé,
mais du code appelé qui échoue en silence**. L'échec est absorbé par un état de
repos qui ressemble à un état normal.

Trois choses m'ont trompé, et il faut les nommer :

1. **`node --check` passait.** La syntaxe était valide ; c'est la résolution des
   noms à l'exécution qui ne l'était pas.
2. **Les tests passaient.** Ils lisaient le fichier et vérifiaient des chaînes
   de caractères — ils ne l'exécutaient pas.
3. **J'avais annoncé le travail comme fait**, en écrivant explicitement « je
   n'ai pas vu le mouvement ». La réserve était juste ; je ne suis pas allé
   au bout, alors que le navigateur sans tête était déjà en place et servait à
   mesurer des mises en page depuis le matin.

## 4. Correction

Les trois constantes sont rétablies. Les deux minuteurs sont séparés :
`arreterLeBattement()` pour le battement, `arreter()` pour tout.

Un troisième défaut est apparu en vérifiant : un Koda invisible au chargement —
panneau replié — abandonnait définitivement, rien ne le rappelant quand il
réapparaissait. Il repasse désormais une fois par seconde.

## 5. Vérification, en navigateur cette fois

| Contrôle | Résultat |
|---|---|
| Éléments attachés à l'animateur | **2** |
| Erreurs JavaScript | **aucune** |
| Images distinctes pendant trois secondes de parole | **19** |
| Enchaînement de la poignée laissée seule | **repos → somnole → dort** |

## 6. Ce qu'on en retient

**Un test qui lit un fichier ne dit rien de ce qu'il fait.** Les tests de Koda
vérifiaient la présence de chaînes ; le script pouvait lever à la première
ligne sans qu'aucun ne bronche. Un contrôle a été ajouté — toute constante
employée doit être déclarée — mais il ne remplace pas ce qui manquait vraiment :
**ouvrir la page**.

Et la réserve honnête n'est pas une protection. Écrire « je n'ai pas vu le
mouvement » décrit exactement le trou par lequel le défaut est passé. Le dire ne
le rebouche pas.
