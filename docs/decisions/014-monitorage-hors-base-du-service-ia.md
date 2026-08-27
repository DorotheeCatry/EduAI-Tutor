# 014 — Monitorage du service IA : hors base, par effets mesurés

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C20 (E5), C21 (E5), C10 (E3)

## Contexte

Le référentiel exige un monitorage du service en production (C20). Le chantier
a été placé avant l'API FastAPI du service IA (C9), pour une raison qui ne tient
pas à la difficulté : **c'est le seul chantier dont la valeur dépend du temps
écoulé.** Une suite de tests écrite demain vaut autant qu'écrite ce soir ; un
monitorage lancé ce soir capture huit jours de traces avant la soutenance.

## Décision 1 — JSON Lines dans un fichier, jamais en base

Le monitorage doit survivre à la panne qu'il observe. Écrire les traces dans
PostgreSQL, c'est les perdre exactement quand PostgreSQL tombe — et c'est ce
mode de défaillance qu'on cherche à documenter.

Une ligne JSON par événement, et non un tableau JSON global : un tableau doit
être refermé pour être valide, donc un processus tué rendrait illisibles toutes
les traces antérieures à l'incident. C'est-à-dire celles qui comptent.

Ouverture en `O_APPEND` à chaque écriture : le noyau positionne et écrit en une
opération, ce qui empêche deux processus d'entrelacer leurs lignes.

Un fichier par jour, nommé par la date UTC. Une rotation par taille couperait
au milieu d'une journée et rendrait toute comparaison jour à jour laborieuse.

## Décision 2 — instrumenter par le point d'accroche global de LangChain

`register_configure_hook` de `langchain_core.tracers.context`, le mécanisme
qu'utilise LangSmith, plutôt qu'une modification de chaque site d'appel.

Le projet compte une vingtaine d'`invoke` répartis dans quatre agents et un
orchestrateur. Les reprendre un à un garantirait d'en oublier — et **un
monitorage qui couvre quatre appels sur cinq inspire une confiance qu'il ne
mérite pas.** Le point d'accroche couvre par construction les appels existants
et ceux qui seront écrits demain.

Deux rappels sont branchés, pas un : `on_llm_start` **et**
`on_chat_model_start`. `ChatGroq` et `ChatOllama` passent par le second. Ne
brancher que le premier aurait laissé la totalité des appels du projet hors du
monitorage, sans que rien ne le signale.

## Décision 3 — mesurer des effets, jamais des intentions

C'est la décision qui structure tout le module, et elle vient des quatre
incidents de ces deux jours, qui partagent le même motif : **un rapport de
succès qui ne correspond à rien.**

| Incident | Rapport | Réalité |
|---|---|---|
| S1, 26/08 | `succes` | 0 enregistrement |
| Chargeur, 27/08 | 6 836 documents chargés | base vide |
| Rapport S5, 27/08 | conversion 0,00 s | mesure écrasée par une exécution partielle |
| API `/sources/`, 27/08 | 235 documents | la source n'en fournissait plus que 234 |

Le monitorage en tire trois règles concrètes :

- il consigne **les fragments rendus** par une recherche, pas le `k` demandé ;
- il consigne **les jetons facturés** par le fournisseur, pas une estimation
  tirée d'une longueur de texte — le ratio caractères/jetons varie du simple au
  double selon la langue ;
- `verifier()` **rouvre le fichier** et compte les lignes analysables, au lieu
  de rapporter ce que le journal croit avoir écrit.

## Décision 4 — un coût inconnu vaut NUL, pas zéro

Un coût de zéro se confond avec un appel gratuit ; un coût nul se voit. Les
tarifs vivent dans `tarifs.json`, hors du code, et portent un drapeau
`a_verifier` que **chaque événement transporte**. Tant qu'il est vrai, le
rapport annonce une estimation explicitement non vérifiée plutôt qu'un chiffre
sec.

**Les tarifs actuels sont des ordres de grandeur, pas des relevés.** Ils doivent
être confrontés à la grille tarifaire de la console Groq, puis le drapeau passé
à `false` avec la date du relevé.

## Décision 5 — l'alerte s'écrit dans le journal, sans service externe

Un service de notification est un composant de plus qui peut tomber — et qui
tombe souvent en même temps que ce qu'il surveille : réseau, quota,
authentification. Une ligne dans le fichier ne dépend que du disque.

Deux seuils, tous deux réglables par variable d'environnement :

| Seuil | Défaut | Motif |
|---|---|---|
| Taux d'erreur par fenêtre | 20 pour cent sur 15 min, plancher de 5 appels | Sans plancher, le premier appel raté de la journée produirait un taux de 100 pour cent |
| Latence unitaire | 10 s | Au-delà, l'apprenant qui attend une correction considère le service comme bloqué |
| Silence entre alertes | 10 min, par nature | Sans lui, une panne du fournisseur noierait le journal sous des lignes identiques |

Le silence est appliqué **par nature** et non globalement : une alerte de
latence ne doit pas masquer une montée du taux d'erreur pendant dix minutes.

## Décision 6 — la sonde ne peut pas faire tomber le service

Toute exception de la sonde est rattrapée. Mais elle est **comptée** :
`echecs_sonde` et `echecs_ecriture` sont exposés. Avaler une erreur sans la
compter reproduirait exactement le motif que ce module existe pour détecter.

## Ce qui n'est pas consigné, et pourquoi

Ni le contenu des prompts, ni le texte des requêtes RAG — seulement leur
longueur. Un prompt peut contenir du code d'apprenant, une question peut être
identifiante. Le journal de monitorage n'a pas à en garder copie : c'est la même
règle de minimisation que celle appliquée au corpus (voir
`docs/rgpd_eduai_data.md` § 5).

## Décision 7 — Prometheus agrège, le fichier détaille

Les deux sorties coexistent parce qu'aucune ne remplace l'autre.

| | Prometheus | JSON Lines |
|---|---|---|
| Répond à | quel est le quantile de latence sur sept jours ? | quelle requête a échoué à 14 h 32, avec quel message ? |
| Ne sait pas | conserver le détail d'un appel | calculer un quantile sans tout relire |
| Dépend de | un service tiers | le seul système de fichiers |

Si Prometheus tombe, le détail continue de s'écrire. C'est précisément la panne
qu'on veut pouvoir observer.

**Cardinalité.** Les étiquettes Prometheus sont toutes bornées — agent, modèle,
fournisseur, issue, code de retour, classe d'exception. Prometheus crée une
série par combinaison ; y mettre un identifiant de requête ou un message
d'erreur rendrait la base inutilisable en quelques heures. Le détail variable
appartient au fichier, qui n'a pas cette contrainte. C'est l'une des raisons
d'avoir les deux, et pas seulement une commodité.

## Décision 8 — tout provisionné depuis des fichiers versionnés

Configuration de collecte, source de données et tableau de bord vivent dans
`monitoring/`, montés en lecture seule dans les conteneurs.

Un tableau de bord cliqué dans l'interface vit dans la base interne de Grafana,
donc dans un volume Docker. Il n'est pas dans le dépôt, ne se relit pas en
revue, ne se reproduit pas sur une autre machine, et **disparaît au premier
`down -v`**. C'est le même écart que des migrations exclues du dépôt, que le
projet a déjà rencontré.

`allowUiUpdates` est à `false` : une modification faite dans l'interface est
écrasée au rechargement. Sans cela, fichier et interface divergent sans que
personne ne sache lequel fait foi.

### Deux écarts rencontrés en montant la chaîne

**Le conteneur ne joignait pas le service.** `host.docker.internal` était résolu
vers 172.17.0.1, mais Django n'écoute que sur la boucle locale — délibérément.
Les deux issues étaient d'exposer Django sur `0.0.0.0`, ce qui défait la
précaution, ou de partager le réseau de l'hôte. La seconde a été retenue : les
deux conteneurs se lient explicitement à `127.0.0.1`, rien n'est joignable de
plus. Limite : `network_mode: host` est propre à Linux.

**La source de données recevait un identifiant engendré** — `PBFA97CFB590B2093`
— tandis que les huit panneaux du tableau de bord référençaient `prometheus`. Le
tableau de bord serait apparu correctement provisionné et n'aurait affiché
aucune donnée, avec pour seul indice un discret « datasource not found » dans
chaque panneau. L'identifiant est désormais fixé dans le fichier de
provisionnement. C'est exactement le motif des cinq incidents : une
configuration qui se déclare réussie sans produire d'effet.

## Indicateurs du tableau de bord

| Panneau | Ce qu'il montre |
|---|---|
| Taux d'erreur par agent | part des appels qui échouent, fenêtre de 5 min, seuil à 20 pour cent |
| Latence au 95e centile | ce que subissent les 5 pour cent les moins bien servis — la moyenne ne décrit l'expérience de personne |
| Volume d'appels | par agent et modèle ; un effondrement sans erreur signale un service sans trafic, pas en panne |
| Coût cumulé estimé | séparé selon que le tarif a été vérifié ou non |
| **Écart émis − écrits** | cœur de la démarche : toute valeur non nulle invalide toutes les autres mesures |
| Fragments rendus et recherches vides | le nombre rendu, jamais le k demandé |
| Disponibilité vue par le collecteur | la seule mesure qui ne dépende pas du service observé |

## Limites assumées

- **La fenêtre d'alerte est propre au processus.** Avec plusieurs processus
  serveur, chacun surveille sa part du trafic, et le seuil se déclenche plus
  tard qu'avec un compteur partagé. L'analyse hors ligne, elle, lit le fichier
  complet et voit tout.
- **Aucune purge automatique des journaux.** Un fichier par jour permet de
  purger par ancienneté ; la commande reste à écrire.
- **L'agent n'est nommé que sur les trois méthodes de l'orchestrateur** qui
  portent le décorateur `@sous_agent`. Les appels passant par un autre chemin
  sont tracés avec l'agent « inconnu » — modèle, latence et jetons restent
  mesurés, seule la répartition par agent manque.
- **Les compteurs Prometheus vivent dans un seul processus.** Le serveur de
  développement étant mono-processus, `/metrics` décrit aujourd'hui la totalité
  du trafic. Derrière plusieurs travailleurs, le collecteur en verrait une
  fraction. La réponse existe — agrégation par répertoire partagé, via
  `PROMETHEUS_MULTIPROC_DIR` — et sera mise en place quand le service passera
  derrière gunicorn. Elle ne l'est pas d'avance : un mécanisme d'agrégation non
  éprouvé donnerait des chiffres faux plutôt qu'absents. Les traces JSON Lines
  n'ont pas cette limite, tous les processus écrivant dans le même fichier.
- **`network_mode: host` est propre à Linux.** Le jour où le service Django sera
  lui-même conteneurisé, un réseau pont partagé sera la solution naturelle.

## Vérification

| Contrôle | Résultat |
|---|---|
| Appel Groq réel | tracé : 3,64 s, 86 jetons d'entrée, 50 de sortie, coût estimé |
| Modèle inexistant | tracé : `NotFoundError`, **code de retour 404** |
| Erreur RAG | tracée avec sa trace tronquée par le début, la cause conservée |
| Alerte de taux | ne se déclenche pas sous le plancher, se déclenche au plancher |
| Alerte de latence | déclenchée une fois |
| Silence | dix alertes redondantes absorbées, 2 lignes au total |
| `verifier()` | relit le fichier, compte les lignes réellement présentes |
| Rapport d'analyse | agrège agents, modèles, codes de retour, latences en médiane et neuvième décile |
