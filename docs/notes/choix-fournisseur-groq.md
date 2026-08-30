# Note — le choix du fournisseur, et la limite du benchmark

Note personnelle de préparation à l'oral. Prépare la réponse à deux questions
qui viendront : « pourquoi Groq ? » et « pourquoi un seul fournisseur ? »

**Compétences concernées :** C7 (épreuve E2), C10 (épreuve E3)

---

## 1. Pourquoi Groq

Quatre raisons, dans l'ordre où elles ont pesé.

**Le palier gratuit est réel.** Accès à tous les modèles du catalogue sans carte
bancaire, limité par des quotas de débit et non par un système de crédits. Le
passage au palier développeur se fait par simple ajout d'un moyen de paiement,
sans minimum de dépense.

**La latence est la plus faible du marché.** C'est le critère décisif pour
l'agent Coach, dont le retour s'affiche dans l'éditeur : la latence y est perçue
directement par l'apprenant, contrairement à une génération de cours qu'on
attend.

**Le catalogue est composé de modèles ouverts.** Cela rend possible un repli
local sur des modèles de la même famille, ce qui n'aurait pas été le cas avec un
fournisseur servant exclusivement des modèles propriétaires. La continuité de
service et la souveraineté reposent sur ce point.

**L'API est compatible avec l'écosystème existant**, donc intégrable sans
réécriture de la couche d'agents.

---

## 2. Le paysage, pour situer le choix

| Fournisseur | Ce qu'il apporte | Pourquoi il n'a pas été retenu |
|---|---|---|
| **Groq** | Latence la plus faible, palier gratuit sans carte, modèles ouverts | *Retenu* |
| **Mistral** | Hébergement européen, cadre RGPD sans transfert hors UE, palier gratuit | Écarté par arbitrage de délai — c'est la limite du benchmark, voir §4 |
| **Together AI** | Catalogue de modèles ouverts très large | Latence supérieure, pas de palier gratuit durable |
| **Anthropic, OpenAI** | Meilleure qualité de raisonnement | Coût nettement supérieur, aucun palier gratuit, modèles fermés donc sans repli local possible |
| **OpenRouter** | Passerelle multi-fournisseurs, bascule automatique en cas de panne | Ajoute une couche d'intermédiation et un tiers supplémentaire au traitement des données |

---

## 3. La faiblesse connue de Groq, et comment elle a été traitée

Le catalogue change sans préavis. Le projet en a fait l'expérience : le modèle
`meta-llama/llama-4-scout-17b-16e-instruct`, écrit en dur dans trois fichiers
d'agents, a été retiré du catalogue et a renvoyé `404 model_not_found`,
provoquant une panne complète de la couche d'intelligence artificielle.

Trois contre-mesures en découlent, toutes documentées :

- Les identifiants de modèle sont externalisés en variables d'environnement,
  avec un routage par agent (décision 001).
- Un repli local par Ollama est disponible, activable par un drapeau explicite.
- Le monitorage distingue les codes de retour : un `404` signale un modèle
  retiré, un `429` un quota atteint. Ce sont deux incidents différents, qui
  appellent deux réponses différentes.

**À dire en soutenance :** la dépendance à un fournisseur unique est un risque
identifié, pas un angle mort. Il a été rencontré, diagnostiqué, et il est
désormais instrumenté.

---

## 4. La limite du benchmark — à énoncer avant qu'on la trouve

Le benchmark compare quatre modèles : trois servis par Groq, un exécuté
localement par Ollama. **Un seul fournisseur cloud est représenté.**

La conséquence est précise. Sur l'axe souveraineté, la comparaison n'oppose que
deux extrêmes : un service américain rapide, et une inférence locale mesurée à
environ 124 fois plus lente. **Il manque le point intermédiaire** — un
fournisseur européen, hébergeant en UE, avec des performances cloud.

Mistral aurait tenu ce rôle. Il n'a pas été intégré par arbitrage de délai :
le protocole du benchmark ayant été commité avant les mesures, ajouter un
fournisseur après coup aurait imposé de rejouer la campagne entière. Un tableau
incomplet aurait été moins défendable qu'un tableau au périmètre restreint mais
cohérent.

**Formulation pour le rapport E2 :**

> Le benchmark porte sur un seul fournisseur cloud. Un fournisseur européen tel
> que Mistral aurait apporté un troisième point sur l'axe souveraineté, entre le
> cloud extra-européen et l'inférence locale — la comparaison actuelle n'oppose
> que deux extrêmes. C'est la limite principale de cette campagne.

---

## 5. Les questions probables, et les réponses

**« Pourquoi Groq plutôt qu'OpenAI ou Anthropic ? »**
Palier gratuit sans carte, latence la plus faible du marché, et surtout des
modèles ouverts qui rendent le repli local possible sur la même famille. Avec un
fournisseur de modèles fermés, la continuité de service aurait été impossible à
assurer hors ligne.

**« Un seul fournisseur, n'est-ce pas risqué ? »**
Si, et le risque s'est réalisé pendant le projet. Les trois contre-mesures du §3
en découlent. Le risque résiduel est une indisponibilité du service, couverte
par le repli local — dégradé, mais fonctionnel.

**« Pourquoi ne pas avoir testé un fournisseur européen ? »**
C'est la limite principale du benchmark, et elle est écrite comme telle dans le
rapport. Arbitrage de délai : le protocole était commité avant les mesures,
l'ajouter après aurait imposé de rejouer la campagne complète.

**« Le repli local est-il vraiment utilisable ? »**
Il fonctionne, et il est deux ordres de grandeur plus lent : environ 93 secondes
de médiane contre 0,75 seconde. Il assure la continuité, pas l'équivalence.
C'est mesuré, pas supposé.

---

## 6. Ce qu'il ne faut pas dire

- « Groq est le meilleur. » Il est le plus rapide sur les modèles ouverts. Ce
  n'est pas la même affirmation, et la seconde est défendable.
- Présenter le repli Ollama comme équivalent. Le facteur mesuré est d'environ
  124 ; le dire fait la crédibilité de tout le reste.
- Justifier le choix par la seule gratuité. Elle a compté, mais elle ne
  répondrait pas à la question d'un déploiement réel.
