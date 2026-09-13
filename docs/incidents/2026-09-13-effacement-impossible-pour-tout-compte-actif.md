# Incident 024 — La suppression de compte échouait pour tout apprenant réel

**Date :** 13 septembre 2026
**Composant :** `apps/agents/apps.py`, `apps/users/effacement.py`
**Gravité :** majeure — droit à l'effacement inopérant
**Statut :** résolu, vérifié par quatre tests dont un en processus neuf
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C4 (E1) — droit à l'effacement ; C18 (E4) ; C13 (E3)

---

## 1. Déclenchement

Découvert **par accident**, et c'est ce qui rend cet incident instructif.

L'autrice voulait alimenter les courbes de Grafana avant sa soutenance. Le
chemin choisi était : créer un compte de mesure, lui faire produire du trafic
réel, puis l'effacer — les métriques Prometheus vivant dans le collecteur, elles
survivent à la suppression du compte, et la base resterait intacte.

L'effacement a échoué :

```
IntegrityError: update or delete on table "users_kodauser" violates
foreign key constraint "agents_learningsession_user_id_09da2bd7_fk_users_kodauser_id"
DETAIL: Key (id)=(6) is still referenced from table "agents_learningsession".
```

Sans cette manœuvre, le défaut serait passé à la soutenance.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Droit à l'effacement (C4) | **Inopérant pour tout compte ayant utilisé l'application** |
| Comptes concernés | Tous, en pratique : ouvrir un quiz, poser une question à Koda ou lancer une génération crée une `LearningSession` |
| Intégrité des données | **Aucune atteinte.** L'échec est atomique — rien n'était supprimé à moitié |
| Transparence de l'inventaire | Second défaut, voir § 4 |

Un apprenant demandant l'effacement de ses données aurait obtenu une erreur
technique. C'est un manquement au RGPD, pas une gêne d'affichage.

---

## 3. Diagnostic

`apps/agents/` **n'a pas de `models.py`**. Ses deux modèles — `LearningSession`
et `UserMistake` — vivent dans `agent_watcher.py`, à côté du `WatcherAgent`
qui les emploie.

Django importe automatiquement `<application>/models.py` au démarrage. Absent
ici, les deux modèles n'étaient donc **pas enregistrés** au moment où Django
calcule — et met en cache — `User._meta.related_objects`.

Mesuré dans un processus neuf :

```
avant import de agent_watcher : relations agents connues → AUCUNE
après                          : LearningSession, UserMistake
```

Django ne connaissait pas la cascade, ne la collectait pas, et PostgreSQL
refusait la suppression sur sa contrainte de clé étrangère.

**Le `on_delete=models.CASCADE` était pourtant bien déclaré** dans les deux
modèles. Il n'a jamais été faux : il n'était simplement pas lu.

### Pourquoi neuf tests d'effacement n'ont rien vu

`tests/test_effacement_compte.py` ne mentionne **ni `LearningSession`, ni
`UserMistake`**. Il crée un compte, un avatar, des exercices, des sessions
Django — jamais une séance d'apprentissage. La clé étrangère qui casse n'était
donc jamais éprouvée.

S'y ajoute un second effet, plus retors : dans une suite de tests, d'autres
modules importent `agent_watcher` avant que l'effacement ne s'exécute. La
relation y est alors enregistrée, et la cascade **fonctionne**. Un test
fonctionnel écrit naïvement passerait donc même avec le défaut en place.

---

## 4. Un second défaut, trouvé par le même test

L'inventaire présenté avant confirmation — `inventorier()` — ne comptait **ni
les séances, ni les erreurs relevées, ni les fiches de compétence et leurs
enrichissements**.

L'apprenant confirmait donc la suppression de son historique de travail sans
que rien ne le lui dise. La docstring de `_compteurs` annonçait pourtant le
risque : « une liste explicite se relit et se complète » — elle se complète,
encore faut-il le faire.

---

## 5. Correction

**L'import des modèles dans `ready()`** de `AgentsConfig`, avant le branchement
de la sonde. C'est le point que Django prévoit pour cela, appelé une fois,
après le chargement des réglages.

Choix : là plutôt qu'un `models.py` qui réexporterait les classes. Deux
domiciles pour un même modèle est précisément ce qui produit ce genre d'écart.

**Quatre entrées ajoutées à l'inventaire** : `seances_apprentissage`,
`erreurs_relevees`, `fiches_de_competence`, `ajouts_de_fiche`.

---

## 6. Vérification

Dans un processus neuf, sans import préalable de `agent_watcher` — c'est-à-dire
dans la condition du serveur :

```
inventaire : {'compte': 1, 'seances_apprentissage': 1, 'erreurs_relevees': 1}
conforme   : True | subsiste : rien
compte encore présent : False
```

`tests/test_effacement_avec_seances.py`, quatre tests. Le plus important
**s'exécute dans un sous-processus** avec un `django.setup()` frais : c'est le
seul moyen de reproduire la condition réelle, puisque dans la suite la relation
est déjà enregistrée par d'autres imports. Sans cette précaution, le garde-fou
passerait au vert sur un défaut de retour — exactement ce qui vient d'arriver
aux neuf tests existants.

Suite complète : **514 avant, 518 après**.

---

## 7. Famille

**Famille A — vérifié dans un contexte, employé dans un autre.**

Le contexte qui différait n'est ni un fil d'exécution, ni une variable
d'environnement, ni un fichier présent sans être versionné. C'est **l'ordre des
imports d'un processus**.

Dans un processus de test, `agent_watcher` est importé tôt : la cascade
fonctionne. Dans un processus serveur qui n'en a pas besoin, elle est inconnue.
Le code est identique, son comportement non.

La question de la famille A se pose donc ici sous une forme nouvelle :
**qu'est-ce que mon processus a déjà importé, que le processus cible
n'importera pas ?**

C'est la deuxième fois en deux jours que le mode d'exécution d'un processus —
et non son code — produit un défaut : l'incident 023 portait sur une chaîne
d'intergiciels basculée en synchrone par une seule couche. Les deux se
ressemblent assez pour mériter d'être rapprochés.

---

## 8. Ce que cet incident apprend sur la découverte

Il n'a été trouvé ni par un test, ni par une relecture, ni par un usage
ordinaire — mais parce qu'une manœuvre annexe, destinée à tout autre chose,
est passée par un chemin que rien n'empruntait jamais.

Le droit à l'effacement est une fonction qu'on écrit, qu'on documente, et que
personne n'exerce avant le jour où quelqu'un le demande.
