# Veille réglementaire — l'AI Act appliqué à un tuteur pédagogique

**Date de la session :** 28/08/2026
**Compétence visée :** C6 (épreuve E2) — veille technique et réglementaire
**Thématique :** classification d'EduAI Tutor au regard du règlement (UE) 2024/1689

---

## 1. Pourquoi cette thématique

EduAI Tutor s'adresse à des apprenants adultes d'un organisme de formation
professionnelle (décision 004). L'annexe III du règlement européen sur
l'intelligence artificielle classe « éducation et formation » parmi les huit
domaines à haut risque. La question de classification se pose donc directement,
et sa réponse conditionne des obligations documentaires lourdes.

La thématique porte bien sur une réglementation mobilisée par le projet, et non
sur un sujet d'actualité générale.

---

## 2. Qualification des sources

| Source | Auteur | Date | Fiabilité |
|---|---|---|---|
| AI Act Service Desk (Commission européenne) | Commission européenne | à jour | **Source primaire.** Portail officiel, calendrier de mise en œuvre |
| EUR-Lex — règlement (UE) 2024/1689 | Union européenne | 01/08/2024 | **Source primaire.** Texte du règlement |
| EUR-Lex — règlement (UE) 2026/1744 | Union européenne | 24/07/2026 | **Source primaire.** Omnibus numérique IA |
| Analyses de cabinets et blogs juridiques | variable | juillet–août 2026 | **Secondaire.** Utiles pour le calendrier consolidé, à recouper systématiquement — plusieurs se contredisent sur les dates |

**Constat de méthode, à retenir.** Les sources secondaires consultées se
contredisent : certaines annoncent l'application au 2 août 2026 comme
« maintenue », d'autres le report au 2 décembre 2027. L'écart s'explique par la
date de rédaction — l'omnibus a été adopté entre les deux. Sur un sujet dont le
calendrier bouge, la date de publication de la source est un critère de
fiabilité au même titre que l'identité de l'auteur.

C'est exactement le type de piège qu'une veille sert à éviter : une information
juste il y a six mois est fausse aujourd'hui.

---

## 3. Ce que dit le texte

### Architecture générale

Le règlement classe les systèmes selon quatre niveaux de risque :

| Niveau | Exemples | Obligations |
|---|---|---|
| Inacceptable | notation sociale, manipulation comportementale | interdits depuis février 2025 |
| **Haut risque** | huit domaines de l'annexe III, dont **éducation** | documentation, supervision humaine, traçabilité |
| **Risque limité** | **agents conversationnels, génération de contenu** | informer l'utilisateur qu'il interagit avec une IA |
| Minimal | filtres, suggestions | aucune obligation spécifique |

### Le calendrier, tel qu'il est au 28/08/2026

- **1er août 2024** — entrée en vigueur du règlement (UE) 2024/1689
- **2 février 2025** — interdictions applicables
- **2 août 2025** — obligations sur les modèles à usage général
- **27 juillet 2026** — entrée en vigueur du règlement (UE) 2026/1744, dit
  « omnibus numérique IA »
- **2 août 2026** — **obligations de transparence de l'article 50 applicables**,
  ainsi que le régime de sanctions et la surveillance du marché
- **2 décembre 2027** — obligations des systèmes à haut risque de l'annexe III,
  reportées de seize mois par l'omnibus

Sanctions : jusqu'à 35 M€ ou 7 % du chiffre d'affaires mondial pour les
pratiques interdites, 15 M€ ou 3 % pour les manquements haut risque, avec un
plafonnement au montant le plus bas pour les PME.

**Nuance importante.** Le raccourci « l'AI Act est reporté » est faux.
L'omnibus n'abroge rien et ne modifie pas l'annexe III : il déplace une échéance.
Une partie substantielle du règlement est applicable depuis le 2 août 2026,
sanctions comprises.

---

## 4. Classification d'EduAI Tutor — l'analyse

### L'annexe III vise des usages précis

Le domaine « éducation et formation » de l'annexe III couvre les systèmes
**déterminant l'accès à un établissement** et ceux réalisant **l'évaluation des
apprenants**. Ce n'est pas « tout système utilisé en contexte éducatif ».

### Ce que fait EduAI Tutor

- Il explique, reformule, génère des exercices et commente du code.
- Il ne conditionne l'accès à aucune formation.
- Il ne produit aucune note officielle ni décision opposable à l'apprenant.

Le système d'expérience et de progression est un mécanisme d'engagement interne,
sans conséquence sur le parcours de l'apprenant ni sur sa certification.

### Classification retenue

**Risque limité**, au titre de l'agent conversationnel. L'obligation principale
est celle de l'article 50 : informer l'utilisateur qu'il interagit avec un
système d'IA.

**Et cette obligation est applicable depuis le 2 août 2026.** Le report de
l'omnibus concerne le haut risque, pas la transparence.

### La limite de cette analyse — à énoncer, pas à masquer

La frontière est étroite. Si une évolution du produit conduisait les retours du
Coach à alimenter une décision de validation, ou si le score de progression
devenait un critère d'accès à un module obligatoire, la qualification
basculerait vers le haut risque. Trois obligations apparaîtraient alors :
documentation technique conforme, supervision humaine effective, et
enregistrement dans la base européenne.

La classification n'est donc pas un acquis mais un **critère de conception** :
elle contraint ce que le produit peut devenir.

---

## 5. Impact concret sur le projet

| Constat | Conséquence pour EduAI Tutor |
|---|---|
| Article 50 applicable depuis le 02/08/2026 | Une mention visible « réponses générées par une IA » doit figurer dans l'interface, au plus près des contenus produits. **À implémenter.** |
| L'annexe III vise l'évaluation et l'accès | Le projet doit expliciter, dans sa documentation, qu'il ne produit aucune décision opposable. La qualification en dépend. |
| Le RGPD s'applique en parallèle | L'AI Act ne remplace pas le RGPD : les deux s'appliquent simultanément dès qu'un système d'IA traite des données personnelles. Le travail déjà mené sur `eduai_data` reste entier. |
| Report au 02/12/2027 | Aucune obligation haut risque à court terme, mais l'échéance donne un horizon si le produit évolue. |
| Le calendrier a bougé en juillet 2026 | Sur un sujet mouvant, une veille sans récurrence produit une information périmée. Justifie le rythme hebdomadaire. |

**Action retenue** : ajouter la mention de transparence dans l'interface, et la
consigner dans une décision d'architecture.

---

## 6. À suivre

- Publication des normes harmonisées CEN-CENELEC, attendues avant décembre 2027.
  Leur retard pourrait entraîner un nouveau report ciblé.
- Premières décisions de l'AI Office après le 2 août 2026, qui préciseront la
  lecture des textes.
- Lignes directrices de la CNIL sur l'articulation RGPD / AI Act.

---

## 7. Ce que cette session m'a appris sur la méthode

Le sujet a changé cinq semaines avant cette session. Une veille menée en juin
aurait produit une conclusion fausse — non par erreur d'analyse, mais par
obsolescence.

Deux règles que j'en tire :

1. **Sur un sujet réglementaire en cours de déploiement, la date de publication
   d'une source prime sur sa notoriété.** Un cabinet réputé publiant en mai
   2026 est moins fiable qu'un article moins établi publié en août.
2. **Toujours remonter au texte.** Les analyses secondaires se contredisaient ;
   seul le règlement et le portail officiel permettaient de trancher.
