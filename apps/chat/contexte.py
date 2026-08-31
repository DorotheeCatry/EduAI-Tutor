"""
Le contexte que le tuteur reçoit, et celui qu'il ne reçoit pas.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétences concernées : C17 (E4) ; C13 (E3) ; C9 (E2)

Ce module construit, côté serveur, ce que le panneau du tuteur transmet au
modèle. Il est **le seul endroit** où cette composition a lieu : la page l'écrit
dans un bloc JSON, le panneau le lit pour l'afficher à l'apprenant *et* pour
composer sa requête. Bannière et requête lisent donc la même source, et un
contexte absent se voit à l'écran au lieu de manquer en silence.

**Trois principes, dans l'ordre où ils comptent.**

1. **Ce qui est transmis est montré.** Confier le code de quelqu'un à un modèle
   sans le lui dire n'est pas acceptable, et l'afficher évite les malentendus
   quand la réponse porte sur autre chose que ce qu'il croyait.

2. **La bonne réponse d'un quiz n'est JAMAIS transmise.** Un tuteur qui connaît
   la réponse attendue transforme un instrument de mesure en distributeur de
   solutions. Voir la décision 029, et le test qui échoue si `correct_answer`
   réapparaît ici.

3. **Tout est borné.** Un cours entier plus un historique saturerait la fenêtre
   du modèle et se paierait à chaque appel. Les bornes sont ci-dessous, en
   caractères, et chaque troncature est signalée à l'apprenant par un « … ».
"""

#: Bornes, en caractères. Elles sont ici, en clair, plutôt que dispersées dans
#: les appels : c'est ce qui permet de dire ce que coûte une question.
BORNES = {
    "section_de_cours": 2000,
    "enonce_d_exercice": 800,
    "code_saisi": 2000,
    "message_d_erreur": 500,
    "question_de_quiz": 1000,
    "echange_d_historique": 500,
}

#: Nombre d'échanges précédents transmis avec la question.
#:
#: Deux : de quoi comprendre « et pourquoi ? » sans transporter la conversation
#: entière. L'historique n'est pas persisté — il vit dans la page et disparaît
#: en la quittant.
ECHANGES_TRANSMIS = 2


def borner(texte, cle):
    """
    Tronque un texte à la borne nommée, en signalant la troncature.

    Compétence visée : C10 (épreuve E3)

    Choix : un « … » visible plutôt qu'une coupure nette. Motivation :
    l'apprenant voit ce que le tuteur reçoit ; une coupure silencieuse lui
    ferait croire que le tuteur a tout lu.
    """
    if texte is None:
        return ""
    texte = str(texte).strip()
    limite = BORNES[cle]
    if len(texte) <= limite:
        return texte
    return texte[:limite].rstrip() + "…"


def contexte_de_cours(cours, section=None):
    """
    Contexte d'une page de cours : le cours, et la SECTION lue.

    Compétence visée : C10 (épreuve E3)

    Choix : la section seule, jamais le cours entier. Motivation : c'est
    l'unité sur laquelle on bloque, et transporter le cours complet à chaque
    question saturerait la fenêtre pour du texte que l'apprenant ne regarde
    pas. La borne est de 2 000 caractères.
    """
    contexte = {
        "page": "cours",
        "resume": cours.title,
        "elements": [
            {"libelle": "Cours", "valeur": cours.title},
        ],
        "charge": {"cours": cours.title},
    }

    if section is not None:
        contexte["resume"] = f"{cours.title} — {section.title}"
        contexte["elements"].append(
            {"libelle": "Section lue", "valeur": section.title})
        contexte["charge"]["section"] = section.title
        contexte["charge"]["contenu"] = borner(
            getattr(section, "content", ""), "section_de_cours")

    return contexte


def contexte_d_exercice(exercice, code_saisi=None, derniere_erreur=None):
    """
    Contexte d'une page d'exercice : l'énoncé, le code, la dernière erreur.

    Compétence visée : C10 (épreuve E3)

    Choix : la solution attendue de l'exercice n'est **pas** transmise, pour la
    même raison que la bonne réponse d'un quiz — un tuteur qui l'a la donne, et
    l'exercice cesse de mesurer une production (décision 029).
    """
    contexte = {
        "page": "exercice",
        "resume": exercice.title,
        "elements": [
            {"libelle": "Exercice", "valeur": exercice.title},
        ],
        "charge": {
            "exercice": exercice.title,
            "enonce": borner(exercice.description, "enonce_d_exercice"),
        },
    }

    if code_saisi:
        contexte["elements"].append(
            {"libelle": "Votre code", "valeur": "tel qu'il est actuellement saisi"})
        contexte["charge"]["code"] = borner(code_saisi, "code_saisi")

    if derniere_erreur:
        contexte["elements"].append(
            {"libelle": "Dernière erreur", "valeur": borner(derniere_erreur, "message_d_erreur")})
        contexte["charge"]["erreur"] = borner(derniere_erreur, "message_d_erreur")

    return contexte


def contexte_de_quiz(question, reponse_donnee=None):
    """
    Contexte d'une question de quiz — SANS la bonne réponse.

    Compétence visée : C10 (épreuve E3)
    Compétences concernées : C17 (E4), C21 (E5)

    **C'est le refus qui compte ici.** `question` est le dictionnaire produit
    par le générateur : il porte `question`, `options`, `explanation` et
    `correct_answer`. Les trois premiers champs peuvent aider ; le quatrième
    donnerait la réponse.

    Un tuteur qui connaît la réponse attendue la donne — c'est ce qu'on lui
    demande de faire, aider — et le quiz cesse de mesurer quoi que ce soit. Le
    dispositif de progression tout entier repose sur des résultats mesurés
    (décision 028) : une seule fuite ici les rendrait tous douteux.

    `explanation` est écartée pour la même raison : elle contient l'explication
    de la bonne réponse, donc la bonne réponse.
    """
    return {
        "page": "quiz",
        "resume": borner(question.get("question", ""), "question_de_quiz")[:60] + "…",
        "elements": [
            {"libelle": "Question en cours", "valeur": borner(
                question.get("question", ""), "question_de_quiz")},
            {"libelle": "Votre réponse", "valeur": reponse_donnee or "aucune pour l'instant"},
        ],
        "charge": {
            "question": borner(question.get("question", ""), "question_de_quiz"),
            "options": list(question.get("options", [])),
            "reponse_donnee": reponse_donnee or "",
            # Ni `correct_answer`, ni `explanation`. Voir la docstring.
        },
    }


def contexte_general():
    """
    Contexte des pages qui n'en ont pas : accueil, profil, le reste.

    Compétence visée : C10 (épreuve E3)

    Rendre une structure plutôt que `None` : le panneau affiche alors « aucun
    contexte » explicitement, au lieu de laisser une bannière vide dont on ne
    saurait pas si elle est absente ou en panne.
    """
    return {
        "page": "general",
        "resume": "",
        "elements": [],
        "charge": {},
    }


def composer_l_invite(message, contexte, historique=None):
    """
    Compose ce qui part au modèle : le contexte, l'historique, puis la question.

    Compétence visée : C10 (épreuve E3)

    Choix : la question de l'apprenant vient EN DERNIER. Motivation : c'est ce
    à quoi le modèle doit répondre, et un contexte long placé après elle la
    noierait.

    Choix : le contexte est étiqueté, pas fondu dans une phrase. Motivation :
    ce qui est lisible pour un relecteur l'est aussi pour le modèle, et cela
    rend vérifiable, à l'œil, que rien d'autre n'est transmis.
    """
    morceaux = []

    if contexte and contexte.get("charge"):
        morceaux.append("Contexte de travail de l'apprenant :")
        for cle, valeur in contexte["charge"].items():
            if valeur in (None, "", []):
                continue
            morceaux.append(f"- {cle} : {valeur}")
        morceaux.append("")

    for echange in (historique or [])[-ECHANGES_TRANSMIS:]:
        question = borner(echange.get("question"), "echange_d_historique")
        reponse = borner(echange.get("reponse"), "echange_d_historique")
        if question:
            morceaux.append(f"Question précédente : {question}")
        if reponse:
            morceaux.append(f"Réponse précédente : {reponse}")

    if morceaux:
        morceaux.append("")
    morceaux.append(f"Question : {message}")

    return "\n".join(morceaux)
