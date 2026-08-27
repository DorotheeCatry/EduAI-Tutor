# Notes — commandes shell utiles au projet

Mémo personnel. Commandes rencontrées pendant le développement du pipeline,
avec ce qu'elles font réellement plutôt que leur formule toute faite.

---

## Lancer une tâche longue sans bloquer le terminal

```bash
nohup wget -c https://exemple.org/gros-fichier.7z > telechargement.log 2>&1 &
```

Quatre mécanismes indépendants dans cette ligne.

### `&` — arrière-plan

Rend la main immédiatement au lieu d'attendre la fin. Le processus continue,
mais il reste rattaché au terminal.

### `nohup` — *no hangup*

Fermer un terminal envoie le signal `SIGHUP` aux processus lancés depuis lui,
ce qui les tue. `nohup` les en protège : la tâche survit à la fermeture du
terminal et à la déconnexion de la session.

`&` seul ne suffit donc pas si on compte fermer la fenêtre.

### `> fichier` — redirection de la sortie standard

Un programme Unix dispose de trois flux :

| Flux | Numéro | Rôle |
|---|---|---|
| `stdin` | 0 | Entrée |
| `stdout` | 1 | Sortie normale |
| `stderr` | 2 | Erreurs |

`> fichier` envoie **stdout** dans le fichier, en l'écrasant.
`>> fichier` ajoute à la suite sans écraser.

### `2>&1` — rediriger aussi les erreurs

Envoie **stderr** vers la destination actuelle de stdout — donc le même fichier.

**L'ordre est significatif.** `> fichier 2>&1` fonctionne ; `2>&1 > fichier`
ne fait pas la même chose, car stderr est redirigé vers le terminal avant que
stdout ne change de destination.

---

## Suivre une tâche en cours

```bash
tail -f telechargement.log    # affiche les nouvelles lignes en direct
tail -40 telechargement.log   # les 40 dernières lignes, puis rend la main
```

`-f` = *follow*. `Ctrl+C` arrête **l'affichage**, pas la tâche : ce sont deux
processus distincts.

```bash
jobs              # tâches en fond du terminal courant seulement
pgrep -a wget     # tous les processus wget, quel que soit le terminal
kill <PID>        # arrêter un processus par son identifiant
```

`jobs` ne voit rien après fermeture du terminal d'origine — `pgrep` reste le
bon réflexe.

---

## Télécharger

```bash
wget -c https://exemple.org/fichier.7z
```

`-c` = *continue*. Reprend un téléchargement interrompu au lieu de tout
recommencer. Indispensable sur les fichiers volumineux.

---

## Occupation disque

```bash
du -sh dossier/       # taille totale d'un dossier
du -sh *              # taille de chaque élément du dossier courant
df -h ~               # espace libre de la partition
df -h /media/...      # espace libre d'une autre partition
```

- `-s` = *summarize*, un total au lieu du détail
- `-h` = *human-readable*, `18G` plutôt que `19327352832`

---

## Trouver un fichier

```bash
find ~ -maxdepth 3 -name "manage.py"           # limité à 3 niveaux
find / -name "manage.py" 2>/dev/null           # partout, erreurs masquées
find . -type f -name "*.jsonl"                 # fichiers seulement
```

`2>/dev/null` jette les erreurs de permission dans le vide — sans quoi une
recherche sur `/` noie le résultat sous les refus d'accès.

---

## Chercher dans des fichiers

```bash
grep -c "motif" fichier              # compte les LIGNES contenant le motif
grep -rn "motif" --include=*.py .    # récursif, avec numéro de ligne
grep -rln "motif" .                  # liste seulement les fichiers concernés
```

| Option | Effet |
|---|---|
| `-c` | Compte les lignes correspondantes |
| `-r` | Récursif dans les sous-dossiers |
| `-n` | Affiche le numéro de ligne |
| `-l` | Affiche les noms de fichiers, pas les lignes |
| `-i` | Ignore la casse |

**Piège rencontré.** `grep -c $'\x00' fichier` ne cherche pas les octets nuls :
`$'\x00'` se réduit à une chaîne vide en bash, et grep compte alors *toutes*
les lignes. Pour chercher un caractère de contrôle dans du JSON, chercher sa
forme échappée : `grep -c '\\u0000' fichier`.

---

## Docker

```bash
docker compose up -d              # démarre les services en fond
docker compose ps                 # état des conteneurs
docker compose logs postgres      # journaux d'un service
docker compose down               # arrête, CONSERVE les volumes
docker compose down -v            # arrête et SUPPRIME les volumes
docker compose exec postgres psql -U eduai -d eduai_data
```

**Deux pièges vécus sur ce projet.**

`restart: unless-stopped` redémarre un conteneur sans le **recréer**. Une
modification du `docker-compose.yml` reste donc sans effet tant que
`docker compose up -d` trouve un conteneur en bonne santé. Pour forcer :

```bash
docker compose up -d --force-recreate
```

Les scripts de `/docker-entrypoint-initdb.d` ne s'exécutent qu'au **premier**
démarrage du volume. Corriger un schéma après coup impose un
`docker compose down -v`, qui détruit les données.

---

## Groupes et permissions

```bash
sudo usermod -aG docker $USER   # ajoute l'utilisateur au groupe docker
newgrp docker                    # active le groupe sans se déconnecter
groups                           # groupes actifs dans la session courante
```

L'appartenance à un groupe n'est lue qu'à l'ouverture de session. `newgrp`
ouvre un sous-shell avec le groupe actif — pratique, mais les **autres**
terminaux déjà ouverts ne le voient pas. Une déconnexion/reconnexion règle
tout d'un coup.

---

## Cache de chemins de bash

```bash
hash -r      # vide le cache des chemins de commandes
which -a docker   # tous les emplacements d'une commande, dans l'ordre
```

Bash mémorise l'emplacement des commandes déjà lancées. Si le binaire est
déplacé ou supprimé, l'erreur est trompeuse :

```
bash: /usr/local/bin/docker: No such file or directory
```

alors que la commande existe ailleurs. `hash -r` résout ce cas.

---

## Services systemd

```bash
sudo systemctl status ollama     # état d'un service
sudo systemctl start ollama      # démarrer
sudo systemctl enable ollama     # démarrage automatique au boot
journalctl -e -u ollama          # journaux d'un service
journalctl --vacuum-time=7d      # purge les journaux de plus de 7 jours
```

---

## Nettoyage disque

```bash
sudo apt autoremove --purge      # anciens noyaux et dépendances orphelines
sudo apt clean                   # cache des paquets téléchargés
uv cache clean                   # cache uv
docker system prune -a           # images, conteneurs et réseaux inutilisés
sudo journalctl --vacuum-time=7d # journaux systemd
```

Les anciens noyaux avec leurs en-têtes et modules représentent souvent
plusieurs gigaoctets.

---

## Git

```bash
git branch --show-current                    # branche courante
git status                                   # état de l'arbre de travail
git ls-files | grep migrations               # fichiers SUIVIS correspondants
git log --oneline | grep "\[C1\]"            # commits taggés d'une compétence
git add -f chemin/                           # forcer l'ajout malgré .gitignore
```

`git ls-files` liste ce que Git **suit**, pas ce qui existe sur le disque —
c'est la commande qui a révélé que 15 migrations présentes localement étaient
absentes du dépôt.

---

## Pourquoi ces notes comptent pour la certification

Les mécanismes de tâche en arrière-plan et de redirection de flux sont
exactement ceux du monitorage attendu en C20 : un service qui tourne
indépendamment de toute session et écrit ses journaux dans un fichier
horodaté.

Les deux pièges Docker relevés plus haut relèvent du même écart, celui entre
« le code est corrigé » et « le système exécute la correction » — matière
directe pour la résolution d'incident de C21.
