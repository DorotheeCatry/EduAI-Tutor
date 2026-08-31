# 025 — Ce qui se traduit, et ce qui ne se traduit pas

**Date :** 31 août 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C5 (E1) et C9 (E2) — les deux API ; C13 (E3) — accessibilité ; C21 (E5)

## Contexte

L'internationalisation de l'interface pose une question que le seul mot
« traduire » masque : **jusqu'où**. Une application n'est pas un bloc, et
traduire ce qui ne doit pas l'être coûte deux fois — au moment de le faire, et
à chaque fois qu'on cherche ensuite une chaîne dans les journaux.

## Décision, en une table

| Élément | Traduit ? | Motif |
|---|---|---|
| Gabarits de l'interface | **oui** | C'est ce que l'apprenant lit |
| Messages `django.contrib.messages` | **oui** | Même raison : ils s'affichent dans l'interface |
| Étiquettes et aides des formulaires | **oui** | Idem |
| `verbose_name` des modèles | **oui** | Ils remontent dans les formulaires et l'administration |
| **Messages d'erreur des deux API** | **non** | Voir ci-dessous |
| Journaux applicatifs | **non** | Voir ci-dessous |
| Dossiers d'incident, décisions, documentation | **non** | Voir ci-dessous |
| **Contenu pédagogique et corpus** | **non** | Voir la réserve 10 |

## Pourquoi les messages d'API ne se traduisent pas

C'est le point qui demandait une décision explicite, et non un choix par
défaut.

**Les deux API renvoient déjà un identifiant lisible par une machine.** Le
service IA répond `{"detail": "...", "code": "quota_depasse",
"identifiant_incident": "f5dd85d4"}`. Le champ qui porte le sens est `code` ;
`detail` est une phrase pour l'humain qui lit une réponse ou la documentation.

**Traduire `detail` donnerait l'illusion d'une API localisée sans en fournir
les moyens.** Un consommateur sérieux ne fait pas d'analyse de chaîne pour
décider quoi faire : il regarde `code`. Et l'interface qui veut afficher un
message à l'apprenant doit le tirer de **son propre catalogue**, indexé par ce
code — c'est-à-dire traduire côté client, là où la langue de la personne est
connue. Traduire côté serveur inviterait à faire l'inverse, et à afficher
l'anglais du serveur à un apprenant francophone parce que le serveur ignore
qui lit.

**Le service IA n'est pas Django.** FastAPI ne partage ni les catalogues, ni
`LocaleMiddleware`, ni la préférence du compte. Lui donner l'i18n de Django
supposerait de recâbler la négociation de langue dans un second cadre, à quatre
jours du rendu, pour un consommateur unique — l'application web — qui traduit
déjà ce qu'il affiche.

**Enfin, la stabilité a une valeur.** Un message d'erreur qui change de langue
selon l'appelant devient impossible à retrouver dans les journaux et dans les
sept dossiers d'incident de ce projet, qui le citent mot pour mot.

**Ce que cela impose :** quand l'application web affiche une erreur venue d'une
API, elle doit la traduire à partir du `code`, jamais recopier `detail` tel
quel. C'est une règle pour la suite, non un état constaté aujourd'hui.

## Pourquoi les journaux et les incidents ne se traduisent pas

Ils s'adressent à qui exploite le service, pas à qui l'utilise. Un journal
traduit devient inutilisable dès qu'on le lit sur une machine réglée
autrement : chercher une chaîne dans les traces suppose qu'elle soit toujours
la même. Ce projet écrit ses journaux en français ; ils y restent.

## La langue des chaînes sources, et pourquoi elle est mêlée

Une conséquence à assumer plutôt qu'à taire. Les chaînes sources du projet sont
**en anglais pour l'interface héritée**, **en français pour tout ce qui a été
écrit en août 2026** — messages de quota, écran de suppression de compte,
compteur de générations.

Les catalogues traitent les deux sens : le catalogue `fr` traduit les sources
anglaises et laisse vides les sources déjà françaises ; le catalogue `en` fait
l'inverse. Une entrée vide signifie « utiliser la chaîne source », ce qui est
correct dans les deux cas.

**L'alternative aurait été de réécrire les 330 chaînes sources en français**
pour n'avoir qu'une langue de départ. C'est plus propre, et c'est un chantier
de réécriture complète des gabarits à quatre jours du rendu, sans autre gain
que l'élégance. Écarté, et écrit ici pour que le mélange se lise comme un choix
et non comme un oubli.

## Les noms de langue restent dans leur langue

Dans le sélecteur du profil, « English » reste « English » en français et
« Français » reste « Français » en anglais. Traduire les noms de langue rendrait
le sélecteur inutilisable pour la personne qui ne lit pas la langue
actuellement affichée — c'est-à-dire exactement celle qui vient le chercher.

## Conséquences

- `docs/reserves.md`, réserve 10 : l'interface est traduite, le contenu
  pédagogique ne l'est pas.
- Le `README` porte la procédure de mise à jour des catalogues : un `.po` non
  régénéré après ajout de chaînes est un écart silencieux de plus.
- La règle « traduire à partir du `code`, jamais recopier `detail` » est à
  appliquer la prochaine fois que l'interface affichera une erreur d'API.
