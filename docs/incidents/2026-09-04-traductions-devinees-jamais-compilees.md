# Incident 019 — Des traductions devinées, jamais compilées, comptées comme faites

**Date :** 4 septembre 2026
**Compétence visée :** C21 (épreuve E5) — résolution d'incidents
**Compétences concernées :** C10 (E3) — accessibilité ; C17 (E4) ; C18 (E4)
**Composants :** `locale/en/LC_MESSAGES/django.po`, `locale/fr/LC_MESSAGES/django.po`

## Déclenchement

La relecture du rapport E3 portait sur une affirmation d'accessibilité :
« interface bilingue, **330 chaînes traduites** ». Le décompte a été refait sur
le catalogue plutôt que cru. Il n'y avait pas 330 traductions.

## Périmètre

Toute l'interface servie à un compte dont la langue est l'anglais, et — pour la
seconde moitié du défaut — une partie de l'interface servie en français.

## Diagnostic

Trois défauts distincts se masquaient l'un l'autre.

**Premier : le catalogue était en retard sur l'application.** `makemessages`
n'avait pas été rejoué depuis un moment ; 83 chaînes présentes dans les gabarits
ne figuraient dans aucun catalogue. Elles étaient servies en français à tout le
monde, sans que rien ne le signale.

**Deuxième : le décompte confondait deux populations.** Le projet mélange deux
langues à la source — 275 chaînes sont écrites en anglais dans le code, 327 en
français. Un `msgstr` anglais vide n'a pas le même sens dans les deux cas :
pour une chaîne de source anglaise, c'est le bon comportement, le repli rend
déjà l'anglais. Les compter comme manquantes surestimait le défaut ; ne pas
distinguer les deux populations rendait toute mesure ininterprétable.

**Troisième, et le plus instructif : trente-quatre entrées « fuzzy ».** Quand
une chaîne nouvelle ressemble à une chaîne disparue, `makemessages` recopie
l'ancienne traduction et pose le marqueur `fuzzy`. Les rapprochements étaient
faux :

| Chaîne | Traduction devinée |
|---|---|
| `Créé le` | *Imported on* |
| `À revoir` | *Worth knowing:* |
| `Noté. Une autre question ?` | *Your question* |
| `niveau %(n)s` | *Level 1* |

**Le piège est double.** `msgfmt` **exclut** ces entrées du catalogue compilé :
la chaîne retombe donc sur sa langue source, et l'utilisateur ne voit jamais la
traduction absurde. Mais un décompte des `msgstr` non vides les compte comme
traduites. **Une entrée approximative est une chaîne non traduite qui se
présente comme traduite** — et aucun outil de la chaîne ne le signalait.

Deux d'entre elles étaient des bombes à retardement : `%(n)s compétence`
portait `%(total)s competencies, none started`, et `niveau %(n)s` portait
`Level 1`. Le marqueur de variable n'y survivait pas. Si l'une de ces entrées
avait été validée à la main — un geste d'une seconde dans n'importe quel éditeur
de catalogue — la page correspondante aurait levé une erreur en anglais
seulement, donc jamais pendant un essai en français.

Le catalogue français portait le même défaut en miroir : 35 entrées
approximatives, dont des chaînes de source anglaise (`Multiplayer`,
`Enter a room code`) servies telles quelles à un francophone.

## Résolution

1. `makemessages` rejoué, les 83 chaînes manquantes extraites.
2. **171 chaînes de source française traduites** en anglais. Les douze dont la
   forme anglaise est le mot lui-même — `Module`, `Source`, `Correct` — restent
   au repli, et la liste est explicite dans le test.
3. **Les 69 entrées approximatives traitées une par une** : traduction correcte
   côté anglais, retour au repli côté français quand le `msgid` était déjà
   français. Plus aucun marqueur `fuzzy` hors l'en-tête des catalogues.
4. Vider les fausses entrées françaises a révélé **onze chaînes de plus** qui
   n'avaient jamais eu de traduction anglaise : le troisième défaut cachait une
   partie du premier.

## Tests

`tests/test_couverture_traduction.py`, quatre contrôles :

- toute chaîne de source française porte une forme anglaise, ou figure dans une
  liste d'exemption explicite ;
- cette liste d'exemption ne couvre aucune chaîne déjà traduite, pour qu'elle ne
  devienne pas un tapis sous lequel glisser un oubli ;
- les marqueurs `%(nom)s` sont identiques entre la source et sa traduction ;
- aucune entrée approximative ne subsiste, dans aucun des deux catalogues.

Le troisième contrôle est celui qui a trouvé `niveau %(n)s` → `Level 1`.

## Le motif, et ce qu'il rejoint

Ce dossier partage son motif avec les dix-huit précédents : **une chose qui
semble faite et qui ne l'est pas.** La particularité est ici que le mécanisme
défaillant était **conçu pour être silencieux** — le repli sur la langue source
est un comportement voulu de `gettext`, et c'est ce qui rend l'oubli
indétectable à l'usage. Un francophone qui essaie l'application ne voit rien,
puisque sa langue est celle de la source.

La question à ajouter à `motifs_incidents.md` : **ce mécanisme de repli
distingue-t-il « absent » de « identique » ?** Un repli qui rend la bonne valeur
par accident empêche de voir qu'aucune valeur n'a été fournie.
