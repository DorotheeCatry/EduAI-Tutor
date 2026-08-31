"""
Application de la langue choisie par l'apprenant à l'interface.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — accessibilité ; C19 (E5)

Pourquoi ce module existe : le champ `language_preference` existait depuis
l'origine, la page de profil proposait un sélecteur, la valeur était bien
enregistrée en base — et **rien ne la lisait pour l'interface**. Seul
l'orchestrateur d'agents la consultait, pour choisir la langue des quiz
générés. L'apprenant qui choisissait « Français » voyait donc son choix
accepté, stocké, et sans effet visible.

C'est le motif que ce projet documente depuis le premier incident : une action
et son effet qui ne coïncident pas. Ici, l'écart était particulièrement
trompeur, parce que le réglage n'était pas ignoré — il était utilisé ailleurs.

Choix : un intergiciel plutôt que la vue du profil qui poserait un cookie.
Motivation : la préférence est un attribut du compte, pas du navigateur. Posée
en cookie, elle ne suivrait pas l'apprenant d'un poste à l'autre, et se
perdrait au premier nettoyage du navigateur. Lue à chaque requête, elle vaut
partout où le compte est ouvert.

Choix : cet intergiciel s'ajoute à `LocaleMiddleware` au lieu de le remplacer.
Motivation : `LocaleMiddleware` sert les visiteurs non connectés — page de
connexion, inscription — en s'appuyant sur l'en-tête `Accept-Language` du
navigateur. Il reste donc utile, et c'est seulement quand un compte exprime une
préférence que celle-ci prend le pas.
"""

from django.utils import translation


class LangueDeLApprenant:
    """
    Active la langue enregistrée sur le compte, pour chaque requête.

    Compétence visée : C17 (épreuve E4)

    Cet intergiciel doit être déclaré **après** `AuthenticationMiddleware` :
    avant lui, `request.user` n'existe pas encore, et la préférence serait
    illisible. Il doit également venir après `LocaleMiddleware`, dont il
    remplace la décision quand un compte exprime un choix.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        langue = self._langue_du_compte(request)

        if langue:
            translation.activate(langue)
            # `request.LANGUAGE_CODE` est ce que lisent les gabarits par
            # `{% get_current_language %}`, et donc l'attribut `lang` de la
            # balise <html>. Ne pas le mettre à jour laisserait un lecteur
            # d'écran annoncer la page dans la mauvaise langue, alors même que
            # le texte affiché serait traduit.
            request.LANGUAGE_CODE = langue

        return self.get_response(request)

    @staticmethod
    def _langue_du_compte(request):
        """
        Rend la langue du compte, ou `None` s'il n'y en a pas d'utilisable.

        Compétence visée : C17 (épreuve E4)

        Choix : une langue inconnue est ignorée plutôt que d'échouer.
        Motivation : `LANGUAGES` peut changer — une langue retirée des
        réglages laisserait des comptes portant une valeur devenue invalide.
        Faire échouer la requête punirait l'apprenant pour un changement de
        configuration ; on retombe sur la langue négociée par le navigateur,
        et la page reste servie.
        """
        utilisateur = getattr(request, "user", None)
        if utilisateur is None or not utilisateur.is_authenticated:
            return None

        langue = getattr(utilisateur, "language_preference", None)
        if not langue:
            return None

        from django.conf import settings

        if langue not in dict(settings.LANGUAGES):
            return None

        return langue
