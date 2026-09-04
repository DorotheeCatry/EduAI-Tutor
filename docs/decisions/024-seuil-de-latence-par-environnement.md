# 024 — Un seuil de latence par environnement, dérivé de la mesure

**Date :** 31 août 2026
**Compétence visée :** C20 (épreuve E5) — monitorage du service IA
**Compétences concernées :** C11 (E3) — indicateurs ; C13 (E3) ; C21 (E5)

## Contexte

Le monitorage lève une alerte au-delà de `MONITORAGE_SEUIL_LATENCE`, fixé à
**10 secondes**. Cette valeur a été choisie sur le poste de développement, où la
recherche documentaire répond en 3 secondes : le seuil y marque un écart réel au
fonctionnement normal.

Le déploiement a changé le contexte. Sans GPU et sur des cœurs mutualisés, la
même recherche demande **14 à 59 secondes chez l'hébergeur, médiane 28**
(réserve 7). Avec le seuil de 10 secondes, **chaque appel lève une alerte**.

Une alerte permanente n'est plus une alerte : on l'apprend, puis on la traite
comme le bruit de fond d'un système en bon état. C'est exactement ce que
l'incident 009 vient de documenter, à propos de l'empreinte du corpus — et il
ne s'agit pas de le répéter ici.

## La distinction qui fonde cette décision

**L'indicateur n'était pas faux. Le contexte a changé.**

C'est un point de fond, et il commande le traitement. Un indicateur faux se
corrige — c'était le cas de l'empreinte, qui mesurait les octets d'un fichier
que SQLite réécrit tout seul. Un indicateur juste dont le contexte a changé se
**règle**, et le réglage se justifie.

Confondre les deux mène à deux erreurs symétriques : garder un seuil devenu
inapplicable, ou le relever jusqu'à ce que l'alarme se taise. La seconde est la
plus tentante, et c'est celle qu'il fallait écarter.

## Options

1. Un seuil unique relevé pour tout le monde.
2. **Un seuil par environnement**, la valeur de production étant dérivée de la
   dispersion mesurée.
3. Supprimer l'alerte de latence en production.

## Option retenue

**La deuxième.** Dix secondes sur le poste, **soixante-quinze** chez
l'hébergeur, par la variable `MONITORAGE_SEUIL_LATENCE`.

## Raisons

**Le seuil unique relevé perdrait le seuil local.** Trois secondes de réponse
habituelle et un seuil à 75 laisseraient passer, sur le poste, une dégradation
d'un facteur vingt sans rien dire. Le seuil de développement a sa valeur
propre ; il n'a pas à payer les limites de l'hébergeur.

**Supprimer l'alerte reviendrait à renoncer à mesurer** ce qui est justement
devenu le point sensible du service.

**Les deux seuils ne répondent pas à la même question**, et c'est ce qui les
rend légitimement différents :

| Environnement | Nature du seuil | Ce qu'il détecte |
|---|---|---|
| Poste, 10 s | seuil d'**expérience** | Le service paraît bloqué à l'apprenant |
| Hébergeur, 75 s | seuil d'**anomalie** | Quelque chose a changé par rapport au régime mesuré |

## D'où vient le 75

**Pas du confort.** La valeur est dérivée de neuf mesures de `POST
/ai/recherche` en production, une requête à la fois, modèle chargé :

```
14,0  16,6  18,7  22,0  28,4  29,6  48,5  56,6  58,9   (secondes)
moyenne 32,6   écart-type 17,5   médiane 28,4   maximum 58,9
```

Deux règles indépendantes, qui convergent :

| Règle | Valeur |
|---|---|
| Moyenne + 2,5 écarts-types | **76,4 s** |
| Maximum observé + 30 % | **76,6 s** |

D'où **75 secondes**, arrondi vers le bas — un seuil qui ne doit pas être plus
permissif que ce que la mesure justifie.

## Ce qui reste au-dessus du seuil, et doit y rester

Le seuil n'a pas été choisi pour que plus rien ne se déclenche. Deux situations
réelles le franchissent, et ce sont précisément celles qu'on veut voir :

| Situation | Mesure | Pourquoi l'alerte est légitime |
|---|---|---|
| Premier appel après un déploiement | 90 à 92 s | Le modèle d'embarquement se charge. Une alerte par déploiement, qui marque un redémarrage |
| Deux recherches concurrentes | 102 et 128 s | Sérialisées par `OLLAMA_NUM_PARALLEL=1`, posé pour tenir sous le plafond mémoire. Une file d'attente qui s'allonge est une information |

## Conséquences

- `MONITORAGE_SEUIL_LATENCE=75` sur les services `web` et `service-ai` de
  l'hébergeur ; la valeur par défaut du code reste 10.
- Le commentaire de `apps/monitoring/alertes.py` porte les deux valeurs, leur
  nature respective et le calcul — la justification vit à côté du réglage, non
  dans un document qu'il faut penser à ouvrir.
- `.env.example` documente les deux valeurs.
- **Ce seuil est daté.** Il vaut pour cet hébergeur, ce palier de ressources et
  ce modèle d'embarquement. Un changement de l'un des trois demande de rejouer
  les neuf mesures, pas d'ajuster la valeur à vue.

---

## Mise à jour du 4 septembre 2026 — la mesure qui a démenti la dérivation

**Cette décision a déclenché sa propre condition de révision, et personne ne
l'a vu.**

Le paragraphe ci-dessus dit : *« Un changement de l'un des trois demande de
rejouer les neuf mesures, pas d'ajuster la valeur à vue. »* Le soir même du
31 août, `OLLAMA_KEEP_ALIVE=24h` a été posé sur le serveur d'embarquement —
**pour borner la mémoire, sans penser à la latence.** La mesure refaite dans la
foulée est sans ambiguïté (`docs/reserves.md`, « Correction du 31/08, au soir ») :

| Relevé | n | minimum | médiane | maximum |
|---|---|---|---|---|
| 31/08 matin — les neuf mesures qui fondent le 75 | 9 | 14,0 s | **28,4 s** | 58,9 s |
| 31/08 soir — après `OLLAMA_KEEP_ALIVE=24h` | 7 | 3,5 s | **4,6 s** | 14,5 s |

Rien n'a changé du modèle, du processeur, du corpus ni de l'hébergeur. Le
régime, lui, a changé d'un facteur six.

### Ce que cela fait au seuil

**Le seuil de 75 secondes n'est pas devenu faux : il est devenu inatteignable.**
Le maximum observé dans le nouveau régime est de 14,5 secondes, soit un
cinquième du seuil. Les deux situations que la section « ce qui reste au-dessus
du seuil » désignait comme légitimes — le premier appel après déploiement, deux
recherches concurrentes — étaient mesurées dans l'ancien régime et n'ont pas été
rejouées depuis.

Le journal de monitorage des six derniers jours ne porte, sur le poste, aucune
latence supérieure à 6,8 secondes.

**Un seuil qui ne peut plus se déclencher est le symétrique exact du problème
que cette décision traitait.** L'alerte permanente s'apprend et devient du bruit
de fond ; l'alerte impossible se tait et devient un contrôle décoratif. Les
deux donnent la même chose : un dispositif de surveillance auquel on ne demande
plus rien.

### Ce qui est décidé, et ce qui ne l'est pas

**Le seuil reste à 75 secondes pour l'instant, et ce n'est pas un choix : c'est
un constat d'insuffisance.** Le rebaisser au jugé — à 15 ou à 20 secondes — est
précisément l'erreur que cette décision écartait dans son option 1. La bonne
suite est de **rejouer les neuf mesures dans le régime actuel** et de réappliquer
les deux règles, ce qui n'a pas été fait faute de temps avant le rendu.

Ce que cette mise à jour acte, en attendant :

- la dérivation du 31/08 matin **ne vaut plus** pour le régime en vigueur ;
- la phrase « le seuil continue de se déclencher sur des événements réels » ne
  doit plus être avancée sans une mesure à l'appui ;
- la condition de révision inscrite dans cette décision **a fonctionné comme
  règle et échoué comme pratique** : elle était écrite, elle n'a pas été
  appliquée, parce que le changement qui la déclenchait avait été fait pour une
  autre raison.

### Ce que cet écart apprend

Le réglage qui a changé le régime a été posé **pour borner la mémoire**. Sa
conséquence sur la latence était un effet de bord bénéfique, donc silencieux :
rien ne casse quand un service devient six fois plus rapide, et rien ne
signale qu'un seuil vient de perdre sa justification.

La question à ajouter à `docs/motifs_incidents.md` :

> **Ce réglage change-t-il le régime d'une grandeur que je surveille ailleurs ?**

Une amélioration ne déclenche aucune alarme. C'est ce qui la rend plus difficile
à suivre qu'une panne.
