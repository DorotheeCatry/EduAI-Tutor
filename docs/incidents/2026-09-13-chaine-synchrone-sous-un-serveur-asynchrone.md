# Incident 023 — Une seule couche synchrone, et toute la chaîne haute l'était

**Date :** 13 septembre 2026
**Composant :** `apps/users/middleware.py`, `eduai_project/statiques.py`, `eduai_project/settings.py`
**Gravité :** modérée — dégradation de performance, aucun défaut fonctionnel
**Statut :** résolu, vérifié par huit tests
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — mise en production ; C17 (E4) ; C18 (E4)

---

## 1. Déclenchement

Relevé dans les journaux de l'hébergeur, déploiement `08e6a95f`, à l'occasion
d'une vérification de routine après mise en ligne :

```
/app/.venv/lib/python3.13/site-packages/django/core/handlers/asgi.py:333:
Warning: StreamingHttpResponse must consume synchronous iterators in order to
serve them asynchronously. Use an asynchronous iterator instead.
```

C'était le badge « ⚠ 1 » du service `web`. Aucune requête n'échouait : les
lignes voisines du journal portent des `200` et des `304`.

---

## 2. Ce que l'avertissement coûtait réellement

Le code que Django exécute après avoir averti :

```python
for part in await sync_to_async(list)(self.streaming_content):
    yield part
```

Il **matérialise le fichier entier en mémoire** avant d'en envoyer le premier
octet, au lieu de le diffuser par blocs de 4 Ko.

Sur ce projet, cela portait sur les plus gros fichiers servis :

```
1,4 Mo   ANGRY_TALKING.gif
784 Ko   JUMPING.gif
112 Ko   koda_angry.png
```

Le service tourne avec **un seul travailleur** (choix documenté dans
`docker/entree-web.sh` : la couche de canaux et le compteur Prometheus vivent
en mémoire de processus). Chaque affichage d'une animation réservait donc son
poids d'un coup.

---

## 3. Diagnostic — et une première hypothèse fausse

**Première lecture, incomplète.** WhiteNoise 6.12 n'a aucun chemin asynchrone
— vérifié sur le paquet installé entier, pas un seul `async def`. Il rend un
`FileResponse` dont le contenu est un itérateur synchrone. La conclusion
paraissait acquise : c'est WhiteNoise, il suffit de l'envelopper.

**Une couche intermédiaire a été écrite, et n'a rien changé.** L'avertissement
subsistait, sans qu'aucune erreur ne l'explique. Le code semblait pourtant
juste.

**La cause réelle.** `BaseHandler.load_middleware` compose la chaîne **de bas
en haut**, sur `reversed(MIDDLEWARE)`, avec cette règle :

```python
elif not handler_is_async and middleware_can_sync:
    middleware_is_async = False
```

Une couche purement synchrone rend donc synchrone **tout ce qui la surmonte et
accepte ce mode**. Le relevé de la chaîne réelle, obtenu en rejouant cet
algorithme :

| Mode | Couche |
|---|---|
| ASYNC | `BrowserReloadMiddleware` |
| ASYNC | `XFrameOptionsMiddleware` |
| ASYNC | `MessageMiddleware` |
| **sync** | **`LangueDeLApprenant`** ← la cause |
| sync | `AuthenticationMiddleware` |
| sync | `CsrfViewMiddleware` |
| sync | `CommonMiddleware` |
| sync | `LocaleMiddleware` |
| sync | `SessionMiddleware` |
| sync | `WhiteNoiseMiddleware` |
| sync | `SecurityMiddleware` |

`LangueDeLApprenant` — un intergiciel **du projet**, écrit sans
`async_capable` — faisait basculer huit couches sur onze. L'application était
servie en ASGI et exécutait en réalité toute la partie haute de sa chaîne en
mode synchrone.

Le fichier statique n'était que le symptôme visible, parce que c'est le seul
endroit où Django prend la peine d'avertir.

---

## 4. Correction

**`LangueDeLApprenant` sait fonctionner dans les deux modes.** Le chemin
asynchrone emploie `await request.auser()` et non `request.user` : ce dernier
est un objet paresseux dont la résolution interroge la base, ce qui lève
`SynchronousOnlyOperation` depuis une pile asynchrone. `auser` est posé par
`AuthenticationMiddleware` à côté de `user`, et cet intergiciel est bien
déclaré après lui.

La règle de décision — quelle langue retenir — est extraite dans
`_langue_utilisable`, partagée par les deux chemins : deux implémentations
parallèles finiraient par diverger, et l'une des deux n'est éprouvée qu'en
production.

**`WhiteNoiseAsynchrone`**, sous-classe locale de `WhiteNoiseMiddleware`,
déclare `async_capable` et rend ses fichiers par un générateur asynchrone qui
tire **un bloc par attente**. Elle ne touche ni à la résolution du fichier, ni
aux en-têtes, ni au cache, ni à l'empreinte : tout cela reste à la
bibliothèque.

**Pourquoi une sous-classe plutôt qu'une couche indépendante.** Une couche
posée au-dessus de WhiteNoise reste soumise à la même règle de composition :
WhiteNoise étant synchrone, elle était instanciée en synchrone et sa branche
utile n'était jamais atteinte. Lui déclarer `sync_capable = False` l'aurait
forcée en asynchrone, au prix d'un `async_to_sync` sur **toute** requête d'une
pile synchrone — les tests compris.

---

## 5. Vérification

Sur la pile ASGI réelle, avant et après :

| | Avant | Après |
|---|---|---|
| Avertissements « synchronous iterators » | 1 | **0** |
| Octets rendus | 113 679 | 113 679 |
| Contenu identique au fichier | oui | oui |
| Couches de la chaîne en mode synchrone | 8 sur 11 | **0 sur 11** |

`tests/test_pile_asynchrone.py`, huit tests. Le plus important ne teste pas un
effet mais une **structure** : il rejoue l'algorithme de composition de Django
et échoue si une couche purement synchrone est ajoutée, en nommant celle qui
bascule et toutes celles qu'elle entraîne. C'est le garde-fou qui manquait —
le défaut n'était visible par aucun test, puisque la couche fautive
fonctionnait parfaitement.

Suite complète : **506 avant, 514 après**.

---

## 6. Ce que cet incident apprend

**Aucun test ne couvrait le chemin asynchrone.** Le client de test de Django
est synchrone : les 506 tests du projet passaient tous par la branche
synchrone des intergiciels. Une couche pouvait donc être fausse en asynchrone
sans qu'aucun test ne bronche — et c'est précisément ce qui est arrivé, à
l'envers : elle n'avait pas de chemin asynchrone du tout.

**Le symptôme désignait le mauvais coupable, et de façon convaincante.**
WhiteNoise était bien synchrone, l'analyse était exacte, et la correction
fondée sur elle n'a rien changé. C'est l'échec de la première tentative qui a
conduit à relever la chaîne entière — l'inventaire, plutôt que l'élément que le
message nomme. Le même réflexe avait laissé une garde de RestrictedPython
absente pendant des semaines (incident 021).

**Famille A — vérifié dans un contexte, employé dans un autre.**
`LangueDeLApprenant` était correcte dans le contexte où elle a été écrite et
éprouvée : une chaîne synchrone, celle des tests et du serveur de
développement. Employée sous un serveur ASGI, elle changeait le mode de toute
la chaîne au-dessus d'elle. Rien en elle n'était faux ; c'est l'environnement
qui différait.

La question de la famille A, posée ici sur un mode d'exécution : **ce composant
a-t-il été éprouvé dans le mode où il s'exécutera en production ?**
