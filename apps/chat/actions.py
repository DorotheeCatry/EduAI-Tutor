"""
Les actions contextuelles : des questions qu'on n'a pas à taper.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétence concernée : C17 (E4)

Ce ne sont pas des capacités nouvelles du modèle : chaque action envoie une
invite préformée, avec le contexte courant, aux agents qui existent déjà. C'est
du câblage entre composants, et c'est ce qui rend l'architecture multi-agents
lisible par l'usage plutôt que par un schéma.

Les invites sont ici, en données, et non dispersées dans les gabarits : c'est
ce qui permet de les relire toutes d'un coup, et de vérifier qu'aucune ne
demande au tuteur de donner une solution.
"""

from django.utils.translation import gettext_lazy as _

#: Actions proposées sous une section de cours.
ACTIONS_DE_COURS = [
    {
        "code": "developper",
        "libelle": _("Développe cette partie"),
        "invite": "Développe la section ci-dessus plus en profondeur, en restant "
                  "sur le même sujet. N'introduis pas de notion nouvelle sans "
                  "l'expliquer.",
    },
    {
        "code": "cas-complexe",
        "libelle": _("Un cas plus complexe"),
        "invite": "Donne un cas limite ou une exception que la section ci-dessus "
                  "ne traite pas, et explique pourquoi il pose problème.",
    },
    {
        "code": "reformuler",
        "libelle": _("Je ne comprends pas"),
        "invite": "Reformule la section ci-dessus sous un autre angle, avec une "
                  "analogie différente. Ne répète pas la même explication.",
    },
    {
        "code": "exemple",
        "libelle": _("Montre-moi un exemple"),
        "invite": "Donne un exemple de code exécutable illustrant la section "
                  "ci-dessus, commenté ligne à ligne.",
    },
]

#: Actions proposées sur un exercice.
#:
#: Aucune ne demande la solution. « Un indice sans la solution » le dit au
#: modèle explicitement : un tuteur qui résout l'exercice à la place de
#: l'apprenant supprime ce que l'exercice mesure (décision 029).
ACTIONS_D_EXERCICE = [
    {
        "code": "pourquoi-echec",
        "libelle": _("Pourquoi mon code échoue"),
        "invite": "Explique pourquoi le code ci-dessus échoue, en te fondant sur "
                  "le message d'erreur. NE DONNE PAS le code corrigé : nomme la "
                  "cause, et laisse l'apprenant écrire la correction.",
    },
    {
        "code": "indice",
        "libelle": _("Un indice sans la solution"),
        "invite": "Donne UN indice pour avancer sur cet exercice. N'écris ni la "
                  "solution, ni un extrait de code qui la contienne. Oriente "
                  "vers la notion à mobiliser.",
    },
]

#: Actions proposées pendant un quiz.
#:
#: La bonne réponse n'étant pas transmise (décision 029), le tuteur ne peut pas
#: la donner même si on la lui demandait. Ces actions portent sur la
#: compréhension de l'énoncé, jamais sur la réponse.
ACTIONS_DE_QUIZ = [
    {
        "code": "clarifier",
        "libelle": _("Que demande cette question ?"),
        "invite": "Reformule la question ci-dessus pour la rendre plus claire. "
                  "NE DONNE PAS la réponse et n'indique pas quelle option est "
                  "correcte : tu ne la connais pas, et ce n'est pas ce qu'on te "
                  "demande.",
    },
]

ACTIONS_PAR_PAGE = {
    "cours": ACTIONS_DE_COURS,
    "exercice": ACTIONS_D_EXERCICE,
    "quiz": ACTIONS_DE_QUIZ,
    "general": [],
}


def actions_pour(page):
    """
    Rend les actions proposées sur une page donnée.

    Compétence visée : C10 (épreuve E3)
    """
    return ACTIONS_PAR_PAGE.get(page, [])


def invite_de_l_action(code):
    """
    Rend l'invite préformée d'une action, ou `None` si le code est inconnu.

    Compétence visée : C10 (épreuve E3)

    `None` plutôt qu'une invite par défaut : un code inconnu vient d'un
    formulaire modifié, et lui répondre par une invite générique reviendrait à
    accepter n'importe quoi.
    """
    for actions in ACTIONS_PAR_PAGE.values():
        for action in actions:
            if action["code"] == code:
                return action["invite"]
    return None
