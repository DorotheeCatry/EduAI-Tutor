"""
Les trois couches du cours : référence, fiche, enrichissements.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C10 (E3) ; C4 (E1) — attribution ; C13 (E3) — quotas

Ce module porte les opérations, les vues ne portent que le HTTP.

**Le corpus interrogé est le corpus documentaire, jamais les supports de
formation.** Ce n'est pas un choix de qualité mais de droit : les deux
collections n'ont pas les mêmes métadonnées.

    eduai_knowledge_base       → source: 'control-flow.md', section, type
    eduai_corpus_documentaire  → url_source, code_licence, attribution_requise

Un enrichissement puisé dans la première serait **inattribuable** — non parce
qu'on aurait oublié de l'afficher, mais parce que l'information n'existe pas.
Or l'attribution est la condition qui autorise l'usage de ce corpus
(décision 041).
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext as _

from apps.courses.models import (
    AjoutDeFiche,
    CoursDeReference,
    FicheDApprenant,
    PartieDeCours,
)

logger = logging.getLogger(__name__)

#: Nombre de fragments du corpus employés pour un enrichissement.
FRAGMENTS_PAR_ENRICHISSEMENT = 4


def cours_actif(competence) -> CoursDeReference | None:
    """
    Rend le cours de référence en vigueur pour une compétence.

    Compétence visée : C17 (épreuve E4)

    Choix : le publié prime sur le provisoire, et un cours remplacé n'est
    jamais rendu. Motivation : c'est la règle qui donne son sens au double
    statut — dès qu'un formateur publie, l'apprenant lit le sien.
    """
    return (
        CoursDeReference.objects
        .filter(competence=competence, remplace_le__isnull=True)
        .order_by("statut")          # « publie » avant « provisoire »
        .first()
    )


def fiche_de(apprenant, competence) -> FicheDApprenant:
    """
    Rend la fiche de cet apprenant pour cette compétence, en la créant au besoin.

    Compétence visée : C17 (épreuve E4)
    Choix : créée à la demande plutôt qu'à l'inscription. Motivation : vingt et
    une fiches vides par compte diraient à l'apprenant qu'il a commencé vingt
    et un travaux qu'il n'a pas ouverts.
    """
    fiche, _cree = FicheDApprenant.objects.get_or_create(
        apprenant=apprenant, competence=competence)
    return fiche


def publier_le_cours(competence, parties: list[dict], titre: str, redige_par):
    """
    Publie le cours d'un formateur, et met le provisoire de côté.

    Compétence visée : C17 (épreuve E4)

    `parties` est une liste de dictionnaires : `titre`, `contenu`,
    `fichier_source`, `sous_module`. L'ordre de la liste fait l'ordre des
    parties.

    Choix : le cours remplacé est daté, jamais supprimé. Motivation : il cède
    la place, l'historique reste — un apprenant doit pouvoir comprendre d'où
    venait ce qu'il lisait la semaine précédente. Cela vaut aussi bien pour un
    provisoire que pour une version antérieure du cours publié.

    **La fiche de l'apprenant n'est pas touchée** : elle est rattachée à la
    compétence, pas au cours. C'est tout l'objet de ce découpage.
    """
    # Tout cours actif cède la place, quel que soit son statut — pas seulement
    # le provisoire.
    #
    # Compétence visée : C4 (épreuve E1)
    # Ce filtre ne visait que `PROVISOIRE`, ce qui suffisait au cas décrit par
    # la décision 041 — un formateur publie, le provisoire s'efface. Mais
    # republier un support corrigé se heurtait alors à la contrainte d'unicité,
    # et l'import des cours n'était pas rejouable. Trouvé par le test
    # d'idempotence, pas à la relecture.
    (CoursDeReference.objects
     .filter(competence=competence, remplace_le__isnull=True)
     .update(remplace_le=timezone.now()))

    cours = CoursDeReference.objects.create(
        competence=competence, statut=CoursDeReference.PUBLIE,
        titre=titre, redige_par=redige_par)
    PartieDeCours.objects.bulk_create([
        PartieDeCours(cours=cours, ordre=rang, **partie)
        for rang, partie in enumerate(parties)
    ])
    return cours


def attribution_des_fragments(fragments) -> list[dict[str, Any]]:
    """
    Extrait de chaque fragment ce qu'il faut pour le citer.

    Compétence visée : C4 (épreuve E1) — l'attribution voyage avec le contenu

    Choix : conserver le code de licence et l'obligation d'attribution, pas
    seulement l'URL. Motivation : c'est l'obligation qui décide de l'affichage.
    Une URL sans sa licence ne dit pas s'il FAUT nommer l'auteur.
    """
    sources: list[dict[str, Any]] = []
    vues: set[str] = set()
    for fragment in fragments or []:
        meta = getattr(fragment, "metadata", {}) or {}
        url = meta.get("url_source") or ""
        if not url or url in vues:
            continue
        vues.add(url)
        sources.append({
            "url_source": url,
            "titre": meta.get("titre") or url,
            "code_licence": meta.get("code_licence") or "",
            "attribution_requise": bool(meta.get("attribution_requise")),
        })
    return sources


def _chercher_dans_le_corpus(requete: str) -> list[Any]:
    """
    Interroge le corpus documentaire, celui qui porte les licences.

    Compétence visée : C10 (épreuve E3), C4 (E1)
    Choix : `COLLECTION_DOCUMENTAIRE` explicitement, jamais la collection par
    défaut. Motivation : voir l'en-tête du module — c'est la seule des deux qui
    permette de citer ses sources.
    """
    from langchain_community.vectorstores import Chroma

    from apps.rag.utils import COLLECTION_DOCUMENTAIRE, load_embedding_function

    magasin = Chroma(
        persist_directory="apps/rag/chroma",
        embedding_function=load_embedding_function(),
        collection_name=COLLECTION_DOCUMENTAIRE,
    )
    return magasin.as_retriever(
        search_kwargs={"k": FRAGMENTS_PAR_ENRICHISSEMENT}).invoke(requete)


def enrichir(apprenant, competence, question: str, *, origine: str,
             section_visee: str = "", niveau_vise: int | None = None) -> AjoutDeFiche:
    """
    Produit un enrichissement et l'ajoute à la fiche de l'apprenant.

    Compétence visée : C17 (épreuve E4), C10 (E3)

    Choix : le décompte du quota reste au goulot de l'orchestrateur, il n'est
    pas refait ici. Motivation : le projet a déjà trouvé deux chemins de dépense
    non imputés parce que chaque appelant décomptait pour son compte. Un seul
    endroit décompte, et tout appel y passe.

    **Un enrichissement proposé par le parcours ne décompte rien** (décision
    040) : l'apprenant ne l'a pas demandé, et voir son compteur baisser sans
    geste de sa part ne se comprend qu'après l'avoir subi deux fois.
    """
    from apps.agents.agent_orchestrator import get_orchestrator

    fragments = _chercher_dans_le_corpus(f"{competence.intitule} — {question}")
    sources = attribution_des_fragments(fragments)

    extraits = "\n\n".join(
        (getattr(f, "page_content", "") or "")[:1200] for f in fragments)
    # La consigne de proportion n'est pas une politesse d'invite : sans elle,
    # le modèle répondait à « une liste, c'est quoi ? » par un chapitre complet
    # sur les collections. Une réponse trop longue n'est pas lue, et ce qui
    # n'est pas lu n'apprend rien.
    invite = _(
        "Compétence : %(competence)s.\n"
        "Demande de l'apprenant : %(question)s\n\n"
        "Documentation de référence :\n%(extraits)s\n\n"
        "Réponds en français, en t'appuyant sur cette documentation.\n"
        "Règle de longueur : ta réponse doit être PROPORTIONNÉE à la demande. "
        "Une question courte appelle une réponse courte — quelques phrases et "
        "un exemple s'il éclaire. Ne rédige un développement en plusieurs "
        "parties que si l'apprenant demande explicitement un cours ou une "
        "explication complète. N'ajoute ni plan, ni introduction, ni "
        "conclusion à une réponse brève."
    ) % {"competence": competence.intitule, "question": question,
         "extraits": extraits}

    orchestrateur = get_orchestrator(apprenant)
    # Le parcours ne facture pas : l'apprenant n'a rien demandé.
    facture = origine != AjoutDeFiche.PARCOURS
    reponse = orchestrateur.answer_question(invite, sans_quota=not facture)
    contenu = reponse.get("answer") or reponse.get("reponse") or ""

    return AjoutDeFiche.objects.create(
        fiche=fiche_de(apprenant, competence),
        question=question, origine=origine,
        section_visee=section_visee, niveau_vise=niveau_vise,
        contenu=contenu, sources=sources,
    )
