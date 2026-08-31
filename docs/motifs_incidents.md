# Motifs récurrents des incidents

**Date :** 31 août 2026
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C20 (E5) — monitorage ; C18 (E4) ; C13 (E3) ; C19 (E5)

---

## Pourquoi ce document

Neuf incidents ont été documentés entre le 26 et le 31 août 2026. Pris un par
un, ce sont neuf accidents. Regroupés, ce sont **deux familles** — et une
famille se prévient, là où un accident ne fait que se réparer.

Ce document ne remplace pas les dossiers d'incident : il dit ce qu'ils ont en
commun, et quelle question poser pour éviter la prochaine occurrence.

---

## Famille A — Vérifié dans un contexte, employé dans un autre

**Trois occurrences en quatre jours.** C'est ce qui la qualifie de famille.

| # | Vérifié dans… | Employé dans… | Ce qui a échoué |
|---|---|---|---|
| 003, 28/08 | un script, contexte de l'import | une requête HTTP, fil ou tâche distincte | La sonde de monitorage n'attachait aucun rappel. **22 heures de traces perdues** |
| 007, 30/08 | le poste, `DEBUG=True` | l'intégration continue, `DEBUG=False` | Quatre tests échouaient sur une redirection HTTPS que le poste ne déclenche jamais |
| — , 31/08 | un poste encombré, `staticfiles/` hérité d'un ancien `collectstatic` | un clone vierge | Aucune page ne se rendait hors DEBUG, faute de manifeste de fichiers statiques |

### Le mécanisme commun

Dans les trois cas, **l'objet vérifié était correct**. Ce qui différait était
l'environnement : un contexte d'exécution, une variable, le contenu d'un
répertoire. La vérification avait eu lieu là où elle était commode, pas là où
le code allait servir.

Ce déplacement est invisible par construction : on ne voit pas ce dont on
dispose sans y penser. Le poste de développement porte un fichier produit six
semaines plus tôt, une variable posée dans un `.env`, un contexte
d'import — autant de choses qu'aucune ligne de code ne mentionne.

### La question à poser

> **Qu'est-ce que mon environnement fournit, que l'environnement cible ne
> fournira pas ?**

Trois réponses possibles, dans l'ordre où elles ont été découvertes :

1. **Un contexte d'exécution** — fil, tâche, processus. Éprouver depuis un
   serveur, jamais depuis un script seul.
2. **Une variable d'environnement** — `DJANGO_DEBUG=False uv run pytest`
   reproduit les conditions de la chaîne et de l'hébergeur.
3. **Un fichier présent sans être versionné** — corpus, `staticfiles/`, base
   SQLite, `.env`. La seule parade est de rejouer **depuis un clone** :

```bash
git clone --branch <branche> . /tmp/clone-ci
cd /tmp/clone-ci && DJANGO_DEBUG=False uv run --project <depot> pytest
```

Le 31/08, les deux premières reproductions n'ont rien donné et la troisième a
trouvé en une exécution. L'ordre a son importance : la plus coûteuse est aussi
la plus complète.

### Ce qui est en place

- `docs/strategie_tests.md` porte les trois niveaux de reproduction.
- La chaîne d'intégration s'exécute sur **toute** branche, à chaque poussée :
  elle ne protège que le code qui lui parvient, ce que l'incident 007 a montré
  au prix de trente-sept commits retenus en local.

---

## Famille B — L'instrument ne mesure pas ce qu'il prétend

| # | L'instrument | Ce qu'il mesurait vraiment |
|---|---|---|
| 001, 27/08 | un chargeur annonçant 6 836 documents | le nombre de lignes **envoyées**, sur une base restée vide |
| 003, 28/08 | une sonde se déclarant branchée | son propre démarrage, jamais les appels |
| 006, 29/08 | une sonde de santé nommant une collection | une collection que la recherche n'interrogeait pas |
| 009, 31/08 | une empreinte de corpus | les octets d'un fichier que SQLite réécrit à la lecture |

### Le mécanisme commun

L'instrument **fonctionne**. Il produit une valeur, à l'heure, sans erreur — et
cette valeur est vraie. Elle répond simplement à une autre question que celle
qu'on lui pose.

C'est ce qui rend cette famille plus retorse que la première : rien n'échoue.
Un contrôle absent se remarque ; un contrôle qui répond toujours, jamais.

### Les deux questions à poser

> **De quoi cette valeur est-elle l'effet — et non l'intention ?**

Un chargeur doit compter ce que la base contient, pas ce qu'il a envoyé. Une
sonde doit compter des appels tracés, pas son propre démarrage.

> **Qu'est-ce qui doit rester constant pour que ce contrôle reste silencieux ?**

Si la réponse contient quoi que ce soit qui bouge sans que l'objet surveillé
change, le contrôle est à réécrire. C'est ce qui a condamné l'empreinte sur les
octets de SQLite — et ce qui a conduit, le même jour, à régler le seuil de
latence par environnement plutôt qu'à le relever pour faire taire l'alarme
(décision 024).

### Le corollaire, énoncé le 31/08

**Une alarme qui se déclenche toujours est une alarme qu'on cesse de lire.** Un
contrôle dont l'alerte serait permanente est pire qu'un contrôle absent :
l'absence se remarque, tandis qu'une alarme permanente s'apprend, et finit par
être traitée comme le bruit de fond d'un système en bon état.

---

## Ce que les deux familles partagent

Une action et son effet ne coïncident pas sans qu'on aille le constater.

La famille A porte sur **où** l'on constate, la famille B sur **quoi**. Les deux
se traitent par la même discipline, et c'est la seule règle générale que ce
projet retire de ses neuf incidents :

> Vérifier l'effet, dans les conditions où il se produira.

---

## Une troisième famille, ouverte

Deux occurrences seulement, donc pas encore une famille — mais le compte est
tenu.

| Date | Le réglage | Ce qui manquait |
|---|---|---|
| 31/08 | `language_preference`, choisi et enregistré | rien ne le lisait pour l'interface, seul l'orchestrateur d'agents le consultait |
| 31/08 | `LANGUAGE_CODE = 'en'` avec un unique catalogue `fr` | aucune traduction n'était jamais appliquée |

**Un réglage stocké sans être lu**, ou lu ailleurs que là où on le croit. La
parade est un test qui porte sur l'effet du réglage sur ce que l'utilisateur
reçoit — jamais sur sa présence en base. Un test vérifiant « la préférence est
bien enregistrée » serait passé au vert pendant toute la durée du défaut.

Si une troisième occurrence apparaît, cette section devient une famille et
rejoint les deux premières.

---

## Pièces citées

| Document | Contenu |
|---|---|
| `incidents/` | Les neuf dossiers, un par incident |
| `strategie_tests.md` | Les trois niveaux de reproduction d'un échec d'intégration |
| `decisions/024-seuil-de-latence-par-environnement.md` | Régler un indicateur juste dont le contexte a changé |
| `reserves.md`, réserve 9 | Un contrôle qui repose sur une convention d'exécution |
