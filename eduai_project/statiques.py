"""
Stockage des fichiers statiques collectés.

Compétence visée : C13 (épreuve E3) — mise en production
Compétence visée : C17 (épreuve E4) — application web
"""

from pathlib import Path

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.conf import settings
from whitenoise.middleware import WhiteNoiseMiddleware
from whitenoise.storage import CompressedManifestStaticFilesStorage


class StockageStatiquesTolerant(CompressedManifestStaticFilesStorage):
    """
    Stockage empreinté et compressé, tolérant aux références manquantes.

    Compétence visée : C13 (épreuve E3)

    Choix : une sous-classe plutôt qu'une option de configuration.
    Motivation : `manifest_strict` est un attribut de classe et non un
    paramètre d'initialisation — le déclarer dans `OPTIONS` lève une
    `TypeError` au premier `collectstatic`. La sous-classe est le seul point
    d'accroche prévu, et elle porte ici sa justification.

    Choix : `manifest_strict = False`. Motivation : par défaut, un gabarit qui
    référence un fichier absent du manifeste — une image supprimée, un script
    renommé — provoque une erreur 500 à l'affichage de la page. L'application
    en comporte, hérités de son développement initial. Une page dégradée, à
    laquelle une illustration manque, vaut mieux qu'une page morte pendant une
    démonstration.

    Ce que cette tolérance ne fait pas : elle ne masque rien au moment de la
    construction. `collectstatic` signale les fichiers manquants ; c'est
    seulement l'exécution qui cesse d'en faire une panne.
    """

    manifest_strict = False


def version_de_la_feuille(request):
    """
    Rend un suffixe de version pour la feuille de style, en développement.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5) — incidents

    En production, le stockage empreinte le nom du fichier
    (`tailwind.60e3e678.css`) : un changement de feuille change l'URL, et le
    navigateur va la rechercher. En développement, l'URL est fixe — le
    navigateur garde donc l'ancienne feuille en cache, et une modification de
    style n'apparaît pas. Le 03/09/2026, une couleur pourtant servie par le
    serveur est restée invisible à l'écran pour cette seule raison.

    Choix : la date de modification du fichier, et non un identifiant aléatoire.
    Motivation : elle ne change QUE lorsque la feuille change. Un identifiant
    tiré à chaque requête ferait retélécharger la feuille en permanence, ce qui
    masquerait le problème inverse — une feuille qui ne se reconstruit plus.

    Choix : vide hors développement. Motivation : l'empreinte y fait déjà ce
    travail, mieux ; ajouter un paramètre par-dessus n'ajouterait qu'un cache
    de plus à comprendre.
    """
    if not settings.DEBUG:
        return {"version_feuille": ""}

    feuille = Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css"
    try:
        return {"version_feuille": f"?v={int(feuille.stat().st_mtime)}"}
    except OSError:
        # Feuille absente : le gabarit s'en passe plutôt que d'échouer.
        return {"version_feuille": ""}


# ===========================================================================
# Le service des statiques dans une pile asynchrone
# ===========================================================================

async def _blocs_asynchrones(iterateur):
    """
    Rend, un par un et sans bloquer la boucle, les blocs d'un itérateur synchrone.

    Compétence visée : C13 (épreuve E3), C17 (E4)

    Les blocs sont ceux que `FileResponse` a déjà découpés — 4 096 octets. Cette
    fonction ne les recoupe pas, elle change seulement la façon de les tirer.

    Choix : tirer **un bloc par attente**, et non convertir l'itérateur entier.
    Motivation : c'est tout l'objet de cette couche. Django, lui, fait
    l'inverse — `for part in await sync_to_async(list)(...)` — c'est-à-dire
    qu'il matérialise le fichier complet en mémoire avant d'en envoyer le
    premier octet.

    Choix : `thread_sensitive=False`. Motivation : la lecture d'un fichier
    statique ne touche ni la base ni aucun état de requête. La contraindre au
    fil principal la sérialiserait avec tout le reste, ce qui annulerait le
    bénéfice recherché.
    """
    sentinelle = object()
    bloc_suivant = sync_to_async(next, thread_sensitive=False)

    while True:
        bloc = await bloc_suivant(iterateur, sentinelle)
        if bloc is sentinelle:
            return
        yield bloc


def rendre_le_flux_asynchrone(reponse):
    """
    Remplace l'itérateur synchrone d'une réponse en flux par un asynchrone.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    Rend la réponse telle quelle si elle n'est pas en flux, ou si son contenu
    est déjà asynchrone — la couche doit être sans effet là où il n'y a rien à
    faire.

    Détail qui compte : affecter `streaming_content` fait repasser Django par
    `_set_streaming_content`, qui tente `iter(valeur)`, échoue sur un
    générateur asynchrone, et bascule alors sur `aiter(valeur)` en posant
    `is_async = True`. C'est ce drapeau qui fait disparaître l'avertissement —
    on ne le fait pas taire, on rend vraie la condition qu'il signalait.
    """
    if not getattr(reponse, "streaming", False):
        return reponse

    contenu = reponse.streaming_content
    if hasattr(contenu, "__aiter__"):
        return reponse

    reponse.streaming_content = _blocs_asynchrones(iter(contenu))
    return reponse


class WhiteNoiseAsynchrone(WhiteNoiseMiddleware):
    """
    WhiteNoise, mais qui sert ses fichiers en flux dans une pile asynchrone.

    Compétence visée : C13 (épreuve E3) — mise en production
    Compétences concernées : C17 (E4) ; C21 (E5)

    **Le défaut corrigé.** L'application est servie en ASGI (`uvicorn
    eduai_project.asgi`), choix justifié dans `docker/entree-web.sh` : le projet
    déclare `ASGI_APPLICATION` et embarque Channels, et servir en WSGI ferait
    taire les WebSockets sans que rien ne le dise.

    WhiteNoise, lui, n'a **aucun chemin asynchrone** — vérifié sur le paquet
    6.12 installé, pas un seul `async def`. Il rend un `FileResponse` dont le
    contenu est un itérateur synchrone. Django le détecte, avertit, puis :

        for part in await sync_to_async(list)(self.streaming_content):

    Il **matérialise le fichier entier en mémoire** avant d'en envoyer le
    premier octet. Sur ce projet, les animations de Koda pèsent jusqu'à 1,4 Mo
    et le service tourne avec un seul travailleur.

    Constaté dans les journaux de l'hébergeur le 13/09/2026, déploiement
    `08e6a95f` :

        asgi.py:333: Warning: StreamingHttpResponse must consume synchronous
        iterators in order to serve them asynchronously.

    **Pourquoi une sous-classe de WhiteNoise et non une couche indépendante.**
    C'est la leçon de la première tentative, et elle mérite d'être écrite.

    Une couche posée au-dessus de WhiteNoise ne fonctionnait pas, et le code
    semblait pourtant juste. Django compose sa chaîne **de bas en haut**
    (`BaseHandler.load_middleware`, boucle sur `reversed(MIDDLEWARE)`) et
    applique cette règle :

        elif not handler_is_async and middleware_can_sync:
            middleware_is_async = False

    WhiteNoise n'étant pas asynchrone, tout ce qui se trouve au-dessus de lui
    **et accepte le mode synchrone** est instancié en synchrone. La couche
    était donc appelée par sa branche synchrone, où elle n'a rien à faire, et
    l'avertissement subsistait — sans qu'aucune erreur ne le signale.

    Déclarer `sync_capable = False` l'aurait forcée en asynchrone, au prix d'un
    `async_to_sync` sur **toute** requête d'une pile synchrone — les tests
    compris. Rendre WhiteNoise lui-même asynchrone est plus simple et plus
    sûr : la chaîne reste asynchrone de bout en bout, et une pile synchrone
    retrouve le comportement d'origine sans détour.

    **Ce que cette classe ne change pas.** La résolution du fichier, les
    en-têtes, le cache, la compression, l'empreinte : tout vient de
    `WhiteNoiseMiddleware`. Seule la façon dont les octets sont remis à Django
    change.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        super().__init__(get_response)
        # Django décide du mode de chaque couche à l'initialisation. Sans ce
        # marquage, il croirait celle-ci synchrone et l'envelopperait — ce qui
        # rendrait synchrone tout ce qui la traverse.
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def _fichier_demande(self, request):
        """
        Rend le fichier statique correspondant à la requête, ou None.

        Compétence visée : C13 (épreuve E3)

        Reprend à l'identique la résolution de `WhiteNoiseMiddleware.__call__`,
        `autorefresh` compris — c'est le mode de développement, où les fichiers
        sont cherchés à chaque requête au lieu d'être indexés au démarrage.
        """
        if self.autorefresh:
            return self.find_file(request.path_info)
        return self.files.get(request.path_info)

    def __call__(self, request):
        if iscoroutinefunction(self):
            return self.__acall__(request)
        # Chaîne synchrone : le comportement d'origine, sans détour. Un
        # itérateur synchrone y est exactement ce qu'il faut, et Django
        # n'avertit pas.
        return super().__call__(request)

    async def __acall__(self, request):
        fichier = self._fichier_demande(request)
        if fichier is not None:
            return rendre_le_flux_asynchrone(self.serve(fichier, request))
        return await self.get_response(request)
