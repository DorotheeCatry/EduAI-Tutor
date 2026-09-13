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

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.utils import translation


class LangueDeLApprenant:
    """
    Active la langue enregistrée sur le compte, pour chaque requête.

    Compétence visée : C17 (épreuve E4)

    Cet intergiciel doit être déclaré **après** `AuthenticationMiddleware` :
    avant lui, ni `request.user` ni `request.auser` n'existent, et la
    préférence serait illisible. Il doit également venir après
    `LocaleMiddleware`, dont il remplace la décision quand un compte exprime un
    choix.

    **Il sait fonctionner dans une chaîne asynchrone, et ce n'est pas un
    détail de confort.** Django compose sa chaîne de bas en haut
    (`BaseHandler.load_middleware`, boucle sur `reversed(MIDDLEWARE)`) avec
    cette règle :

        elif not handler_is_async and middleware_can_sync:
            middleware_is_async = False

    Une seule couche purement synchrone rend donc synchrone **tout ce qui la
    surmonte**. Celle-ci l'était, et elle est déclarée au milieu de la liste :
    l'application, pourtant servie en ASGI, exécutait en réalité toute la
    partie haute de sa chaîne en mode synchrone — sessions, langue, requêtes
    communes, CSRF, sécurité et service des fichiers statiques compris.

    Le symptôme visible était ailleurs : Django avertissait que les fichiers
    statiques étaient matérialisés en mémoire au lieu d'être diffusés
    (incident 023). La cause était ici.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        # Django décide du mode de chaque couche à l'initialisation. Sans ce
        # marquage, il croirait celle-ci synchrone et enroberait la chaîne.
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def __call__(self, request):
        if iscoroutinefunction(self):
            return self.__acall__(request)
        self._appliquer(request, self._langue_du_compte(request))
        return self.get_response(request)

    async def __acall__(self, request):
        self._appliquer(request, await self._langue_du_compte_async(request))
        return await self.get_response(request)

    @staticmethod
    def _appliquer(request, langue):
        """
        Active la langue trouvée, et l'annonce à la page.

        Compétence visée : C17 (épreuve E4), C13 (E3) — accessibilité

        `request.LANGUAGE_CODE` est ce que lisent les gabarits par
        `{% get_current_language %}`, et donc l'attribut `lang` de la balise
        <html>. Ne pas le mettre à jour laisserait un lecteur d'écran annoncer
        la page dans la mauvaise langue, alors même que le texte affiché serait
        traduit.
        """
        if langue:
            translation.activate(langue)
            request.LANGUAGE_CODE = langue

    async def _langue_du_compte_async(self, request):
        """
        Comme `_langue_du_compte`, mais sans requête synchrone à la base.

        Compétence visée : C17 (épreuve E4), C13 (E3)

        Choix : `await request.auser()` et non `request.user`. Motivation :
        `request.user` est un objet paresseux dont la résolution interroge la
        base. Y toucher depuis une pile asynchrone lève
        `SynchronousOnlyOperation`. `auser`, posé par `AuthenticationMiddleware`
        à côté de `user`, est la forme attendue ici.
        """
        if not hasattr(request, "auser"):
            # Chaîne où l'authentification n'a pas été posée : on ne suppose
            # rien et on laisse `LocaleMiddleware` décider.
            return None
        return self._langue_utilisable(await request.auser())

    def _langue_du_compte(self, request):
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
        return self._langue_utilisable(getattr(request, "user", None))

    @staticmethod
    def _langue_utilisable(utilisateur):
        """
        Rend la langue d'un compte si elle est exploitable, sinon `None`.

        Compétence visée : C17 (épreuve E4)

        Partagée par les deux modes : la règle de décision ne doit exister
        qu'une fois, sans quoi les chemins synchrone et asynchrone finiraient
        par ne plus dire la même chose.
        """
        if utilisateur is None or not utilisateur.is_authenticated:
            return None

        langue = getattr(utilisateur, "language_preference", None)
        if not langue:
            return None

        from django.conf import settings

        if langue not in dict(settings.LANGUAGES):
            return None

        return langue
