# Conformité RGPD — base `eduai_data`

**Date :** 26/08/2026
**Compétence visée :** C4 (épreuve E1) — base de données conçue dans le respect
du RGPD
**Portée :** la base `eduai_data` et les cinq sources qui l'alimentent. La base
applicative `eduai_app` est traitée au paragraphe 8, pour les points qui la
lient à celle-ci.

---

## 1. Parties prenantes

| Rôle | Qui | Responsabilité |
|---|---|---|
| Responsable de traitement | Direction de l'organisme de formation | Détermine les finalités et les moyens |
| Personnes concernées | Apprenants adultes en formation professionnelle au développement | Titulaires des droits d'accès, de rectification et d'effacement |
| Destinataires internes | Formateurs | Prescrivent le corpus et reçoivent les signaux de progression |

Le service est **réservé aux majeurs**. Ce cadre écarte exactement deux
obligations : le consentement du titulaire de l'autorité parentale (art. 8) et
l'information rédigée en termes compréhensibles par un enfant (art. 12.1).
**Tout le reste du RGPD s'applique** — minimisation, conservation, accès,
effacement, sécurité. Voir `docs/decisions/005`.

---

## 2. Finalité

Constituer un corpus documentaire technique fiable et traçable, servant de base
de connaissance à un tuteur pédagogique augmenté (RAG), afin que ses réponses
s'appuient sur des sources identifiées et citables plutôt que sur la seule
mémoire du modèle de langage.

Finalité déterminée, explicite et légitime au sens de l'article 5.1.b. Aucun
usage secondaire n'est prévu : ni profilage, ni prospection, ni cession.

---

## 3. Base légale

**Pour `eduai_data` telle qu'elle existe aujourd'hui : aucune.** Les sources S1
à S3 ne contiennent aucune donnée à caractère personnel (§4). Le RGPD ne
s'applique donc pas à ce traitement, faute d'objet.

Cette réponse n'est pas une échappatoire : c'est le résultat recherché. La
conformité la plus solide est celle qui n'a rien à protéger.

**Pour S4, source à venir**, qui touchera des productions d'apprenants :

| Traitement | Base légale | Motif |
|---|---|---|
| Collecte des soumissions par la plateforme | Art. 6.1.b — exécution du contrat de formation | L'apprenant soumet du code pour être corrigé : c'est le service attendu |
| Réutilisation dans le corpus `eduai_data` | Art. 6.1.f — intérêt légitime | Finalité ultérieure, soumise au test de compatibilité de l'art. 6.4 |

Le test de compatibilité est satisfait par trois éléments : le lien étroit
entre les deux finalités (améliorer le tuteur qui corrige), le contexte
raisonnablement attendu par l'apprenant, et la pseudonymisation comme garantie
appropriée explicitement citée par l'article 6.4.e.

**Le consentement (art. 6.1.a) est écarté délibérément.** Dans une relation de
formation, le déséquilibre entre l'organisme et l'apprenant rend douteux le
caractère librement donné du consentement. S'en prévaloir fragiliserait le
traitement au lieu de le fonder.

---

## 4. Catégories de données

| Source | Type | Données à caractère personnel | Volume |
|---|---|---|---|
| S1 — Stack Overflow | Service web | **Aucune** | 1 313 documents |
| S2 — Documentation Python | Scraping | **Aucune** | 235 documents |
| S3 — Corpus local | Fichier | **Aucune** | 380 documents |
| S4 — à écrire | Base de données | Identifiant pseudonyme, sous conditions du §5 | — |
| S5 — à écrire | Big data | **Aucune** prévue | — |

Le schéma ne comporte **aucune entité « personne »**. Les treize tables de
`eduai_data` décrivent des documents, des sources, des licences, des mots-clés
et des exécutions d'extraction — jamais des individus.

---

## 5. Minimisation appliquée

L'article 5.1.c impose des données « adéquates, pertinentes et limitées ». Trois
applications concrètes, vérifiables dans le code.

**S1 — les auteurs ne sont pas collectés.** L'API Stack Exchange expose pour
chaque question un objet `owner` contenant `display_name`, `user_id`,
`profile_image` et `link` : un pseudonyme, un identifiant persistant et une
photographie. L'extracteur ne demande aucun de ces champs. Vérifié sur les
1 928 enregistrements extraits : aucune clé de métadonnée ne désigne une
personne.

L'attribution exigée par la licence CC BY-SA est assurée par `url_source`, qui
pointe vers la question d'origine où Stack Overflow crédite lui-même son
auteur. **L'obligation de licence est honorée sans détenir la donnée.**

**S4 — pas d'identifiant direct.** Aucun `user_id`, aucune adresse IP, aucune
adresse électronique n'entrera dans `eduai_data`. Un identifiant pseudonyme
n'est retenu **que si** le lien entre plusieurs soumissions d'un même apprenant
est nécessaire au traitement — et dans ce seul cas.

La contrainte pèse sur l'extracteur, qui devra écarter ces champs à la source
plutôt que les charger puis les purger. Une donnée qu'on ne collecte pas n'a
besoin ni de durée de conservation, ni de procédure d'effacement.

**Précision sur la pseudonymisation.** Un identifiant pseudonyme **reste une
donnée à caractère personnel** au sens du considérant 26, puisque la table de
correspondance existe dans `eduai_app`. Il réduit l'exposition, il ne fait pas
sortir du champ du règlement. Le présenter comme une anonymisation serait une
erreur — et c'est précisément la question qu'un jury pose.

---

## 6. Durées de conservation

| Source | Durée | Motif |
|---|---|---|
| S1 — Stack Overflow | 365 jours | Fraîcheur : une réponse de plus d'un an peut décrire une API obsolète |
| S2 — Documentation Python | 365 jours | Même motif |
| S3 — Corpus local | Sans terme (`NULL`) | Droits détenus par l'autrice du projet |
| S4 | **90 jours** | Durée courte imposée par la présence d'un pseudonyme |
| S5 | 365 jours | Alignée sur les sources externes |

Le motif des 365 jours n'est **pas juridique** : CC BY-SA 4.0 et la licence PSF
sont irrévocables, le retrait d'une source ne retire pas le droit d'usage
acquis. C'est un critère de qualité pédagogique.

La durée est portée par la colonne `source.duree_conservation_jours`, où `NULL`
signifie « sans terme » et non « non renseigné ». Elle est donc dans la base,
pas seulement dans ce document.

---

## 7. Procédure d'effacement

**Purge par ancienneté.** Les documents dont la date d'extraction dépasse la
durée de conservation de leur source sont supprimés :

```sql
DELETE FROM document d
USING source s
WHERE d.code_source = s.code_source
  AND s.duree_conservation_jours IS NOT NULL
  AND d.extrait_le < now() - (s.duree_conservation_jours || ' days')::interval;
```

Les suppressions se propagent par `ON DELETE CASCADE` vers la table fille du
document, vers ses collectes et vers ses mots-clés associés. Les lignes
d'`extraction` subsistent : elles ne contiennent aucune donnée personnelle et
constituent la trace de ce qui a été fait.

**Demande d'effacement d'une personne (art. 17).** Applicable à S4 seule.
L'apprenant s'adresse à l'organisme, qui retrouve son identifiant pseudonyme
dans `eduai_app` puis supprime les documents qui le portent. L'opération est
possible **parce que** la correspondance existe — ce qui confirme le §5 : ces
données restent personnelles.

**Preuve de l'effacement.** La vue `controle_partition` et le dénombrement par
source permettent de constater l'état avant et après. Un effacement qu'on ne
peut pas prouver n'est pas un effacement.

---

## 8. Mesures de sécurité

### En place, vérifiable

| Mesure | Preuve |
|---|---|
| Aucun secret dans le code versionné | Clé secrète Django sortie de `settings.py` et régénérée, commit `30d4e94` |
| Secrets en variables d'environnement seules | `.env` et toutes ses variantes exclues du dépôt |
| Données personnelles d'exécution hors dépôt | `media/` exclu — avatars téléversés |
| Mot de passe de base obligatoire | Le conteneur refuse de démarrer sans `POSTGRES_PASSWORD` |
| Base non exposée au réseau | Port publié sur `127.0.0.1` seulement, commit `2d8ffdb` |
| Protections applicatives Django | Middlewares CSRF, clickjacking, sessions et authentification actifs |
| Intégrité des données | 53 contraintes nommées, dont les règles de licence et d'attribution vérifiées par le moteur |

### Écarts identifiés, non encore corrigés

| Écart | Portée | Traitement prévu |
|---|---|---|
| `DEBUG = True` codé en dur dans `settings.py` | Une erreur expose la trace complète, variables d'environnement comprises | Étape 4, lecture depuis l'environnement |
| Aucun réglage `SECURE_*` — HSTS, cookies sécurisés, redirection HTTPS | Exposition en clair si le service sort du poste | Étape 4 |
| `ALLOWED_HOSTS` autorise `.ngrok-free.app` | L'application a été exposée publiquement par tunnel | À retirer dès que la démonstration ne l'exige plus |
| Aucune route de suppression de compte | Droit d'effacement non exerçable par l'apprenant | Étape 4 |
| `ExerciseSubmission.ip_address` collectée | Donnée personnelle sans finalité établie | **Suppression du champ** à l'étape 4, et non conservation sous une durée |

Sur ce dernier point : une donnée sans finalité ne se conserve pas. Lui
attribuer une durée reviendrait à légitimer une collecte qu'aucun besoin ne
justifie. Voir `docs/decisions/005`.

---

## 9. Registre des traitements

L'exemption de l'article 30.5 pour les organismes de moins de 250 salariés ne
s'applique pas : le traitement n'est pas occasionnel. Le présent document
fournit les éléments qu'un registre exige — finalité, catégories de personnes
et de données, destinataires, durées, mesures de sécurité — mais il ne le
remplace pas. Sa tenue relève du responsable de traitement.
