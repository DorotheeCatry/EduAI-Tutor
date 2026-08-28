# Comparaison de services d'IA — protocole

**Date de rédaction du protocole :** 28 août 2026
**Compétence visée :** C7 (épreuve E2) — comparaison de services d'intelligence artificielle
**Compétences concernées :** C6 (E2) — veille ; C10 (E3) — intégration du modèle ; C20 (E5)

---

> **Ce document est écrit et commité AVANT toute mesure.**
>
> Les critères, leur pondération et la grille de notation qui suivent sont fixés
> sans connaître les résultats. C'est la seule manière d'éviter le travers le
> plus courant de ce genre d'exercice : choisir après coup les critères qui
> désignent le modèle qu'on avait envie de retenir.
>
> Les sections « Mesures » et « Décision » sont vides à ce stade. L'historique
> Git en fait foi : le commit qui ajoute ce protocole ne contient aucun chiffre.

---

## 1. Question posée

Quel modèle affecter à chacun des quatre agents d'EduAI Tutor — Researcher,
Pedagogue, Coach, Watcher — sachant que leurs besoins diffèrent ?

Le routage actuel, acté en décision 001, a été décidé sur des considérations
générales de qualité et de latence, **sans mesure**. Ce document a pour objet de
le confirmer ou de le corriger sur des données.

## 2. Modèles comparés

| Identifiant | Fournisseur | Rôle dans la comparaison |
|---|---|---|
| `openai/gpt-oss-120b` | Groq | Modèle de qualité, routage actuel de Researcher et Pedagogue |
| `openai/gpt-oss-20b` | Groq | Modèle rapide, routage actuel de Coach et Watcher |
| `qwen/qwen3.6-27b` | Groq | Famille distincte — contrôle que le résultat ne tient pas au seul fournisseur d'origine |
| `qwen3:4b` | Ollama, local | Repli souverain, exécuté sur la machine |

Le quatrième n'est pas un concurrent des trois autres : il est **quatre à trente
fois plus petit**. Il est présent pour répondre à une question distincte — que
perd-on en repassant en local ? — et il serait malhonnête de le noter sur la
même échelle sans le dire.

## 3. Critères, fixés avant mesure

Six critères, dont quatre se mesurent et deux se constatent.

| # | Critère | Nature | Comment il est établi |
|---|---|---|---|
| 1 | **Latence** | mesuré | Médiane et neuvième décile des durées d'appel, relevés dans le journal de monitorage |
| 2 | **Jetons consommés** | mesuré | Jetons d'entrée et de sortie tels que **rapportés par le fournisseur**, jamais estimés depuis une longueur de texte |
| 3 | **Coût pour mille requêtes** | mesuré | Jetons moyens × tarif du fournisseur. Voir § 6 sur la fiabilité des tarifs |
| 4 | **Qualité pédagogique** | **noté à la main** | Grille du § 5, appliquée en aveugle par l'autrice du projet |
| 5 | **Souveraineté des données** | constaté | Le prompt sort-il de la machine ? Quelles conditions le fournisseur impose-t-il ? |
| 6 | **Disponibilité tarifaire** | constaté | Le modèle est-il accessible au projet, et à quelles limites de débit ? |

### Pourquoi pas de note globale pondérée

Aucune pondération n'est fixée, et c'est délibéré. Agréger six critères
hétérogènes en un score unique donnerait un classement d'apparence objective
dont le résultat dépendrait entièrement de coefficients choisis par le
rédacteur. La décision du § 8 nommera les critères qui l'ont emportée, agent par
agent, plutôt qu'un chiffre.

## 4. Protocole de mesure

**Dix prompts**, représentatifs des quatre agents du projet :

| Agent | Nombre | Nature |
|---|---|---|
| Pedagogue | 3 | Génération de cours, réexplication adaptée, reformulation pour débutant |
| Researcher | 2 | Synthèse à partir de fragments, réponse à une question technique |
| Coach | 3 | Retour sur du code fautif, génération d'exercice, correction d'erreur |
| Watcher | 2 | Classification d'une méprise, détection de type d'erreur |

**Quatre modèles × dix prompts × trois répétitions = 120 appels.**

Les trois répétitions ne servent pas à moyenner la qualité — un modèle ne change
pas d'avis — mais à **mesurer la dispersion de la latence**, comme cela a été
fait pour la conversion Spark. Une latence médiane sans dispersion ne dit pas si
le service est régulier ou erratique.

**Paramètres tenus constants** : même prompt au caractère près, même température,
même plafond de jetons de sortie, appels séquentiels et non concurrents. Deux
mesures ne se comparent que si elles ont subi les mêmes conditions.

**Instrumentation** : aucune n'est écrite pour ce benchmark. Le monitorage du
projet trace déjà agent, modèle, latence, jetons et coût estimé pour tout appel
passant par LangChain. Le benchmark fournit un protocole et une lecture des
traces, pas une sonde de plus.

## 5. Grille de notation de la qualité

**La qualité n'est pas mesurée automatiquement.** Un modèle juge d'autres
modèles avec des biais connus — préférence pour les réponses longues, pour son
propre style, pour la famille dont il est issu — et aucun de ces biais ne serait
défendable devant un jury. Les réponses sont donc notées à la main.

Le tableau des réponses est produit **côte à côte, sans indiquer quel modèle a
produit quoi** : la notation est faite en aveugle, puis les identités révélées.

Cinq axes, notés de 0 à 3 :

| Axe | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Exactitude technique** | erreurs factuelles | approximations | correct | correct et précis |
| **Adaptation au niveau** | hors sujet pour le niveau visé | inégale | adaptée | adaptée et explicitement graduée |
| **Utilité de l'exemple** | aucun exemple | exemple décoratif | exemple pertinent | exemple exécutable et commenté |
| **Concision** | délayé au point de nuire | verbeux | juste | dense sans être elliptique |
| **Respect du format demandé** | format ignoré | format approximatif | format respecté | format respecté et exploitable tel quel |

Note maximale : 15 par réponse.

**Les cinq axes ne sont pas pondérés entre eux** — même raison qu'au § 3.

## 6. Réserve sur les tarifs

Les tarifs de `apps/monitoring/tarifs.json` portent tous
`"a_verifier": true` : **ils n'ont pas été confrontés à la grille du
fournisseur.** Tout coût calculé à partir d'eux est un ordre de grandeur, et les
mesures le signalent explicitement.

Cette vérification demande un accès à la console Groq, qui n'est pas
programmatique. Elle relève de l'autrice du projet. Tant qu'elle n'est pas
faite, le critère 3 est établi **en jetons**, qui sont mesurés, et non en
monnaie, qui est déduite.

Un coût plausible et faux serait pire qu'un coût absent : c'est le motif que ce
projet documente depuis sept incidents.

## 7. Mesures

*À compléter après exécution du protocole. Aucune ligne ici au moment du commit
de ce document.*

## 8. Décision

*À compléter. Elle nommera, agent par agent, les critères qui l'ont emportée.*

---

## Annexe — état des services au moment de la rédaction

| Modèle | État | Détail |
|---|---|---|
| `openai/gpt-oss-120b` | disponible | vérifié sur `/v1/models` |
| `openai/gpt-oss-20b` | disponible | vérifié sur `/v1/models` |
| `qwen/qwen3.6-27b` | disponible | vérifié sur `/v1/models` |
| `qwen3:4b` | **indisponible** | service Ollama en échec de démarrage, voir ci-dessous |

**Le service Ollama est en boucle de redémarrage — 12 517 tentatives.** Sa
surcharge systemd le pointe vers `/media/apprenant/Stockage/ollama_models`,
répertoire situé sous un point de montage dont les droits sont `drwx------
apprenant:apprenant`. L'utilisateur système `ollama` ne peut pas le traverser :

```
Error: mkdir /media/apprenant/Stockage: permission denied
```

C'est la même cause qui faisait échouer les recherches RAG toute la semaine —
les fonctions d'embedding appellent Ollama sur le port 11434.

Le correctif demande des privilèges. Le plus simple est de rendre au service son
emplacement par défaut, où deux modèles sont déjà installés :

```bash
sudo rm /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama
ollama pull qwen3:4b        # seul qwen3.5 est présent aujourd'hui
```

Tant que ce point n'est pas traité, le quatrième modèle reste **non mesuré**, et
les tableaux du § 7 le diront plutôt que de laisser une case vide.
