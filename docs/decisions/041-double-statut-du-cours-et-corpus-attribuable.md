# 041 — Le double statut du cours, et le seul corpus qui permet de citer

**Date :** 2 septembre 2026
**Compétence visée :** C17 (épreuve E4) — application web
**Compétences concernées :** C4 (E1) — attribution ; C10 (E3) ; C13 (E3)

## Deux statuts, jamais un drapeau

| Statut | Origine | Ce qu'il engage |
|---|---|---|
| **Publié** | écrit par l'organisme, relu | la responsabilité pédagogique d'un formateur |
| **Provisoire** | engendré par le modèle | rien. Aucune relecture |

**Le statut décide du comportement, pas seulement de l'affichage** — d'où deux
valeurs distinctes plutôt qu'un booléen `est_engendre`. Le champ `redige_par`
n'est renseigné que pour un cours publié : c'est lui qui dit qui répond du
contenu.

## Ce que ce mécanisme résout, et ce qu'il n'est pas

**Ce n'est pas un contournement du manque de contenu.** Un formateur publie ses
cours au rythme de sa progression pédagogique ; un apprenant qui veut prendre de
l'avance se heurte sinon à une porte fermée. Le cours provisoire lui donne de
quoi commencer, **en disant clairement ce qu'il est**.

À l'écran, un cours provisoire porte un **bandeau en tête**, avec une icône *et*
un texte — jamais une couleur seule, jamais une note grise en pied de page.
L'apprenant doit savoir avant de lire, pas après. Un test vérifie que le statut
apparaît avant le contenu.

## Quand le cours publié arrive

Le provisoire **cède la place sans être supprimé** : `remplace_le` est daté, il
sort de l'affichage, il reste consultable. Un apprenant doit pouvoir comprendre
d'où venait ce qu'il lisait la semaine précédente.

Une contrainte d'unicité partielle — sur les cours dont `remplace_le` est nul —
garantit qu'il n'y a jamais deux cours courants pour une compétence et un
statut, tout en laissant l'historique s'accumuler.

**La fiche de l'apprenant n'est pas touchée.** Voir décision 040.

## Le corpus interrogé, et pourquoi il n'y a pas de choix

Un enrichissement puise dans le corpus documentaire. **Ce n'est pas un choix de
qualité mais de droit.** Les deux collections du vector store n'ont pas les
mêmes métadonnées, et le constat suffit à trancher :

| Collection | Fragments | Métadonnées |
|---|---|---|
| `eduai_knowledge_base` | 387 | `source: 'control-flow.md'`, `section`, `type` |
| `eduai_corpus_documentaire` | 21 189 | `url_source`, `code_licence`, `attribution_requise` |

Un enrichissement puisé dans la première serait **inattribuable — non parce
qu'on aurait oublié de l'afficher, mais parce que l'information n'existe pas**.
Aucun développement ultérieur ne pourrait la faire apparaître : elle n'a jamais
été écrite au moment de l'indexation.

Or l'attribution est la condition juridique qui autorise l'usage de ce corpus,
sous CC BY-SA et licences équivalentes. La collection pédagogique reste ce
qu'elle est — le contexte du Pédagogue — et n'est pas interrogée par les
enrichissements. Un test le vérifie sur le code, pas sur l'intention.

## L'attribution voyage jusque dans la fiche

Chaque ajout porte ses `sources` : `url_source`, `titre`, `code_licence` et
`attribution_requise`, une entrée par fragment employé, dédoublonnées.

**La licence est conservée, pas seulement l'URL.** Une URL seule ne dit pas s'il
*faut* nommer l'auteur — c'est l'obligation qui décide de l'affichage, et elle
est portée par le fragment depuis l'indexation (`indexation_corpus.py`).

## Ce que ce choix laisse ouvert

Un ajout conserve les sources telles qu'elles étaient au moment où il a été
produit. Si un document disparaît du corpus, le lien mourra dans la fiche sans
que rien ne le signale. Le pipeline sait marquer un document disparu
(décision 013) ; rien ne relie encore ce marquage aux fiches.
