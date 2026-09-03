"""
Le lexique : ce que l'apprenant a croisé, et d'où ça vient.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C4 (E1) — attribution ; C1 (E1) — sources ; C10 (E3)

Deux listes, deux provenances, et **aucune des deux n'est écrite à la main** :

1. **Les modules rencontrés dans les cours.** Ils sont relevés dans le contenu
   des supports publiés, en lisant les lignes `import`. Ce que l'apprenant voit
   ici est donc exactement ce que ses cours emploient — pas une liste générale
   de modules Python.

2. **Les bibliothèques documentées dans le corpus.** Elles viennent de la base
   du jeu de données, avec leur licence et le nombre de pages collectées. Ce
   sont les sources que le tuteur peut citer quand il répond.

Choix : ne rien rédiger. Motivation : une définition inventée serait invérifiable
et vieillirait mal. La description d'un module standard est donc **sa propre
docstring**, lue à l'exécution ; celle d'une bibliothèque est le décompte réel
de ce qui a été collecté chez elle. Rien de ce qui s'affiche ici n'a été écrit
pour l'occasion.
"""

import importlib
import re
import sys
from collections import Counter, defaultdict

#: Les lignes d'import, sous leurs deux formes.
IMPORT = re.compile(
    r"^\s*(?:from\s+([a-zA-Z_][\w.]*)"
    r"|import\s+([a-zA-Z_][\w.]*(?:\s*,\s*[a-zA-Z_][\w.]*)*))",
    re.M,
)

#: Le nom d'affichage d'une bibliothèque, d'après l'hôte de sa documentation.
#:
#: Choix : une table explicite plutôt qu'une déduction depuis le nom de domaine.
#: Motivation : `www.django-rest-framework.org` ne donne pas « Django REST
#: framework » par découpage, et `docs.pytorch.org` donnerait « docs ». Sept
#: entrées écrites une fois valent mieux qu'une règle qui se trompe.
BIBLIOTHEQUES = {
    "docs.python.org": "Python — bibliothèque standard",
    "pandas.pydata.org": "pandas",
    "scikit-learn.org": "scikit-learn",
    "www.django-rest-framework.org": "Django REST framework",
    "docs.pytorch.org": "PyTorch",
    "fastapi.tiangolo.com": "FastAPI",
    "docs.opencv.org": "OpenCV",
    "www.postgresql.org": "PostgreSQL",
}


def _hote(url: str) -> str:
    """Rend l'hôte d'une URL, sans protocole ni chemin."""
    sans_protocole = re.sub(r"^https?://", "", url or "")
    return sans_protocole.split("/")[0]


def _description_de_module(nom: str) -> str:
    """
    Rend la première ligne de la docstring d'un module standard.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — sécurité

    Choix : n'importer QUE ce que `sys.stdlib_module_names` reconnaît.
    Motivation : les noms viennent du contenu des cours, donc de fichiers que
    le projet n'a pas écrits. Importer un nom arbitraire exécuterait son code
    au chargement de la page — c'est un chemin d'exécution offert à qui
    contrôle un support. La liste de la bibliothèque standard est fixe et
    connue de l'interpréteur : elle ferme la porte.
    """
    if nom not in sys.stdlib_module_names:
        return ""
    try:
        module = importlib.import_module(nom)
    except Exception:
        # Un module standard peut manquer sur une plateforme donnée.
        return ""
    doc = (module.__doc__ or "").strip()
    if not doc:
        return ""
    premiere = doc.splitlines()[0].strip()
    return premiere if len(premiere) > 3 else ""


def modules_des_cours():
    """
    Relève les modules employés par les cours publiés.

    Compétence visée : C17 (épreuve E4)

    Rend une liste triée d'entrées : le nom, sa description, le nombre
    d'occurrences, et les compétences dont les cours l'emploient. Un module cité
    dans plusieurs cours n'apparaît qu'une fois.
    """
    from apps.courses.models import PartieDeCours

    occurrences = Counter()
    competences = defaultdict(set)

    parties = (PartieDeCours.objects
               .filter(cours__remplace_le__isnull=True)
               .select_related("cours__competence"))
    for partie in parties:
        for trouve in IMPORT.finditer(partie.contenu):
            noms = trouve.group(1) or trouve.group(2) or ""
            for nom in noms.split(","):
                racine = nom.strip().split(".")[0]
                if not racine:
                    continue
                occurrences[racine] += 1
                competences[racine].add(
                    (partie.cours.competence.code, partie.cours.competence.intitule))

    entrees = []
    for nom, nombre in occurrences.items():
        entrees.append({
            "nom": nom,
            "description": _description_de_module(nom),
            "standard": nom in sys.stdlib_module_names,
            "occurrences": nombre,
            "competences": sorted(competences[nom]),
        })
    return sorted(entrees, key=lambda e: e["nom"].lower())


def bibliotheques_du_corpus():
    """
    Relève les bibliothèques dont la documentation a été collectée.

    Compétence visée : C4 (épreuve E1) — attribution
    Compétence concernée : C1 (E1)

    Rend, pour chacune, le nombre de pages conservées et sa licence. C'est ce
    que le tuteur peut citer : une bibliothèque absente d'ici ne sera jamais
    une source de sa réponse, et l'apprenant a le droit de le savoir.

    Choix : la base est interrogée en lecture, par les modèles de l'API du jeu
    de données. Motivation : ils portent déjà le routage vers `eduai_data` et
    le filtre des documents retirés. Réécrire la requête ici en ouvrirait une
    seconde à tenir.
    """
    from apps.api_data.models import Document

    compte = Counter()
    licences = defaultdict(set)

    documents = (Document.objects
                 .filter(retire_le__isnull=True)
                 .exclude(url_source__isnull=True)
                 .values_list("url_source", "licence_id"))
    for url, licence in documents.iterator():
        hote = _hote(url)
        if hote not in BIBLIOTHEQUES:
            continue
        compte[hote] += 1
        if licence:
            licences[hote].add(str(licence))

    entrees = [{
        "nom": BIBLIOTHEQUES[hote],
        "hote": hote,
        "url": f"https://{hote}/",
        "pages": nombre,
        "licences": sorted(licences[hote]),
    } for hote, nombre in compte.items()]
    return sorted(entrees, key=lambda e: (-e["pages"], e["nom"].lower()))
