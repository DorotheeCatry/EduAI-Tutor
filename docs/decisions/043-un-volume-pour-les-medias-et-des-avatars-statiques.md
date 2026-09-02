# 043 — Un volume pour les médias, et des avatars Koda restés statiques

**Date :** 02/09/2026
**Compétences :** C13 (épreuve E3), C17 (E4), C21 (E5)

## Contexte

Un avatar choisi par une apprenante ne s'affichait pas, et l'un des choix
proposés provoquait une erreur 500. Le diagnostic a montré que l'avatar était
correctement enregistré : il n'était jamais servi. La page de profil recopiait
l'image Koda dans `media/`, et `/media/` n'était routé que si `DEBUG` valait
vrai. En production, toute requête vers ces fichiers rendait 404.

Deux questions distinctes se posaient donc : où vivent les avatars Koda, et où
vivent les fichiers réellement déposés par les apprenants.

## Options

1. **Tout dans `media/`**, avec un volume persistant et le routage corrigé.
2. **Tout en statique**, en renonçant à l'envoi d'une photo personnelle.
3. **Séparer selon l'origine du fichier** : les avatars Koda sont livrés avec
   l'application, les photos sont déposées par les apprenants.

## Option retenue

La troisième.

Les vingt avatars Koda sont des **fichiers de l'application** : versionnés,
livrés dans l'image, identiques pour tout le monde. Les recopier dans `media/`
n'ajoutait qu'un chemin de plus par lequel se perdre — et c'est exactement ce
qui s'est produit. Ils sont désormais retenus comme un nom de fichier statique,
dans le champ `koda_avatar` déjà prévu pour cela, que le quiz utilisait déjà.

Les photos envoyées, elles, sont des **données d'apprenant**. Elles restent
dans `media/`, qui reçoit un volume persistant monté sur `/app/media`, et
`/media/` est servi hors `DEBUG`.

## Raisons

**Ce qui est livré avec l'application ne doit pas voyager par le stockage des
données des utilisateurs.** La distinction n'est pas esthétique : elle décide
qui doit sauvegarder quoi, ce qui disparaît à un redéploiement, et ce qu'un
effacement de compte doit supprimer. Un avatar Koda ne se sauvegarde pas, il se
reconstruit depuis l'image ; une photo, non.

**Sans volume, la persistance est une illusion silencieuse.** Le système de
fichiers d'un conteneur est éphémère. Une photo enregistrée sans volume n'émet
aucune erreur : elle disparaît au redéploiement suivant, et l'apprenante
retrouve simplement son avatar par défaut sans savoir pourquoi.

**Le point de montage est créé vide dans l'image**, comme celui du corpus
(décision 018) : un volume monté sur un chemin absent appartiendrait à `root`,
et le conteneur, qui ne tourne pas en `root`, ne pourrait rien y écrire.

**Le démarrage le vérifie en écrivant réellement un fichier témoin**, et non en
lisant des bits de permission — qui diraient « accessible » là où l'écriture
échoue. C'est le motif que le projet a documenté cinq fois : un instrument qui
mesure autre chose que ce qu'on croit. L'échec n'arrête pas le service, mais il
laisse trois lignes explicites dans le journal.

## Limite connue

`/media/` est servi par la vue `serve` de Django, que sa documentation
déconseille à grande échelle. Le projet tient sur un seul conteneur et le
volume concerné compte quelques dizaines d'images : ajouter un serveur web
devant l'application coûterait plus en pièces mobiles que ce qu'il rapporte.
La limite est assumée, et consignée dans les réserves.
