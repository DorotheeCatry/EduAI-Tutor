# Incident 005 — Une clé accentuée répondait 500 au lieu de 401

**Date :** 29 août 2026
**Composant :** `service_ia/securite.py`, fonction `verifier_cle`
**Gravité :** majeure — erreur serveur sur un appel simplement invalide
**Statut :** résolu, vérifié, couvert par un test
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C9 (E2), C13 (E3) — OWASP API2, C18 (E4)
**Identifiants de corrélation :** `a9b6d93c4a57` (détection), `4914fc58a80f`
(reproduction du 29/08)

---

## 1. Déclenchement

Essais d'authentification avant mise en ligne. Une clé est collée par erreur
dans l'en-tête `X-Cle-Service` — une valeur invalide contenant une lettre
accentuée. Le service répond **500** :

```json
{"detail":"Erreur interne du service.","code":"erreur_interne",
 "identifiant_incident":"4914fc58a80f"}
```

Attendu : **401**. La clé est fausse, rien de plus.

## 2. Diagnostic

`verifier_cle` comparait deux chaînes :

```python
if hmac.compare_digest(fournie, attendue):
```

`hmac.compare_digest` accepte deux `str` **uniquement si les deux ne
contiennent que des caractères ASCII**. Sinon elle lève :

```
TypeError: comparing strings with non-ASCII characters is not supported
```

La restriction est logique du point de vue de la fonction : la comparaison à
temps constant travaille sur des octets, et une chaîne Python n'a pas de
représentation en octets tant qu'un encodage n'est pas choisi. La bibliothèque
refuse de choisir à la place de l'appelant, plutôt que de comparer deux valeurs
dont la longueur en octets dépendrait d'un encodage implicite.

L'exception traversait la dépendance d'authentification et sortait en 500.

### Pourquoi les tests ne le voyaient pas

Le test d'une clé invalide existait, et portait ce commentaire :

> *Valeur en ASCII pur : les en-têtes HTTP ne transportent pas d'accents, et un
> client qui en enverrait échouerait avant même d'atteindre le service.*

**L'hypothèse était fausse**, et elle était écrite, ce qui la rendait plus
solide qu'un simple oubli : elle décourageait d'écrire le test manquant.

Deux faits la contredisent :

1. Les en-têtes HTTP sont décodés en **latin-1** par Starlette. Une lettre
   accentuée envoyée en UTF-8 arrive donc sous forme de deux caractères hors
   ASCII. La chaîne atteint bien la comparaison.
2. C'est **le client d'essai** de FastAPI qui encode ses en-têtes en ASCII et
   refuse la valeur — pas le serveur. Un client réel (`curl`, `requests`) pose
   les octets sur le fil sans ce scrupule.

La protection observée appartenait donc à l'outil de test, et avait été prise
pour une propriété du protocole.

## 3. Conséquences si le défaut avait atteint la production

| Conséquence | Détail |
|---|---|
| Réponse trompeuse | Un 500 annonce une panne du service là où l'appel est simplement refusé. L'appelant réessaie au lieu de corriger sa clé |
| Bruit dans les journaux | Toute clé mal formée produit une erreur interne. Les vraies pannes se noient dans ce fond |
| **Fuite d'information** | Un attaquant distingue 401 (clé fausse en ASCII) de 500 (clé fausse non ASCII). Il apprend que la nature de sa saisie modifie le traitement — exactement ce que le reste de cette fonction s'applique à ne pas révéler |

Le troisième point est le plus sérieux : la fonction prend soin de répondre à
l'identique pour une clé absente et pour une clé fausse, précisément pour ne
rien apprendre à l'appelant. Ce défaut rouvrait un canal à côté.

## 4. Résolution

La comparaison porte désormais sur des octets :

```python
fournie_octets = fournie.encode("utf-8", "surrogateescape")

for attendue in cles:
    if hmac.compare_digest(fournie_octets, attendue.encode("utf-8", "surrogateescape")):
        return attendue
```

`surrogateescape` plutôt qu'un encodage strict : les octets non décodables
d'une variable d'environnement arrivent en Python sous forme de substituts,
qu'un encodage strict rejetterait par une `UnicodeEncodeError` — le même défaut
déplacé d'un cran. **Une clé illisible doit aboutir à un refus, jamais à une
exception.**

La propriété de temps constant est préservée : elle vaut sur des octets, et
c'est justement en octets que la comparaison a désormais lieu.

## 5. Test de non-régression

`test_une_cle_non_ascii_est_refusee_et_non_une_erreur_serveur` envoie l'en-tête
**en octets**, pour reproduire ce que reçoit le serveur et non ce que le client
d'essai veut bien émettre. Il vérifie le code 401 **et** l'égalité de la
réponse avec celle d'une clé fausse en ASCII — le canal secondaire est donc
couvert, pas seulement le code de retour.

| Vérification | Sans le correctif | Avec le correctif |
|---|---|---|
| Test de non-régression | **échec** | succès |
| Suite complète (88 tests) | — | **88 succès** |
| `ruff` | — | aucun signalement |

Le commentaire fautif a été retiré du test existant : laisser une hypothèse
fausse en place, c'est laisser en place la raison pour laquelle le test manquait.

## 6. Ce que l'incident enseigne

Il rejoint le motif que ce projet documente depuis une semaine, sous une forme
nouvelle : **ce n'est pas une mesure qui mentait, c'est une hypothèse écrite
dans un test.** Un commentaire qui affirme qu'un cas est impossible interdit
d'écrire le test de ce cas — et l'affirmation, une fois versionnée, se relit
comme une vérification déjà faite.

Une hypothèse d'impossibilité écrite dans un test doit être ou bien démontrée,
ou bien remplacée par le test qu'elle dispense d'écrire.
