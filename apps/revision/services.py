"""
Ce que l'apprenant a réellement manqué, et sur quoi il se trompe le plus.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C20 (E5) — restitution ; C13 (E3) — quotas ; C21 (E5)

Deux services, une même règle : **ne rien engendrer**.

Rejouer une notion en demandant au modèle d'autres questions mesure la notion,
pas l'erreur. Or l'apprenant qui vient ici veut revoir **ce qu'il a manqué** —
la question exacte, et la réponse qu'il avait donnée. Ces deux éléments sont
déjà en base (`UserMistake`), avec la bonne réponse.

Conséquence heureuse : cette révision **ne coûte aucune génération**. Elle ne
touche pas le fournisseur, donc pas le quota, et reste disponible quand le
quota est épuisé — c'est-à-dire exactement quand l'apprenant a beaucoup
travaillé.
"""

import random
from collections import Counter

from apps.agents.agent_watcher import UserMistake
from apps.courses.views import render_markdown

#: Au-delà, une séance de révision cesse d'être une séance.
QUESTIONS_AU_PLUS = 20

#: Les teintes du camembert, dans l'ordre. Elles viennent du thème : vert
#: primaire, bleu primaire, puis des variantes assez espacées pour rester
#: distinguables. La couleur ne porte jamais seule l'information — chaque part
#: est aussi nommée dans la légende ET dans le tableau qui suit.
TEINTES = ("#4CAF50", "#3B82F6", "#E0C868", "#F87171", "#A78BFA",
           "#22D3EE", "#FB923C", "#94A3B8")


def _cle_de_notion(erreur):
    """Rend le couple (valeur transmissible, intitulé) d'une erreur."""
    if erreur.competence_id:
        return erreur.competence.code, erreur.competence.intitule
    return erreur.topic, erreur.topic


def erreurs_a_rejouer(utilisateur, notions=None, limite=QUESTIONS_AU_PLUS):
    """
    Rend les questions réellement manquées, prêtes à être reposées.

    Compétence visée : C17 (épreuve E4)

    Chaque entrée porte la question telle qu'elle a été posée, et **deux**
    propositions : la bonne réponse, et celle que l'apprenant avait donnée.
    Choix : ces deux-là et rien d'autre. Motivation : inventer des distracteurs
    demanderait au modèle de compléter une question qu'il n'a pas écrite, et
    produirait des choix dont personne ne garantit qu'ils sont faux. Les deux
    réponses en base sont vraies : l'une est correcte, l'autre a réellement été
    donnée. C'est le distracteur le plus utile qui soit — le sien.

    Choix : l'ordre des propositions est tiré au sort à chaque affichage.
    Motivation : sans cela, la bonne réponse occuperait toujours la même place
    et la révision mesurerait la position, pas la connaissance.

    `notions` filtre sur les codes de compétence ou les sujets libres cochés ;
    vide, tout est repris — c'est le « quiz général sur tout ».
    """
    lignes = (UserMistake.objects
              .filter(user=utilisateur, reviewed=False)
              .select_related("competence")
              .order_by("-timestamp"))

    retenues = []
    for erreur in lignes:
        valeur, intitule = _cle_de_notion(erreur)
        if notions and valeur not in notions:
            continue
        bonne = (erreur.correct_answer or "").strip()
        donnee = (erreur.user_answer or "").strip()
        # Sans les deux réponses, il n'y a pas de question à reposer : on
        # l'écarte plutôt que d'afficher un choix unique dont la réponse est
        # évidente.
        if not bonne or not donnee or bonne == donnee:
            continue
        propositions = [bonne, donnee]
        random.shuffle(propositions)
        retenues.append({
            "id": erreur.id,
            "question": erreur.question,
            # Une question de quiz porte souvent un bloc de code : elle est du
            # Markdown, et s'affichait avec ses accents graves.
            "question_html": render_markdown(erreur.question),
            "propositions": propositions,
            "bonne_reponse": bonne,
            "notion": intitule,
            "pose_le": erreur.timestamp,
        })
        if len(retenues) >= limite:
            break
    return retenues


def corriger(utilisateur, reponses):
    """
    Corrige une séance de révision et marque comme revues celles qui sont sues.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C20 (E5)

    `reponses` associe l'identifiant d'une erreur à la proposition choisie.

    Choix : ne marquer « revue » qu'une erreur **effectivement corrigée**.
    Motivation : `reviewed` existait depuis l'origine et n'était écrit nulle
    part — les vingt-neuf erreurs de la base le portaient toutes à faux. Un
    drapeau qu'on lève au seul fait d'avoir affiché la question ne dirait rien
    de plus que la date de la question elle-même.
    """
    erreurs = {e.id: e for e in UserMistake.objects.filter(
        user=utilisateur, id__in=list(reponses))}

    corrigees, manquees = [], []
    for identifiant, choix in reponses.items():
        erreur = erreurs.get(identifiant)
        if erreur is None:
            continue
        _, intitule = _cle_de_notion(erreur)
        entree = {"question": erreur.question,
                  "question_html": render_markdown(erreur.question),
                  "notion": intitule,
                  "bonne_reponse": (erreur.correct_answer or "").strip(),
                  "choix": choix}
        if choix.strip() == (erreur.correct_answer or "").strip():
            corrigees.append(entree)
        else:
            manquees.append(entree)

    if corrigees:
        UserMistake.objects.filter(
            user=utilisateur,
            id__in=[e.id for e in erreurs.values()
                    if (e.correct_answer or "").strip()
                    == reponses.get(e.id, "").strip()],
        ).update(reviewed=True)

    return {"corrigees": corrigees, "manquees": manquees,
            "total": len(corrigees) + len(manquees)}


def repartition_des_erreurs(utilisateur):
    """
    Rend la part de chaque notion dans les erreurs, prête à être dessinée.

    Compétence visée : C20 (épreuve E5) — restitution
    Compétence concernée : C13 (E3) — accessibilité

    Rend les parts avec leur pourcentage, leur teinte et le tracé SVG de leur
    secteur. Le camembert est calculé ICI, côté serveur, et non par une
    bibliothèque de graphiques chargée depuis un CDN : huit parts au plus, un
    peu de trigonométrie, aucune dépendance de plus à tenir ni à charger.

    Le tracé n'est qu'une des deux restitutions : le gabarit affiche aussi un
    tableau à en-têtes, qui dit les mêmes nombres. Un graphique qu'un lecteur
    d'écran ne peut pas restituer n'informe que ceux qui voient.
    """
    import math

    comptes = Counter()
    for erreur in (UserMistake.objects
                   .filter(user=utilisateur)
                   .select_related("competence")):
        comptes[_cle_de_notion(erreur)[1]] += 1

    total = sum(comptes.values())
    if not total:
        return {"total": 0, "parts": []}

    parts = []
    angle = -math.pi / 2          # on commence en haut, comme une horloge
    rayon, centre = 60.0, 70.0
    for rang, (notion, nombre) in enumerate(comptes.most_common()):
        portion = nombre / total
        fin = angle + portion * 2 * math.pi
        grand_arc = 1 if portion > 0.5 else 0
        depart = (centre + rayon * math.cos(angle), centre + rayon * math.sin(angle))
        arrivee = (centre + rayon * math.cos(fin), centre + rayon * math.sin(fin))
        # Une part unique ne se dessine pas par un arc : ses deux extrémités
        # se confondent et le chemin serait vide. On trace alors le disque.
        if portion >= 0.999:
            trace = (f"M {centre} {centre - rayon} "
                     f"A {rayon} {rayon} 0 1 1 {centre - 0.01} {centre - rayon} Z")
        else:
            trace = (f"M {centre} {centre} L {depart[0]:.2f} {depart[1]:.2f} "
                     f"A {rayon} {rayon} 0 {grand_arc} 1 "
                     f"{arrivee[0]:.2f} {arrivee[1]:.2f} Z")
        parts.append({
            "notion": notion,
            "erreurs": nombre,
            "pourcentage": round(100 * portion),
            "teinte": TEINTES[rang % len(TEINTES)],
            "trace": trace,
        })
        angle = fin
    return {"total": total, "parts": parts}
