"""
Reconnaître un échange courant, et y répondre sans déranger le modèle.

Compétence visée : C10 (épreuve E3) — agents et interactions
Compétences concernées : C13 (E3) — quotas ; C17 (E4)

Dire « ça va ? » à Koda dans une page de cours produisait un cours entier sur
la compétence en question : la demande partait dans la recherche documentaire,
et l'invite ordonnait de répondre en s'appuyant sur la documentation trouvée.
Le modèle obéissait. La réponse était ensuite versée dans la fiche de
l'apprenant, où elle voisinait avec ses vraies questions.

Deux défauts distincts, réparés ici :

1. **La réponse n'était pas proportionnée à la demande.** Une politesse appelle
   une phrase, pas un chapitre.
2. **N'importe quel échange finissait dans la fiche.** Une fiche doit garder ce
   que l'apprenant a cherché à comprendre, pas les bonjours.

Choix : une réponse assemblée localement, jamais engendrée par le modèle.
Motivation : c'est déjà la règle des salutations de Koda (`salutation.py`), et
elle vaut pour les mêmes raisons. Le quota d'abord — dépenser une génération
pour dire bonjour serait absurde. La justesse ensuite — une phrase assemblée ne
peut pas partir dans un cours au hasard. Et la dépense enfin : répondre sans
appeler le fournisseur n'ouvre aucun chemin de dépense non compté, ce que le
projet a déjà eu à corriger deux fois.

Choix : la reconnaissance est volontairement ÉTROITE. Motivation : se tromper
dans un sens coûte une politesse traitée comme une question — bénin. Se tromper
dans l'autre coûte une vraie question renvoyée d'un « ça marche ! » et jamais
enregistrée. Le doute penche donc systématiquement du côté de la vraie
question.
"""

import random
import re
import unicodedata

from django.utils.translation import gettext as _

#: Au-delà, on ne parle plus de politesse. Une vraie question tient rarement en
#: moins de mots, mais une politesse dépasse rarement ce seuil.
MOTS_AU_PLUS = 6

#: Ce qui, à lui seul, désigne une question de fond : un apprenant qui écrit du
#: code, nomme une notion ou demande une explication ne fait pas la
#: conversation. Le `s?` couvre les pluriels — « les dictionnaires » doit
#: compter autant que « un dictionnaire ».
#:
#: Les mots interrogatifs n'y figurent PAS, bien qu'ils annoncent une question :
#: « comment vas-tu » en est une aussi. La correspondance entière des tournures
#: suffit à les distinguer, et les inscrire ici ferait de cette politesse une
#: demande de cours.
INDICES_TECHNIQUES = re.compile(
    r"[()\[\]{}=<>]|`|\.py\b|"
    r"\b(def|class|import|for|while|lambda|return|print|list|dict|set|tuple|"
    r"str|int|float|bool|none|error|exception|"
    r"erreurs?|listes?|dictionnaires?|ensembles?|boucles?|fonctions?|"
    r"variables?|methodes?|classes?|modules?|exemples?|codes?|"
    r"explique|expliques|explication|montre|donne|difference|differences)\b"
)

#: Les tournures reconnues, en correspondance ENTIÈRE et non en simple début.
#:
#: Choix : `fullmatch`, et non `match`. Motivation mesurée : avec un simple
#: début de ligne, « ça va marcher ? » passait pour un « ça va ? » et « salut,
#: ça déconne » pour un bonjour. Les deux sont de vraies demandes. Exiger que
#: le message ENTIER soit une politesse ramène le doute du bon côté : ce qui
#: dépasse la formule est traité comme une question.
#:
#: Les queues optionnelles — un « koda », un « toi » — sont écrites une fois
#: pour toutes dans QUEUES, plutôt que répétées dans chaque motif.
QUEUES = r"(?: (?:koda|toi|a toi|tout le monde|les amis))?"

TOURNURES_COURANTES = tuple(re.compile(motif + QUEUES) for motif in (
    r"(?:re)?(?:salut|bonjour|bonsoir|coucou|hello|hey|yo|hi|wesh)",
    r"(?:comment )?(?:ca va|ca roule|ca gaze|ca farte)(?: bien)?",
    r"comment (?:vas tu|allez vous)",
    r"(?:tu vas|vous allez) bien",
    r"quoi de neuf",
    r"(?:merci|thanks|thx)(?: beaucoup| bien| infiniment)?",
    r"(?:ok|okay|d accord|daccord|tres bien|parfait|nickel|super|cool|genial|"
    r"top|bravo|bien vu|impeccable|ca marche|compris|je vois)",
    r"(?:tu es la|t es la|tu m entends|il y a quelqu un)",
    r"(?:a plus|a bientot|au revoir|bye|ciao|bonne nuit|bonne journee|"
    r"bonne soiree)",
    r"(?:qui es tu|qui est tu|comment tu t appelles|c est quoi ton nom|"
    r"tu t appelles comment)",
))


def _aplatir(message: str) -> str:
    """
    Ramène un message à sa forme comparable : sans accents ni ponctuation.

    Compétence visée : C10 (épreuve E3)

    Choix : aplatir plutôt que multiplier les variantes dans les expressions.
    Motivation : « Ça va ? », « ca va », « CA VA !! » sont le même message, et
    une liste qui devrait les prévoir toutes finirait par en oublier.
    """
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", message.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sans_accents)).strip()


def est_un_echange_courant(message: str) -> bool:
    """
    Dit si un message relève de la conversation plutôt que du cours.

    Compétence visée : C10 (épreuve E3)

    Trois conditions, toutes nécessaires : le message est court, il ne porte
    aucun indice technique, et il commence par une tournure reconnue. Une seule
    manquante, et le message repart vers la vraie réponse documentée.
    """
    if not message or not message.strip():
        return False

    aplati = _aplatir(message)
    if not aplati or len(aplati.split()) > MOTS_AU_PLUS:
        return False
    if INDICES_TECHNIQUES.search(aplati):
        return False
    return any(tournure.fullmatch(aplati) for tournure in TOURNURES_COURANTES)


def _repertoire(pseudo: str) -> dict[str, list[str]]:
    """
    Les réponses de Koda, par famille d'échange.

    Compétence visée : C17 (épreuve E4)

    Elles portent le pseudo de l'apprenant et le ton de Koda, et **toutes
    ramènent au travail** : c'est une conversation dans une page de cours, pas
    un salon de discussion.
    """
    return {
        "salutation": [
            _("Salut %(p)s ! Sur quoi on attaque ?") % {"p": pseudo},
            _("Te voilà, %(p)s. Une question sur le cours ?") % {"p": pseudo},
            _("Bonjour %(p)s ! Dis-moi ce qui coince.") % {"p": pseudo},
        ],
        "forme": [
            _("Impeccable, et prêt à répondre. Et toi, ça avance ?"),
            _("Très bien ! J'attendais que tu me demandes quelque chose."),
            _("Au top. Pose-moi une vraie question, pour voir."),
        ],
        "remerciement": [
            _("Avec plaisir, %(p)s.") % {"p": pseudo},
            _("Quand tu veux. J'avais parié avec les autres Koda que tu y arriverais."),
            _("De rien ! Si un point reste flou, dis-le."),
        ],
        "acquiescement": [
            _("Parfait. On continue ?"),
            _("Noté. Une autre question ?"),
            _("Très bien. Je reste là."),
        ],
        "presence": [
            _("Toujours là, %(p)s.") % {"p": pseudo},
            _("Présent. Je t'écoute."),
        ],
        "adieu": [
            _("À bientôt, %(p)s !") % {"p": pseudo},
            _("Bonne suite, %(p)s. Je garde ta fiche au chaud.") % {"p": pseudo},
        ],
        "identite": [
            _("Koda, ton tuteur. Je vois le cours que tu lis, alors demande-moi "
              "ce que tu veux dessus."),
        ],
    }


def _famille(message: str) -> str:
    """Range un message dans une famille de réponse."""
    aplati = _aplatir(message)
    if re.match(r"^(qui es tu|qui est tu|comment tu t appelles|c est quoi ton "
                r"nom|tu t appelles comment)", aplati):
        return "identite"
    if re.match(r"^(a plus|au revoir|bye|ciao|bonne nuit|bonne journee)", aplati):
        return "adieu"
    if re.match(r"^(merci|thanks|thx)", aplati):
        return "remerciement"
    if re.match(r"^(tu es la|t es la|tu m entends|il y a quelqu un)", aplati):
        return "presence"
    if re.match(r"^(ca|comment) (va|vas tu|ca va)|^(tu vas bien|vous allez bien|"
                r"ca roule|ca gaze|quoi de neuf|ca farte)", aplati):
        return "forme"
    if re.match(r"^(salut|bonjour|bonsoir|coucou|hello|hey|yo|hi|wesh)", aplati):
        return "salutation"
    return "acquiescement"


def repondre(message: str, pseudo: str) -> str:
    """
    Rend la réponse de Koda à un échange courant.

    Compétence visée : C17 (épreuve E4)

    Choix : plusieurs formulations par famille, tirées au sort. Motivation : un
    tuteur qui répond toujours la même phrase cesse très vite de ressembler à
    quelqu'un — et l'apprenant cesse de lui parler.
    """
    return random.choice(_repertoire(pseudo)[_famille(message)])
