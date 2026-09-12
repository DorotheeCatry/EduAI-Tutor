"""
Vues du tuteur : le panneau contextuel et son point d'envoi.

Compétence visée : C10 (épreuve E3) — intégration du modèle
Compétences concernées : C17 (E4) ; C13 (E3) ; C9 (E2)
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.agents.agent_orchestrator import get_orchestrator
from apps.quotas.service import QuotaDepasse, etat

from .actions import invite_de_l_action
from .contexte import composer_l_invite
from .echange_courant import est_un_echange_courant, repondre


@require_POST
@login_required
def send_message(request):
    """
    Répond à une question du tuteur, avec le contexte de la page courante.

    Compétence visée : C10 (épreuve E3)
    Compétences concernées : C9 (E2) — quotas ; C13 (E3) — CSRF

    Choix : `@csrf_exempt` est RETIRÉ, remplacé par `@require_POST`.
    Motivation : cette vue déclenche un appel facturé et décompte le quota du
    compte connecté. Sans protection CSRF, n'importe quelle page tierce ouverte
    dans le navigateur de l'apprenant pouvait épuiser son quota à son insu.
    C'est la deuxième occurrence du même défaut dans ce projet, après la
    soumission de quiz — consignée à ce titre (réserve 14).

    Choix : le contexte arrive du client, mais **ce qui en est fait est décidé
    ici**. Motivation : le client ne peut pas demander plus que ce que le
    serveur compose — il envoie ce que la page a écrit, et
    `composer_l_invite` en fait une invite dont la forme est fixée côté
    serveur.
    """
    try:
        donnees = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'corps de requête illisible'}, status=400)

    message = (donnees.get('message') or '').strip()
    action = (donnees.get('action') or '').strip()
    contexte = donnees.get('contexte') or {}
    historique = donnees.get('historique') or []

    # Une action préformée remplace le message ; un code inconnu est refusé
    # plutôt que traité comme une question libre.
    if action:
        invite = invite_de_l_action(action)
        if invite is None:
            return JsonResponse({'error': 'action inconnue'}, status=400)
        message = invite

    if not message:
        return JsonResponse({'error': 'message vide'}, status=400)

    # Une politesse reçoit une phrase, sans appeler le modèle.
    #
    # Compétence visée : C10 (épreuve E3), C13 (E3)
    # Choix : le même raccourci que la page de cours (décision 044), posé ici
    # aussi. Motivation : il n'existait que sur `courses:enrichir`, si bien que
    # le même « bonjour » recevait une phrase dans une page de cours et un
    # développement facturé dans le panneau flottant — qui, lui, est présent
    # sur toutes les pages. Un dispositif qui ne tient que sur l'une des deux
    # portes d'entrée ne tient pas.
    #
    # Placé APRÈS la résolution des actions, délibérément : une action
    # préformée a déjà remplacé `message` par une invite complète, qui n'est
    # pas une politesse et doit partir au modèle.
    if not action and est_un_echange_courant(message):
        return JsonResponse({
            'reponse': repondre(message, request.user.username),
            'horodatage': timezone.localtime().strftime('%H:%M'),
            'quota': etat(request.user),
        })

    orchestrateur = get_orchestrator(request.user)

    # Le décompte a lieu dans `answer_question`, comme pour la génération de
    # cours et de quiz — vérifié, non supposé : c'est ce chemin-là qui dépense.
    try:
        resultat = orchestrateur.answer_question(
            composer_l_invite(message, contexte, historique)
        )
    except QuotaDepasse as depassement:
        return JsonResponse(
            {
                'reponse': depassement.message,
                'horodatage': timezone.localtime().strftime('%H:%M'),
                'quota': etat(request.user),
            },
            status=429,
        )

    if resultat.get('success'):
        reponse = resultat['answer']
    else:
        reponse = _("Désolé, je n'ai pas pu traiter votre question : %(motif)s") % {
            "motif": resultat.get('error', _('erreur inconnue'))
        }

    return JsonResponse({
        'reponse': reponse,
        # L'heure réelle du serveur. Elle valait « 12:34:56 », en dur, sur tous
        # les messages — septième foyer de données fabriquées du projet
        # (réserve 12).
        'horodatage': timezone.localtime().strftime('%H:%M'),
        'quota': etat(request.user),
    })
