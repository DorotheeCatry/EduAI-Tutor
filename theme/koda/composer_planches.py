"""
Assemble les planches de sprites de Koda à partir des frames livrées.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — poids des ressources ; C19 (E5) — provenance

Ce script est un outil de construction, au même titre que
`theme/tailwind-v3/construire.sh` : il tourne à la main, et ce qu'il produit est
versionné. Les frames sources, elles, ne le sont pas (44 Mio) — voir
`docs/provenance-ressources.md`.

Trois décisions de fabrication sont inscrites ici, et documentées en 035 :

1. **Une planche par famille de cadrage, jamais de mélange.** Les cinq
   séquences livrées ne sont pas superposables : le recalage des silhouettes
   donne 0,0 % d'écart entre deux frames d'une même séquence, et 14,3 % entre
   `NEUTRAL` et `SLEEPING` même au meilleur décalage. Mélanger deux séquences
   dans un même emplacement produirait un saut à chaque changement d'état.

2. **Certaines images sont composées.** À l'intérieur d'une séquence, le
   registre étant parfait, greffer la zone des yeux d'une frame sur le corps
   d'une autre est invisible. C'est ce qui permet un clignement paupières
   closes ET bouche fermée — combinaison absente de toutes les séquences
   livrées — ou un clin d'œil.

3. **Palette réduite à 64 couleurs.** L'illustration est en aplats ; les 1 926
   couleurs d'une frame sont presque toutes de l'anticrénelage. Mesuré : 184
   Kio pour la planche en gros plan sans réduction, 35 Kio avec.

   Cette réduction passe en mode palette, ce qui ramène la transparence de 247
   niveaux à 18 : les bords anticrénelés durcissent. **Ce choix tient à ce que
   l'application est sombre.** Comparé à l'agrandissement sur le fond du
   panneau (#1f2937), le durcissement est invisible — le contour du dessin est
   noir, le fond l'est presque. Sur fond clair il se verrait. Préserver l'alpha
   coûterait 91 Kio au lieu de 35.

   **Si un thème clair apparaît un jour, ces planches sont à refaire** en
   réduisant les couleurs sans toucher à la couche alpha.

Lancement :

    uv run python theme/koda/composer_planches.py
"""

import json
import sys
from pathlib import Path

from PIL import Image

# --- 1. Initialisation des dépendances et des chemins ---------------------

RACINE = Path(__file__).resolve().parents[2]
FRAMES = RACINE / "static" / "img" / "koda" / "frames"
SORTIE = RACINE / "static" / "img" / "koda" / "planches"

# Cadrages, relevés sur la boîte englobante alpha de TOUTES les frames de la
# séquence, marge de vingt pixels comprise. Un cadrage tiré de trois frames
# échantillonnées coupait les têtes et les bras levés du salut : c'est le
# mouvement qui déborde, pas la pose de départ.
CADRE_GROS_PLAN = (410, 140, 1410, 960)
CADRE_BUSTE = (409, 43, 1476, 938)
CADRE_CORPS = (537, 0, 1481, 1050)

# Zone des yeux, obtenue par différence entre une frame aux yeux ouverts et une
# frame aux yeux fermés, puis élargie de quelques pixels.
YEUX = (730, 350, 1150, 570)
YEUX_GAUCHE = (730, 350, 945, 570)

LARGEUR_GROS_PLAN = 192
LARGEUR_BUSTE = 192
LARGEUR_CORPS = 384
COULEURS = 64
COLONNES = 8


def frame(sequence, numero):
    """Charge une frame livrée, par son numéro d'origine."""
    chemin = FRAMES / sequence / ("final-%04d.png" % numero)
    if not chemin.exists():
        raise FileNotFoundError(
            "frame absente : %s — les sources ne sont pas versionnées, "
            "voir docs/provenance-ressources.md" % chemin
        )
    return Image.open(chemin).convert("RGBA")


def greffer(base, source_yeux, zone=YEUX):
    """
    Compose une image en greffant la zone des yeux d'une frame sur une autre.

    Compétence visée : C17 (épreuve E4)
    Choix : la greffe se fait toujours entre deux frames de la MÊME séquence.
    Motivation : le registre y est parfait, la greffe est donc invisible ;
    entre deux séquences, la tête change de taille et le raccord se verrait.
    """
    composee = base.copy()
    composee.paste(source_yeux.crop(zone), zone)
    return composee


# --- 2. Règles logiques : ce que contient chaque planche -------------------

def images_du_gros_plan():
    """
    Les images du panneau du tuteur, dans l'ordre où la planche les range.

    Compétence visée : C17 (épreuve E4)
    Choix : `repos`, `écoute` et `réfléchit` partagent le même corps et ne
    diffèrent que par l'ouverture des paupières. Motivation : la pose est fixe
    dans la séquence livrée ; prétendre distinguer davantage ces états
    exigerait des dessins qui n'existent pas.
    """
    n = lambda i: frame("NEUTRAL_TALKING_GIF", i)  # noqa: E731
    s = lambda i: frame("SLEEPING_TALKING", i)     # noqa: E731

    repos = n(22)
    images = [
        # 0-4 : repos et son clignement, composés
        repos,
        greffer(repos, n(19)),
        greffer(repos, n(17)),
        greffer(repos, n(16)),
        greffer(repos, n(20)),
    ]
    # 5-22 : la parole, clignement compris — tel que livré
    images += [n(i) for i in range(4, 22)]
    # 23 : le clin d'œil, composé sur un seul œil
    images.append(greffer(repos, n(16), YEUX_GAUCHE))
    # 24-28 : l'assoupissement
    images += [s(i) for i in (1, 3, 5, 7, 9)]
    # 29-32 : le sommeil
    images += [s(i) for i in (12, 20, 28, 36)]
    # 33-36 : le réveil
    images += [s(i) for i in (41, 44, 47, 50)]
    return images


def images_du_corps_entier():
    """Salut et réjouissance : les deux séquences en pied."""
    salut = [frame("SALUTE_GIF", i) for i in range(1, 25)]
    joie = [frame("JUMPING_GIF", i) for i in range(1, 32, 2)]
    repos = [frame("JUMPING_GIF", i) for i in range(33, 49, 2)]
    return salut + joie + repos


def images_du_buste():
    """
    La contrariété, écourtée.

    Compétence visée : C17 (épreuve E4)
    Choix : vingt frames sur quarante-huit, et réservée au refus technique.
    Motivation : la séquence montre un personnage qui crie, poings serrés. La
    servir quand un apprenant se trompe ferait dire au tuteur qu'il est en
    colère contre lui — voir décision 035.
    """
    return [frame("ANGRY_TALKING_GIF", i) for i in range(1, 21)]


# --- 3. Assemblage et sauvegarde ------------------------------------------

def assembler(images, cadre, largeur, nom):
    """Range les images en grille et écrit la planche, palette réduite."""
    hauteur = round(largeur * (cadre[3] - cadre[1]) / (cadre[2] - cadre[0]))
    lignes = (len(images) + COLONNES - 1) // COLONNES
    planche = Image.new("RGBA", (COLONNES * largeur, lignes * hauteur))
    for rang, image in enumerate(images):
        vignette = image.crop(cadre).resize((largeur, hauteur), Image.LANCZOS)
        planche.paste(vignette, ((rang % COLONNES) * largeur,
                                 (rang // COLONNES) * hauteur))

    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    planche.quantize(colors=COULEURS, method=Image.FASTOCTREE).save(
        chemin, "PNG", optimize=True)
    poids = chemin.stat().st_size / 1024
    print("%-26s %2d images | %dx%d | %6.1f Kio"
          % (nom, len(images), largeur, hauteur, poids))
    return {"fichier": "img/koda/planches/" + nom, "images": len(images),
            "colonnes": COLONNES, "largeur": largeur, "hauteur": hauteur}


def main():
    """
    Point de lancement.

    Compétence visée : C17 (épreuve E4)
    """
    # Seule la planche que l'application sert est produite par défaut, et
    # c'est la seule versionnée.
    #
    # Compétence visée : C21 (épreuve E5)
    # Choix : ne pas livrer une planche que rien n'affiche. Motivation : ce
    # projet a déjà payé le prix d'une ressource complète et inemployée — 465
    # lignes de consumer WebSocket qui laissaient croire à une fonctionnalité
    # (décision 031). Deux cent soixante Kio d'images qu'aucune page ne charge
    # racontent la même histoire, en plus discret.
    #
    # `--tout` reconstruit les autres le jour où elles seront branchées.
    a_produire = [("gros_plan", images_du_gros_plan, CADRE_GROS_PLAN,
                   LARGEUR_GROS_PLAN, "koda-gros-plan.png")]
    if "--tout" in sys.argv:
        a_produire += [
            ("corps_entier", images_du_corps_entier, CADRE_CORPS,
             LARGEUR_CORPS, "koda-corps-entier.png"),
            ("buste", images_du_buste, CADRE_BUSTE,
             LARGEUR_BUSTE, "koda-buste.png"),
        ]
    try:
        planches = {
            cle: assembler(images(), cadre, largeur, nom)
            for cle, images, cadre, largeur, nom in a_produire
        }
    except FileNotFoundError as erreur:
        raise SystemExit("Assemblage impossible : %s" % erreur)

    total = sum((SORTIE / Path(p["fichier"]).name).stat().st_size
                for p in planches.values()) / 1024
    print("total des planches : %.1f Kio" % total)

    (SORTIE / "planches.json").write_text(
        json.dumps(planches, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print("descripteur écrit : planches.json")


if __name__ == "__main__":
    main()
