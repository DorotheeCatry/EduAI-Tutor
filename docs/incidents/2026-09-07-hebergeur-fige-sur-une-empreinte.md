# Incident 020 — Un crochet de déploiement qui redéployait toujours la même image

**Date :** 7 septembre 2026
**Composant :** configuration des services chez l'hébergeur (Railway)
**Gravité :** majeure — la livraison automatique n'a jamais rien livré
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C13 (E3) — déploiement ; C19 (E5) — chaîne de livraison

---

## 1. Déclenchement

**07/09, matin.** Constat à l'usage : l'application servie par l'hébergeur ne
correspond pas à l'état du dépôt. Des modifications fusionnées ne s'y voient
pas.

La première lecture était banale — trois commits attendaient sur une branche de
chantier jamais fusionnée dans `main`, or la chaîne ne livre que depuis `main`.
Cette lecture était vraie **et insuffisante** : la fusion faite et la chaîne
repassée au vert, l'hébergeur servait toujours la version précédente.

---

## 2. Périmètre impacté

| Élément | Impact |
|---|---|
| Application web déployée (C17) | Figée sur le commit `56e9b35` |
| Service IA déployé (C9) | Figé sur le même commit |
| Serveur d'embarquement | Figé sur le même commit |
| Chaîne d'intégration continue | **Aucun** — elle publiait bien les images |
| Données | Aucune perte : rien n'a été déployé, donc rien n'a été écrasé |

La chaîne n'était pas en cause. Elle publiait à chaque fusion trois images
correctes, étiquetées `:main` et par empreinte de commit. Ces images étaient
justes, complètes, et personne ne les tirait.

---

## 3. Diagnostic

Le relevé de la configuration réelle des services, par
`railway status --json`, donne pour chacun des trois :

```
"source": {"image": "ghcr.io/dorotheecatry/eduai-tutor/web:56e9b355fbc1f3c7…",
           "repo": null}
```

La source d'un service n'était **pas** l'étiquette mobile `:main` mais
**l'empreinte d'un commit**, écrite en dur. `repo: null` confirme par ailleurs
qu'aucun service n'est relié au dépôt GitHub.

Ce détail change tout le sens du crochet de redéploiement. Un crochet demande à
l'hébergeur de **redéployer sa source configurée**. Quand cette source est une
empreinte fixe, redéployer signifie *retirer exactement la même image*.
L'appel réussissait, l'hébergeur répondait, un déploiement avait bien lieu — et
il reposait la version déjà en place. La chaîne annonçait « déploiement
demandé », ce qui était vrai, et laissait croire à une mise à jour, ce qui ne
l'était pas.

**L'écart avec la documentation.** `docs/chaine_livraison.md` affirme, à sa
section 6.1 : « `:main` est ce que l'hébergeur déploie ; l'empreinte de commit
est ce qui permet de dire quelle version tourne et d'y revenir. » La
configuration réelle faisait l'inverse : elle déployait l'empreinte et
n'utilisait jamais `:main`. La documentation décrivait une intention, pas un
état. C'est le troisième incident du projet de ce motif — un dispositif décrit
comme actif et jamais vérifié sur le système en marche.

---

## 4. Correction

Les trois services applicatifs ont été repointés sur l'étiquette mobile, puis
redéployés depuis leur source :

```bash
railway service source connect --service embarquement \
  --image ghcr.io/dorotheecatry/eduai-tutor/embarquement:main
railway service source connect --service service-ai \
  --image ghcr.io/dorotheecatry/eduai-tutor/service-ia:main
railway service source connect --service web \
  --image ghcr.io/dorotheecatry/eduai-tutor/web:main

railway redeploy --service <service> --from-source --yes
```

`--from-source` est la clé : sans lui, `railway redeploy` rejoue le déploiement
existant, donc l'image existante. C'est le mécanisme même qui avait rendu le
crochet inopérant.

**Pourquoi l'étiquette mobile plutôt qu'une empreinte à jour.** Repointer sur
l'empreinte du nouveau commit aurait corrigé le symptôme du jour et laissé la
cause en place : chaque livraison aurait de nouveau exigé une bascule manuelle,
et le crochet serait resté décoratif. Le retour arrière, lui, ne se perd pas :
la chaîne publie toujours les deux étiquettes, et revenir à une version
consiste à repointer un service sur l'empreinte voulue.

---

## 5. Vérification

Contrôle sur le système en marche, pas sur la configuration :

| Service | Étiquette servie | Empreinte constatée | État |
|---|---|---|---|
| `web` | `web:main` | `sha256:142e3d74da2e…` | en marche |
| `service-ai` | `service-ia:main` | `sha256:24cfdc493c64…` | en marche |
| `embarquement` | `embarquement:main` | `sha256:f3873b810674…` | en marche |

L'empreinte `142e3d74…` est celle que le registre associe à `web:main` **et** à
`web:f6a0408daaf0…`, l'empreinte du commit fusionné : la version servie est
bien celle du dépôt.

Contrôles fonctionnels :

- `https://koda-tutor.up.railway.app/` répond `302` vers la page de connexion ;
- `/api/docs/` — l'API données (C5) — répond `200` ;
- `https://service-ai-production.up.railway.app/ai/sante` — l'API du service IA
  (C9) — répond `operationnel`, quatre agents disponibles.

---

## 6. Réserve subsistante

L'étape « Demander le redéploiement à l'hébergeur » **réussit aussi lorsque le
secret `RAILWAY_CROCHET_DEPLOIEMENT` est absent** : elle le signale dans son
journal et rend 0, par un choix délibéré de la chaîne. Son succès ne prouve
donc pas qu'un crochet est configuré, et le relevé du jour ne permet pas de
trancher.

Par ailleurs, un crochet Railway porte sur **un** service. Trois services
composent le déploiement.

Ces deux points ne se vérifient que sur la prochaine fusion dans `main` : si
les empreintes servies changent seules, le crochet fonctionne pour les services
concernés ; sinon, il faut soit créer les crochets manquants, soit continuer à
appeler `railway redeploy --from-source` à la main. Consigné en réserve tant
que la mesure n'a pas été faite.
