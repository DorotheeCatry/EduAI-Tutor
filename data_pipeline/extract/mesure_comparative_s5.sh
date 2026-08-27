#!/usr/bin/env bash
#
# Mesure comparative de la source big data (S5) sur les deux dumps.
#
# Compétence visée : C1 (épreuve E1) — traitement d'un système big data
# Compétence visée : C20 (épreuve E5) — mesure et suivi d'un traitement
#
# Objectif : rejouer strictement le même traitement sur le dump Data Science
# (123 Mio) et sur celui de Stack Overflow, afin que la comparaison des durées
# mesure le volume et non deux versions du code. C'est cette comparaison qui
# justifie chiffrément le recours à un moteur distribué.
#
# Le script attend la fin du téléchargement en cours, vérifie l'archive,
# la décompresse, puis lance l'extracteur. Il peut donc être lancé avant que
# le téléchargement soit terminé.
#
# Lancement :
#   nohup bash data_pipeline/extract/mesure_comparative_s5.sh > mesure.log 2>&1 &
#
# Arrêt : tuer le processus. Aucune étape n'est destructive ; la reprise
# repart de l'étape la plus avancée déjà terminée.

set -u -o pipefail

RACINE="/media/apprenant/Stockage/eduai-data"
ARCHIVE="$RACINE/dumps/stackoverflow.com-Posts.7z"
DESTINATION="$RACINE/dumps/stackoverflow"
MEMOIRE_PILOTE="${MEMOIRE_PILOTE:-12g}"

journal() { printf '%s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

# --- 1. Attendre la fin du téléchargement ---------------------------------
#
# On surveille le processus wget plutôt que la taille du fichier : une taille
# stable pendant quelques secondes ne prouve pas la fin du transfert, elle
# peut aussi signaler une connexion figée.
journal "Attente de la fin du téléchargement."
while pgrep -f "wget -c https://archive.org/download/stackexchange/stackoverflow" > /dev/null; do
    taille=$(stat -c %s "$ARCHIVE" 2>/dev/null || echo 0)
    journal "  téléchargement en cours — $((taille / 1024 / 1024 / 1024)) Gio"
    sleep 300
done
journal "Téléchargement terminé : $(du -h "$ARCHIVE" | cut -f1)"

# --- 2. Vérifier l'intégrité de l'archive ---------------------------------
#
# Une archive tronquée produirait un XML tronqué, donc une mesure fausse
# présentée comme valide. Le contrôle coûte quelques minutes, une mesure
# fausse coûterait la crédibilité du chiffre à l'oral.
journal "Vérification de l'archive."
if ! 7z t "$ARCHIVE" > /dev/null 2>&1; then
    journal "ÉCHEC : archive corrompue ou incomplète. Reprendre le téléchargement"
    journal "        avec : wget -c <url>  (l'option -c reprend où il s'est arrêté)"
    exit 1
fi
journal "Archive intègre."

# --- 3. Décompresser ------------------------------------------------------
if [ -f "$DESTINATION/Posts.xml" ]; then
    journal "Posts.xml déjà présent, décompression sautée."
else
    journal "Décompression vers $DESTINATION."
    mkdir -p "$DESTINATION"
    # Espace libre contrôlé avant de commencer : le XML décompressé est
    # nettement plus volumineux que l'archive, et un disque plein en cours
    # de décompression laisse un fichier partiel difficile à distinguer
    # d'un fichier complet.
    libre_gio=$(df -BG --output=avail "$RACINE" | tail -1 | tr -dc '0-9')
    journal "  espace libre : ${libre_gio} Gio"
    if [ "$libre_gio" -lt 250 ]; then
        journal "ÉCHEC : moins de 250 Gio libres, décompression annulée."
        exit 1
    fi
    if ! 7z x -o"$DESTINATION" -y "$ARCHIVE" > /dev/null; then
        journal "ÉCHEC : décompression interrompue."
        exit 1
    fi
    journal "Décompression terminée : $(du -h "$DESTINATION/Posts.xml" | cut -f1)"
fi

# --- 4. Lancer l'extracteur sur le gros dump ------------------------------
#
# Mêmes paramètres de sélection que sur le dump Data Science : seul le chemin
# change. C'est la condition pour que la comparaison porte sur le volume.
journal "Lancement de S5 sur le dump Stack Overflow (pilote : $MEMOIRE_PILOTE)."
cd /media/apprenant/Stockage/workspace/EduAI-Tutor || exit 1

uv run python -m data_pipeline.extract.s5_bigdata_stackexchange \
    --dump "$DESTINATION" \
    --memoire-pilote "$MEMOIRE_PILOTE"
code=$?

if [ $code -ne 0 ]; then
    journal "ÉCHEC : l'extracteur a rendu le code $code."
    journal "        Piste la plus probable : mémoire du pilote insuffisante."
    journal "        Relancer avec MEMOIRE_PILOTE=16g bash $0"
    exit $code
fi

# --- 5. Comparer les deux mesures -----------------------------------------
journal "Comparaison des deux rapports de métriques."
uv run python - <<'PY'
import json
from pathlib import Path

racine = Path("data_pipeline/data/raw")
rapports = {}
for chemin in sorted(racine.glob("s5_bigdata_stackexchange.*.metriques.json")):
    nom = chemin.name.split(".")[1]
    rapports[nom] = json.loads(chemin.read_text(encoding="utf-8"))

if len(rapports) < 2:
    print("Un seul rapport disponible, comparaison impossible.")
    raise SystemExit(0)

champs = [
    ("taille_posts_xml_mio", "Posts.xml (Mio)"),
    ("posts_dans_parquet", "posts traités"),
    ("partitions_annee", "partitions"),
    ("duree_conversion_secondes", "conversion (s)"),
    ("duree_metriques_secondes", "volumétrie (s)"),
    ("duree_selection_secondes", "sélection (s)"),
    ("duree_secondes", "total (s)"),
    ("documents_retenus", "documents retenus"),
]
noms = list(rapports)
largeur = max(len(libelle) for _, libelle in champs) + 2

print()
print("MESURE COMPARATIVE — source big data (S5)")
print()
print(" " * largeur + "".join(f"{nom:>22}" for nom in noms))
for cle, libelle in champs:
    ligne = f"{libelle:<{largeur}}"
    for nom in noms:
        ligne += f"{rapports[nom].get(cle, '—'):>22}"
    print(ligne)

petit, grand = noms[0], noms[1]
if rapports[petit].get("taille_posts_xml_mio", 0) > rapports[grand].get("taille_posts_xml_mio", 0):
    petit, grand = grand, petit

facteur_volume = rapports[grand]["taille_posts_xml_mio"] / rapports[petit]["taille_posts_xml_mio"]
facteur_duree = rapports[grand]["duree_secondes"] / rapports[petit]["duree_secondes"]
print()
print(f"Volume    : x{facteur_volume:.1f}")
print(f"Durée     : x{facteur_duree:.1f}")
print(f"Rendement : {facteur_volume / facteur_duree:.2f} "
      "(> 1 = le traitement encaisse le volume mieux que linéairement)")
PY

journal "Mesure comparative terminée."
