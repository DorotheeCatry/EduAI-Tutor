# Note — les motifs récurrents du projet, et ce qu'ils donnent à l'oral

Note personnelle. Rassemble ce qui structure le dossier au-delà des compétences
prises une à une : trois familles de défauts rencontrées à répétition, les
contre-mesures qui en découlent, et les formulations à ne pas perdre.

**Compétences concernées :** C20 et C21 (E5) au premier chef, mais la matière
sert aussi C12, C18, C19 et l'argumentation générale.

---

## 1. Pourquoi cette note existe

Le dossier documente plusieurs incidents. Pris isolément, chacun satisfait le
critère C21 — un incident réel, diagnostiqué, résolu, testé.

Mais ils ne sont pas indépendants. En les écrivant, trois familles se sont
dégagées, et c'est **la taxonomie qui vaut plus que les incidents séparés** :
elle montre qu'on est passé de « j'ai corrigé une panne » à « j'ai identifié un
mode de défaillance récurrent et je m'en protège ».

C'est ce qu'il faut raconter le 14, pas la liste des pannes.

---

## 2. Les trois familles

### Famille A — le rapport ne correspond pas à son effet

Le programme rend compte de son **intention**, pas de son **effet**.

| Occurrence | Ce qui était annoncé | Ce qui s'était produit |
|---|---|---|
| Extracteur S1 | « succès » | 0 enregistrement — filtre d'API inadapté |
| Chargeur PostgreSQL | « 6 836 documents chargés » | base vide — transaction jamais validée |
| Extraction stérile | fichier écrit | l'ancienne sortie écrasée par du vide |
| Tableau de bord | 85 %, 72 %, 90 % | valeurs calculées pour paraître vivantes |

**Le cas le plus instructif** est le dernier : `success_rate = min(95, 60 + (user.xp // 50))`,
commenté « Between 60% and 95% ». Ce n'était pas une maquette oubliée mais un
chiffre construit pour avoir l'air vivant. **Un zéro se remarque, un chiffre
vraisemblable non.**

Six foyers au total, découverts par vagues successives — le motif ne s'est
arrêté qu'à force de chercher.

**Contre-mesures :** contrainte de base refusant un succès à zéro enregistrement,
contrôle du statut transactionnel après écriture, compteurs jumeaux
« événements émis » et « lignes écrites » avec leur écart tracé en permanence,
tests qui échouent si une valeur inventée réapparaît.

**Question à se poser :** *de quoi cette valeur est-elle l'effet ?*

### Famille B — l'instrument enregistre autre chose que la question posée

Le dispositif fonctionne, et ce qu'il produit ne répond pas à ce qu'on croit.

| Occurrence | Le piège |
|---|---|
| `record_mistake(topic=session_id)` | Les erreurs étaient étiquetées par identifiant de session, jamais par notion. Impossible de dire sur quoi un apprenant échoue |
| `attempts_count` | Compte **toutes** les soumissions, y compris après la réussite. Ce n'est pas le nombre de tentatives avant réussite, malgré son nom |
| Empreinte du corpus | Portait sur les octets de `chroma.sqlite3`, que SQLite réécrit à la simple lecture. L'alarme se déclenchait toujours |
| Sonde `/ai/sante` | Annonçait la collection `eduai_knowledge_base` alors que la recherche interroge `eduai_corpus_documentaire` |

**Le cas d'`attempts_count` mérite d'être raconté** : le champ est correct, c'est
son **nom** qui induit en erreur. Nous l'avions supposé dans le mauvais sens.
D'où la troisième question de cette famille : *le nom de ce champ décrit-il ce
qu'il contient ?* Un nom est une promesse, et personne ne relit une promesse
tenue.

**Formulation à garder :** *une alarme qui se déclenche toujours est une alarme
qu'on cesse de lire.*

**Questions à se poser :** *qu'est-ce qui doit rester constant ?* et *le nom
décrit-il le contenu ?*

### Famille C — écrit, joignable, jamais appelé

Du code correct en apparence, et qu'aucun chemin n'atteint.

| Occurrence | Ce qui dormait |
|---|---|
| Soumission du quiz solo | Route, vue, orchestrateur, agent — tout écrit. Le gabarit affichait le score et redirigeait sans jamais poster. **Aucune session close depuis l'origine** |
| Sélecteur de langue | Réglage stocké en base, jamais lu |
| Catalogue de traduction | Généré, jamais appliqué |
| Sonde de monitorage | Posée par `ContextVar.set()`, donc invisible depuis toute requête HTTP |

**Le cas du quiz est le plus parlant** : en écrivant les tests, deux défauts
supplémentaires sont sortis — une comparaison de dates naïves et avec fuseau qui
aurait levé à chaque clôture, et une réponse non sérialisable. **Du code qui n'a
jamais tourné ne peut pas être correct ; il peut seulement en avoir l'air.**

**Contre-mesure :** poser la question *qui appelle ce code, et par quel chemin
l'apprenant y arrive ?* **avant** d'écrire le modèle. Elle a évité une cinquième
occurrence sur le rattachement exercice → compétence : une colonne nullable
aurait existé et serait restée vide partout, sans rien casser.

---

## 3. Un motif transversal — le contexte change, la vérification ne suit pas

Distinct des trois familles, et rencontré trois fois en quatre jours.

| Vérifié dans | Se comportait autrement dans |
|---|---|
| Un script Python | Une requête HTTP (sonde `ContextVar`) |
| `DEBUG=True` en local | `DEBUG=False` en intégration continue (redirection HTTPS) |
| Un poste encombré | Un clone vierge (`staticfiles/` résiduel) |

**Méthode retenue :** quand les variables d'environnement ne suffisent pas à
reproduire, rejouer depuis un clone frais. C'est ce qui a isolé le troisième
cas — l'écart n'était ni dans la configuration ni dans la base, mais dans le
contenu du répertoire.

---

## 4. Les décisions qui se défendent le mieux

### La validité pédagogique prime sur la serviabilité

**Le contexte transmis au tuteur pendant un quiz ne contient jamais la bonne
réponse.** Si le tuteur la connaît, il la donnera, et le quiz cesse de mesurer
quoi que ce soit.

Ce n'est ni un problème technique ni un problème de sécurité : c'est un problème
de **validité de l'instrument**. Un tuteur trop serviable détruit ce qu'il est
censé soutenir.

À citer si le jury demande comment sont gérés les risques d'un système d'IA en
éducation.

### Un rattachement faux est pire qu'un rattachement absent

La déduction automatique exercice → compétence par mots-clés a été écartée : un
exercice sur les listes rangé sous « manipuler les types de base » ferait
progresser une compétence non travaillée, **et personne ne le verrait**.
L'absence, elle, s'affiche.

### Faire attester une production par une reconnaissance

Les quiz ne font progresser aucun niveau. Les trois niveaux nomment des actes de
production — imiter, adapter, transposer ; un QCM mesure la reconnaissance, qui
n'est aucun des trois. Les quiz alimentent le bloc « à revoir » : ils révèlent
une lacune, ils ne certifient pas une acquisition.

### Le niveau 3 est déclaré non mesuré

Deux critères ont été examinés et écartés. Un seuil plus élevé mesurerait la
même preuve en plus grand nombre — « mettre un mot fort sur un compteur ». La
réussite au premier essai mesurerait l'autonomie **en la nommant
transposition**, puisque rien n'établit qu'un exercice engendré depuis le même
libellé constitue un contexte nouveau.

L'indicateur de premier essai est conservé et affiché, sans donner de niveau :
*la donnée est là, elle informe, elle ne prétend pas.*

### Une chaîne qui ne s'exécute que sur `main` ne protège pas `main`

Elle constate l'échec après la fusion. D'où la validation sur toutes les
branches, et la livraison sur `main` seulement.

### Elle ne lit pas un corpus, elle dépense

La justification du découpage DRF / FastAPI. Les deux API ne partagent ni
framework, ni processus, ni **modèle de menace** : l'une sert un corpus stocké,
l'autre déclenche un appel facturé à chaque requête.

---

## 5. Les seuils et les réglages — justifiés, jamais confortables

**Seuil de latence, deux valeurs.** 10 s en local, seuil d'expérience ; 75 s sur
l'hébergeur, seuil d'anomalie. Le second est dérivé de neuf mesures par deux
règles indépendantes qui convergent — moyenne + 2,5 σ = 76,4 et maximum + 30 % =
76,6 — puis arrondi **vers le bas**, un seuil ne devant pas être plus permissif
que ce que la mesure justifie.

Il continue de se déclencher sur des événements réels : premier appel après
déploiement, recherches concurrentes. **Un seuil sous lequel plus rien ne tombe
serait du confort.**

**Distinction à retenir :** l'indicateur de l'empreinte était *faux* — il se
corrige. Le seuil de latence était *juste* et son contexte a changé — il se
règle, et le réglage se justifie.

**Plafond de quota relevé de 5 à 15** avec l'arrivée du tuteur contextuel : même
logique, un changement d'usage, pas un assouplissement.

---

## 6. Les limites assumées — à énoncer avant qu'on les trouve

| Limite | Formulation |
|---|---|
| Niveau 2 | Atteste que **trois exercices ont été résolus**, pas que trois problèmes différents l'ont été. Le modèle peut produire des énoncés voisins |
| Empreinte du corpus | « L'empreinte en dernier » ne protège que d'une interruption à la fin. Un échec au début suivi d'une reprise produit un corpus incomplet **attesté complet** — par le dispositif même qui existe pour l'éviter |
| Repli local | Fonctionne, et **deux ordres de grandeur plus lent** : 93 s de médiane contre 0,75 s. Il assure la continuité, pas l'équivalence |
| Latence en production | Médiane 28 s, dispersion d'un facteur quatre. À contraintes égales, le poste est 11 à 32 fois plus rapide : le manque n'est pas le nombre de vCPU, c'est leur vitesse |
| Benchmark | Un seul fournisseur cloud. La comparaison n'oppose que deux extrêmes sur l'axe souveraineté |
| Corpus local | Un module rempli sur onze. Le pipeline ingère n'importe quel corpus sans modification |
| Démarche agile | Pas de rétrospective formalisée : les seules rétrospectives sont les dossiers d'incident, donc **déclenchées par l'échec**. Ce qui va mal assez pour casser est examiné ; ce qui va médiocrement ne l'est jamais |

**Formulation générale à retenir :** *un contrôle qui repose sur une convention
d'exécution n'est pas un contrôle, c'est une convention.*

---

## 7. Ce qu'il ne faut pas dire

- « J'ai eu quelques bugs. » Ce sont des modes de défaillance identifiés, avec
  des contre-mesures nommées.
- Présenter le repli local comme équivalent. Le facteur mesuré est de 124.
- « Le référentiel le demande » comme justification d'un choix technique. Vrai,
  et la pire réponse possible : elle présente une contrainte administrative là
  où il existe une raison technique.
- Annoncer un facteur d'accélération non mesuré. Le gain Spark est de l'ordre de
  384×, **avec la réserve que l'ancienne requête n'a jamais abouti** — c'est une
  extrapolation, pas une mesure.

---

## 8. Les trois phrases à ne pas perdre

> Le programme rend compte de son intention, pas de son effet.

> Du code qui n'a jamais tourné ne peut pas être correct ; il peut seulement en
> avoir l'air.

> Un contrôle qui repose sur une convention d'exécution n'est pas un contrôle,
> c'est une convention.
