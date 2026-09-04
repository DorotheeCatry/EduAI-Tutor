# Incident 020 — Un modèle retiré du catalogue, et deux pannes qui attendaient derrière

**Date de l'incident :** 25 août 2026
**Date de cette fiche :** 4 septembre 2026
**Composants :** `apps/agents/agent_researcher.py`, `agent_pedagogue.py`, `agent_coach.py`, puis `apps/agents/tools/model_config.py`
**Gravité :** haute — toute la couche d'intelligence artificielle hors service
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C10 (E3) — intégration du modèle ; C20 (E5) — monitorage ; C7 (E2)

> **Pourquoi cette fiche est datée du 4 septembre.** L'incident du 25 août a été
> consigné le jour même, mais **comme décision d'architecture** (décision 001),
> parce que sa résolution portait un choix de conception. Ce format documente la
> résolution ; il ne documente ni le déclenchement, ni le périmètre, ni les
> tests. Le registre d'incidents ne portait donc aucune fiche pour l'incident
> que le rapport E5 présente comme son cas principal. Cette fiche comble ce
> manque, à partir de la décision 001, du code et des messages d'erreur
> conservés. **Elle n'est pas antidatée** : ce qu'elle rapporte est reconstruit,
> et le dire vaut mieux que de laisser croire à une rédaction du jour même.

---

## 1. Déclenchement

**25/08, à la reprise du projet après treize mois d'interruption.** Toute
génération échoue, sans exception : le cours ne se produit pas, l'exercice non
plus, le quiz reste vide, le tuteur ne répond pas.

L'application, elle, se comporte normalement. Elle sert ses pages, la connexion
fonctionne, les cours déjà produits se lisent. **Rien dans l'interface ne
distingue une panne de la couche IA d'une lenteur** — c'est ce qui a d'abord
fait chercher du côté du réseau.

Le premier message utile vient du client du fournisseur :

```
404 model_not_found : meta-llama/llama-4-scout-17b-16e-instruct
```

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Génération de cours, d'exercices, de quiz | **hors service** |
| Tuteur conversationnel | **hors service** |
| Recherche documentaire (RAG) | **hors service** — pour une autre raison, découverte plus tard |
| Connexion, navigation, lecture des cours existants | aucun |
| Données | aucune perte |

Le périmètre est donc **toute la couche qui parle au modèle**, et elle seule.

---

## 3. Diagnostic

### 3.1 La cause visible : un modèle qui n'existe plus

`meta-llama/llama-4-scout-17b-16e-instruct` a été retiré du catalogue Groq sans
préavis. Le fournisseur n'a aucune obligation de maintenir un modèle
disponible, et treize mois s'étaient écoulés depuis la dernière exécution.

Le point qui a rendu la correction coûteuse n'est pas le retrait : c'est que
l'identifiant était **écrit en dur dans trois fichiers différents**, sans
constante ni configuration. Réparer supposait de savoir où chercher.

### 3.2 Ce que la correction de la première cause a révélé

Identifiant remplacé par un modèle valide du catalogue. La panne persiste, avec
un autre code :

```
403 model_permission_blocked_project
```

**Aucun modèle n'était autorisé au niveau du projet** dans la console du
fournisseur. La clé d'API était pourtant valide — le listing des modèles
répondait 200. C'est ce qui rend cette cause particulièrement retorse : tous les
contrôles d'authentification passent, et seul l'appel réel échoue.

Cette seconde cause était **invisible tant que la première existait** : on ne
voit pas un 403 sur un modèle qui répond déjà 404.

### 3.3 Ce que la correction de la deuxième a révélé

Trois modèles autorisés dans la console. La génération repart. Mais la recherche
documentaire ne rend rien, **en silence** : Ollama n'était pas installé sur la
machine, donc aucun calcul d'embarquement n'aboutissait.

Cette troisième cause était masquée par les deux premières : le repli local
n'était jamais atteint, puisque le chemin distant échouait avant.

### 3.4 Cause racine

Trois causes indépendantes, empilées, chacune masquant la suivante :

| Cause | Code | Ce qui la masquait |
|---|---|---|
| Modèle retiré du catalogue | 404 | Rien — première erreur visible |
| Aucun modèle autorisé au niveau du projet | 403 | La première : un 404 précède un 403 |
| Service d'embarquement local absent | échec muet | Les deux premières : le repli n'était jamais atteint |

**La cause racine n'est aucune des trois.** C'est la **dépendance rigide à un
identifiant nommé en dur**, qui transforme une décision du fournisseur en panne
totale d'un système, et qui rend la réparation manuelle.

### 3.5 Ce qui rend cet incident particulier

Les trois causes se sont révélées **une par une, et seulement dans cet ordre**.
Aucune méthode de diagnostic ne pouvait les voir simultanément : chaque
correction était nécessaire pour rendre la suivante observable.

C'est le motif qu'on retrouvera ensuite dans l'installation d'Ollama, où
corriger les permissions du point de montage a révélé des modèles restés à
l'ancien emplacement. **Un incident n'est pas clos quand sa cause identifiée est
corrigée, mais quand la fonction est vérifiée de bout en bout.**

---

## 4. Résolution

Remplacer l'identifiant aurait réparé la panne du jour. Cela n'aurait rien
changé au prochain retrait de modèle. La résolution a donc porté sur la cause
racine, et elle est consignée en **décision 001** avec ses options écartées.

**Un module unique**, `apps/agents/tools/model_config.py`, centralise le
catalogue et expose `get_model_for(agent)`. L'ordre de résolution est explicite :

1. variable d'environnement propre à l'agent (`GROQ_MODEL_COACH`…) ;
2. variable d'environnement globale (`GROQ_MODEL`) ;
3. routage par défaut du module.

Trois propriétés en découlent, et ce sont elles qui comptent :

- **un modèle se change sans toucher au code**, donc sans redéploiement ;
- **un seul agent peut basculer** — l'ordre de résolution le permet, ce qui sert
  aussi bien à une démonstration qu'à un contournement d'urgence ;
- **un agent inconnu lève une `ValueError`** plutôt que de retomber en silence
  sur un modèle par défaut. Un repli silencieux donnerait une réponse plausible
  produite par le mauvais modèle, ce que rien ne signalerait.

Le routage par défaut distingue les besoins — modèle de qualité pour Researcher
et Pedagogue, modèle rapide pour Coach et Watcher. Ce partage, décidé ici sur
des considérations générales, a été **confirmé par la mesure** cinq jours plus
tard (décision 016 et benchmark C7).

Un drapeau `USE_LOCAL_LLM` bascule vers Ollama : deux ordres de grandeur plus
lent, mais fonctionnel.

---

## 5. Tests en succès

| Contrôle | Résultat |
|---|---|
| Appel de vérification sur chacun des trois modèles autorisés | Les trois répondent |
| Génération d'un cours de bout en bout depuis l'interface | Cours produit, les quatre agents passés |
| Bascule vers le modèle local par le drapeau | Recherche fonctionnelle, latence de 92,8 s de médiane (benchmark C7) |
| Simulation d'un modèle inexistant | 404 tracé dans le journal avec son code, **distinct du 429 de quota** |

**Contrôles de non-régression automatisés :** `tests/test_routage_modeles.py`,
24 cas. Ils gardent les trois niveaux de l'ordre de résolution, l'échec
explicite sur agent inconnu, le caractère asymétrique du drapeau de repli — une
valeur douteuse ne bascule pas le service — et surtout :

> **`test_aucun_identifiant_de_modele_n_est_ecrit_en_dur_dans_les_agents`**

C'est celui qui garde la résolution elle-même. Externaliser la configuration ne
sert à rien si un agent réécrit un jour un identifiant dans son propre fichier :
personne ne le remarquerait avant le prochain retrait de modèle, c'est-à-dire
avant la prochaine panne totale.

**Ces tests ont été écrits le 4 septembre**, en même temps que cette fiche. Le
rapport E5 les annonçait comme existants ; ils ne l'étaient pas. La vérification
du routage reposait jusque-là sur des essais manuels.

---

## 6. Ce que cet incident ajoute

**Une dépendance externe n'est pas une constante.** Un modèle, une version
d'image, un point d'accès d'API : ce sont des valeurs qu'un tiers peut retirer
sans préavis et sans vous prévenir. Elles n'ont pas leur place dans du code.

**Un empilement de causes se diagnostique dans un seul ordre.** Il n'y a pas de
méthode pour les voir toutes d'un coup ; il y a une discipline, qui est de ne
jamais déclarer clos avant d'avoir exercé la fonction entière, et non seulement
le point qu'on venait de corriger.

**Le monitorage est né de cet incident.** Une panne totale de la couche IA n'a
produit, sur le moment, aucun signal exploitable — il a fallu lire les messages
d'erreur un par un. C'est ce qui a conduit à la sonde unique, au journal JSON
Lines et à la distinction des codes de retour : **un 404 est un modèle retiré,
un 429 est un quota atteint, et ce ne sont pas le même incident.**

**Famille :** aucune des trois du registre. Cet incident relève de la
**dépendance externe**, comme la conversion Spark relève du passage à l'échelle.
Le tiret de la colonne « famille » n'est pas une lacune de classement : trois
familles décrivent des erreurs de conception, et celle-ci n'en est pas une.

---

## 7. Reste à faire

- **La décision 001 porte une justification périmée** : elle motive le repli
  local, entre autres, par le traitement de données d'apprenants « potentiellement
  mineurs ». Les décisions 004 et 005 ont établi depuis que le public est
  exclusivement adulte, et `model_config.py` porte déjà la motivation corrigée —
  ces prompts n'ont pas à sortir de la machine, indépendamment de l'âge. La
  décision n'est pas réécrite, conformément à l'usage du projet ; l'écart est
  signalé ici.
- Aucun contrôle ne vérifie qu'un modèle du catalogue est **encore disponible**
  chez le fournisseur. La panne se constaterait au premier appel, comme le
  25 août. Un appel de vérification au démarrage du service IA serait le
  correctif ; il n'est pas écrit.
