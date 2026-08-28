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
| S4 — `eduai_app` | Base de données | **Aucune** — voir §5 | variable selon l'activité |
| S5 — Dump Stack Exchange | Big data | **Aucune** | 4 948 documents |

Le schéma ne comporte **aucune entité « personne »**. Les treize tables de
`eduai_data` décrivent des documents, des sources, des licences, des mots-clés
et des exécutions d'extraction — jamais des individus.

---

## 5. Minimisation appliquée

L'article 5.1.c impose des données « adéquates, pertinentes et limitées ».
Quatre applications concrètes, vérifiables dans le code et chiffrées.

**S1 — les auteurs ne sont pas collectés.** L'API Stack Exchange expose pour
chaque question un objet `owner` contenant `display_name`, `user_id`,
`profile_image` et `link` : un pseudonyme, un identifiant persistant et une
photographie. L'extracteur ne demande aucun de ces champs. Vérifié sur les
1 928 enregistrements extraits : aucune clé de métadonnée ne désigne une
personne.

L'attribution exigée par la licence CC BY-SA est assurée par `url_source`, qui
pointe vers la question d'origine où Stack Overflow crédite lui-même son
auteur. **L'obligation de licence est honorée sans détenir la donnée.**

**S5 — les identifiants d'auteur ne sont pas projetés.** Le dump Stack
Exchange comprend un fichier `Users.xml` qui ne contient que des données
personnelles — nom d'affichage, site web, localisation déclarée, biographie.
Il n'est jamais ouvert : un garde-fou dans l'extracteur refuse le traitement,
plutôt qu'une consigne qui ne vivrait que dans ce document.

L'écarter ne suffit pourtant pas. `Posts.xml`, le seul fichier lu, porte
lui-même des données personnelles. Comptages relevés sur le dump du
07/04/2024, vérifiables par `grep -c` sur le fichier :

| Attribut | Occurrences | Nature |
|---|---|---|
| `OwnerUserId` | 78 448 | identifiant persistant de personne |
| `LastEditorUserId` | 28 401 | identifiant persistant de personne |
| `OwnerDisplayName` | 635 | nom d'affichage en clair |
| `LastEditorDisplayName` | 184 | nom d'affichage en clair |

La projection de `s5_conversion_parquet.spark.sql` n'extrait aucun de ces
quatre attributs. **Sans elle, 819 noms d'affichage en clair entreraient dans
le corpus**, en plus de 106 849 identifiants persistants.

`OwnerUserId` est un entier, non un nom — il n'en reste pas moins une donnée à
caractère personnel. Il identifie durablement une personne, et il suffit de
l'accoler à l'URL du profil public Stack Exchange pour retrouver son nom
d'affichage. Le considérant 26 vise exactement ce cas : la réidentification par
des moyens raisonnablement susceptibles d'être utilisés. C'est le même
raisonnement que celui appliqué plus bas à la pseudonymisation de S4.

Comme pour S1, l'attribution exigée par CC BY-SA passe par l'URL du post, où
Stack Exchange crédite lui-même son auteur. Voir `docs/decisions/009`.

**S4 — aucun identifiant, pas même pseudonyme.** La règle posée ici était
qu'un identifiant pseudonyme ne serait retenu **que si** le lien entre
plusieurs soumissions d'un même apprenant était nécessaire au traitement. La
condition a été examinée à l'écriture de l'extracteur, et tranchée : **elle
n'est pas remplie**.

Le document le plus utile que cette source produit est une paire « voici du
code qui échoue, voici le code du même apprenant qui a fonctionné ensuite ».
Le constituer exige bien de rapprocher deux soumissions d'une même personne —
donc de disposer de `user_id`. Mais ce besoin porte sur la **collecte**, pas
sur le **résultat** : une fois la paire formée, le document porte une erreur et
sa correction, et rien de ce qui suit n'a besoin de savoir qui l'a écrite.

`user_id` sert donc à la jointure latérale de
`s4_soumissions_corrigees.sql` et n'apparaît dans aucune projection. Ni
`user_id`, ni `ip_address`, ni adresse électronique, ni nom : la table
`users_kodauser` n'est même pas jointe.

**Deux garanties tenues par le moteur plutôt que par l'intention.** La
connexion à `eduai_app` est ouverte en lecture seule — le pipeline ne peut pas
écrire dans la base qui porte les comptes. Et un garde-fou inspecte les
colonnes retournées avant de lire la moindre ligne : ajouter `user_id`, un
courriel ou une adresse IP à un fichier `.sql` interrompt l'extraction au lieu
de remplir discrètement le corpus. Vérifié sur cinq projections d'essai.

**Précision sur la pseudonymisation.** Si un identifiant pseudonyme avait été
retenu, il serait **resté une donnée à caractère personnel** au sens du
considérant 26 : la table de correspondance existe dans `eduai_app`, et la
réidentification y serait immédiate. Un pseudonyme réduit l'exposition, il ne
fait pas sortir du champ du règlement. Le présenter comme une anonymisation
serait une erreur — et c'est précisément la question qu'un jury pose. Ce
raisonnement est repris tel quel en `docs/decisions/009` à propos de
`OwnerUserId`, entier d'apparence anodine et pourtant identifiant persistant.

---

## 6. Durées de conservation

| Source | Durée | Motif |
|---|---|---|
| S1 — Stack Overflow | 365 jours | Fraîcheur : une réponse de plus d'un an peut décrire une API obsolète |
| S2 — Documentation Python | 365 jours | Même motif |
| S3 — Corpus local | Sans terme (`NULL`) | Droits détenus par l'autrice du projet |
| S4 | **90 jours** | Durée courte imposée par la présence d'un pseudonyme |
| S5 — Dump Stack Exchange | 365 jours | Fraîcheur, comme S1 : le dump est une photographie datée, une réponse ancienne peut décrire une API disparue |

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

**Demande d'effacement d'une personne (art. 17).** Elle s'exerce sur
`eduai_app`, et sur elle seule.

`eduai_data` ne contient aucun identifiant de personne, pas même pseudonyme
(§5). Une demande d'effacement y est donc **sans objet** : il n'y a rien à y
retrouver, et rien qui puisse être rattaché à un demandeur. Ce n'est pas une
échappatoire mais la conséquence directe de la minimisation — c'est
précisément l'effet recherché, énoncé au §3 : la conformité la plus solide est
celle qui n'a rien à protéger.

La contrepartie est assumée : les documents déjà versés au corpus ne peuvent
pas être retirés individuellement à la demande d'un apprenant, faute de
pouvoir les identifier. Ils disparaissent par la purge d'ancienneté, la
rétention de S4 étant fixée à 90 jours — le délai le plus court du corpus, et
c'est la raison de ce choix.

L'organisme reste tenu d'effacer, dans `eduai_app`, le compte de l'apprenant et
toutes ses productions. C'est là que vivent les données personnelles, et la
route de suppression de compte manquante y est un écart ouvert (§8).

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
| Base non exposée au réseau | Port publié sur `127.0.0.1` seulement, commit `2d8ffdb`, conteneur recréé le 27/08 pour que la machine applique le correctif |
| Protections applicatives Django | Middlewares CSRF, clickjacking, sessions et authentification actifs |
| Intégrité des données | 53 contraintes nommées, dont les règles de licence et d'attribution vérifiées par le moteur |
| Débogage désactivé par défaut | `DEBUG` lu depuis l'environnement, `False` en l'absence de variable, commit `a91392b` |
| Réglages de transport | Redirection HTTPS, HSTS d'un an, cookies de session et CSRF `Secure` et `SameSite`, actifs dès que `DEBUG` vaut `False` |
| Hôtes d'exposition hors du code | `ALLOWED_HOSTS` lu depuis l'environnement, boucle locale par défaut ; le domaine de tunnel vit dans `.env` et se retire sans commit |
| Contrôle de déploiement au vert | `DJANGO_DEBUG=False uv run python manage.py check --deploy` : aucun avertissement |
| Données applicatives sur PostgreSQL | `eduai_app`, distincte de `eduai_data`, commit `c59eedb` — voir `docs/decisions/006` et `008` |

### Écarts corrigés le 28 août 2026

Les deux écarts qui figuraient ici sont traités. Ils sont conservés dans le
tableau, avec leur correctif et sa preuve, plutôt que retirés : un document de
conformité qui efface la trace de ses manquements passés est moins crédible
qu'un document qui montre comment ils ont été levés.

| Écart | Portée | Correctif | Preuve |
|---|---|---|---|
| `ExerciseSubmission.ip_address` collectée | Donnée personnelle sans finalité établie | **Champ supprimé**, migration `exercises/0003_supprime_ip_address` | Colonne absente de `information_schema.columns` ; test `test_les_soumissions_ne_portent_plus_d_adresse_ip` |
| Aucune route de suppression de compte | Droit d'effacement non exerçable par l'apprenant | Route `users:supprimer_compte`, module `apps/users/effacement.py` | 9 tests dans `tests/test_effacement_compte.py` |

#### Sur la suppression du champ `ip_address`

**Une donnée sans finalité ne se conserve pas** — et lui attribuer une durée
reviendrait à régulariser une collecte qui n'aurait pas dû avoir lieu. Le
principe de minimisation de l'article 5.1.c porte d'abord sur la collecte, non
sur la seule durée.

Le champ était renseigné à chaque soumission d'exercice, à partir de
`REMOTE_ADDR`, et **n'était lu par aucun code du projet** : ni sécurité, ni
lutte contre la fraude, ni statistique. Une adresse IP est pourtant une donnée
personnelle au sens du considérant 26, une personne étant identifiable dès lors
que des moyens raisonnablement susceptibles d'être utilisés le permettent — ce
qui est le cas d'une IP rapprochée des journaux d'un fournisseur d'accès.

La colonne a été supprimée, avec les valeurs qu'elle contenait. L'effet est
irréversible et c'est celui qui était recherché.

#### Sur la route de suppression de compte

L'exigence tenue ici est qu'elle soit **effective, et non déclarative**. Un
effacement partiel est pire qu'un effacement absent : il donne l'illusion d'être
conforme.

Une vue qui se contenterait d'appeler `user.delete()` laisserait derrière elle
deux catégories de reliquats, qu'aucune cascade de Django n'atteint :

| Reliquat | Pourquoi la cascade ne l'atteint pas |
|---|---|
| **Le fichier d'avatar** | La suppression retire la ligne qui désigne le fichier, jamais le fichier lui-même |
| **Les sessions ouvertes** | La table des sessions ne porte aucune clé étrangère vers l'utilisateur ; l'identifiant est enfoui dans une charge sérialisée |

Le module d'effacement traite les deux, et **relit la base et le disque après
coup** pour établir ce qui subsiste. Le rapport qu'il rend porte un champ
`conforme` qui ne vaut vrai que si rien ne reste — ni ligne, ni fichier. La vue
n'affiche un message de confirmation que dans ce cas ; sinon elle avertit
l'utilisateur que l'effacement est incomplet et journalise l'incident, plutôt
que de lui annoncer une conformité qu'elle n'a pas constatée.

Ce qui est effacé, vérifié par test : le compte et le profil, la progression,
les cours et exercices créés, les soumissions de code, la progression par
exercice, les participations aux quiz, le fichier d'avatar propre à
l'utilisateur, et les sessions ouvertes.

Ce qui n'est **pas** effacé, et pourquoi : l'avatar livré par défaut avec
l'application. Il appartient à l'application, non à la personne ; le supprimer
casserait l'affichage de tous les autres comptes. Un effacement trop large est
une régression, pas un excès de zèle — un contre-test le garde.

#### Un effet de bord mesuré, non corrigé

La suppression d'un utilisateur qui a **hébergé une salle de quiz** emporte la
salle, donc les réponses des autres participants à cette partie. C'est une
conséquence de la cascade déclarée sur `GameRoom.host`.

L'article 17 donne un droit à l'effacement de **ses** données ; il ne donne pas
le droit d'emporter celles d'autrui. La correction — rendre l'hôte nullable —
modifierait le comportement du quiz et n'a pas été engagée à dix jours du rendu.

L'effet est donc **mesuré avant d'être produit** : le rapport d'effacement
compte les salles supprimées, les participations et les réponses d'autrui
perdues, et l'écran de confirmation en avertit l'utilisateur lorsque le cas se
présente. Une conséquence connue et annoncée n'est pas du même ordre qu'une
conséquence subie — mais elle reste un écart, et elle est inscrite ici comme
tel.

### Écart restant

| Écart | Portée | Traitement |
|---|---|---|
| Cascade sur `GameRoom.host` | L'effacement d'un compte emporte les réponses d'autres participants | Identifié, mesuré, annoncé à l'utilisateur ; correction reportée après le 4 septembre |

---

## 9. Registre des traitements

L'exemption de l'article 30.5 pour les organismes de moins de 250 salariés ne
s'applique pas : le traitement n'est pas occasionnel. Le présent document
fournit les éléments qu'un registre exige — finalité, catégories de personnes
et de données, destinataires, durées, mesures de sécurité — mais il ne le
remplace pas. Sa tenue relève du responsable de traitement.
