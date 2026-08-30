# 020 — Railway comme hébergeur, et ce qui n'est pas déployé

**Date :** 29 août 2026
**Compétence visée :** C13 (épreuve E3) — livraison et déploiement
**Compétences concernées :** C17 (E4), C19 (E5), C20 (E5)

## Contexte

Les épreuves E3 et E4 comportent une démonstration devant jury, et la formation
demande une application déployée. Une démonstration sur un service accessible
vaut mieux qu'un `localhost` : elle prouve que le passage en production a été
fait, pas seulement envisagé.

Le critère C19 n'exige pas formellement un déploiement — il cite la *pull
request* comme exemple d'étape de livraison. Mais C13 **et** C19 exigent une
documentation de la chaîne couvrant installation, configuration, test et
déclencheurs, et un déploiement réel est ce qui rend cette documentation
vérifiable plutôt que théorique.

## Options d'hébergement

1. **Railway**, plan payant, environ 5 $/mois.
2. Un hébergeur gratuit à mise en veille (Render free, Fly.io free).
3. Une machine virtuelle louée, configurée à la main.

## Option retenue

**Railway.**

## Raison

L'hébergeur gratuit à mise en veille est éliminé par la nature de
l'application : le premier appel après une veille recharge le processus, les
chaînes LangChain et le corpus vectoriel. Une démonstration devant jury qui
commence par trente secondes de page blanche coûte plus que 5 $.

La machine virtuelle donnerait le contrôle le plus complet et la facture la
plus prévisible, mais elle demande d'installer et de sécuriser un système, un
serveur web et un certificat — plusieurs jours de travail à six jours du rendu,
pour une compétence que le référentiel n'évalue pas.

Railway construit depuis un `Dockerfile`, fournit le certificat TLS, et pose un
proxy inverse devant l'application. Ce dernier point n'est pas un détail : il
donne son sens à `DJANGO_DERRIERE_PROXY`, prévu par la décision 008 et jamais
utilisé jusqu'ici.

## Périmètre déployé

| Composant | Déployé | Raison |
|---|---|---|
| Application Django (C17, C5) | oui | C'est l'objet de la démonstration |
| Service IA FastAPI (C9) | oui | Seconde API, évaluée séparément |
| PostgreSQL | oui | Les deux bases, `eduai_app` et `eduai_data` |
| Redis | **non** | Voir ci-dessous |
| Prometheus (C20) | **non** | Voir ci-dessous |
| Grafana (C20) | **non** | Voir ci-dessous |

### Pourquoi pas Redis

Le projet déclare `channels` et `channels-redis` dans ses dépendances, ce qui
laisse croire qu'une couche Redis est nécessaire. Elle ne l'est pas : les
réglages utilisent `InMemoryChannelLayer`, et le seul consommateur WebSocket du
projet — le quiz multijoueur — **n'a aucun client** dans les gabarits
(`docs/reserves.md`, réserve 1). Déployer Redis reviendrait à provisionner et
payer un service pour une fonction que personne n'appelle.

### Pourquoi pas Prometheus ni Grafana

Le jury doit voir l'application vivre, pas la pile d'observabilité. Celle-ci
reste montrée en local, où elle fonctionne et où les tableaux de bord sont
provisionnés depuis des fichiers versionnés.

**Ce que cela ne retire pas :** le monitorage applicatif par traces JSON Lines
continue de fonctionner sur le serveur — c'est lui la preuve de C20, et il
n'est pas conditionné à Prometheus. Ce qui reste local, c'est la **restitution
graphique**, pas la collecte.

**Ce que cela retire :** les métriques d'exploitation du serveur déployé ne
seront pas agrégées dans le tableau de bord. Le journal JSON Lines les contient
et reste lisible ; personne ne les regardera en temps réel.

## Conséquences

- Deux images à construire et à publier : `Dockerfile` à la racine pour
  l'application web, `service_ia/Dockerfile` pour l'API du service IA.
- Le corpus vectoriel est embarqué dans les images plutôt qu'indexé au
  démarrage — décision 021.
- **Aucune ouverture publique au-delà de la démonstration.** Tant que 82
  documents portent une licence non vérifiée, une ouverture large créerait des
  obligations non tenues. Elle est envisagée après la soutenance du
  14 septembre, comme décision distincte.
- Le plafond global de générations (décision 019) prend ici tout son sens : sur
  une adresse publique, chaque visiteur déclencherait des appels facturés.

---

## Complément du 30 août 2026 — ce que le déploiement réel a appris

**Le coût.** Railway offre un mois gratuit, qui couvre la période de
certification jusqu'à la soutenance du 14 septembre. L'arbitrage à 5 $/mois
reste celui qui a été fait, mais il ne se paie pas sur cette période.

**La mémoire du serveur d'embarquement.** Estimée à 2 Go avant déploiement,
**mesurée à 800 Mo** en fonctionnement continu. L'estimation était pessimiste
d'un facteur 2,5.

**Le coût réel n'est pas celui qu'on attendait.** Ce n'est pas la mémoire qui
pèse, c'est la latence : Railway n'a pas de GPU, et l'embarquement y est
environ trois fois plus lent qu'en local — 13,6 s pour 9 jetons, 52,2 s pour
343. La conséquence porte sur la démonstrabilité du RAG devant le jury, pas sur
le budget. Elle est ouverte en réserve 7, et sera tranchée sur une mesure de
bout en bout, pas sur une estimation.

C'est la deuxième fois dans ce projet qu'une estimation de coût se révèle
fausse dans un sens et juste dans l'autre : on avait provisionné pour la
ressource visible, et c'est le temps qui manque.
