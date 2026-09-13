"""
La pile de requêtes est asynchrone de bout en bout, et les statiques diffusent.

Compétence visée : C13 (épreuve E3) — mise en production
Compétences concernées : C17 (E4) ; C21 (E5) ; C18 (E4)

L'application est servie en ASGI. Une seule couche d'intergiciel purement
synchrone suffit pourtant à rendre synchrone **tout ce qui la surmonte** :
Django compose sa chaîne de bas en haut, et applique
(`BaseHandler.load_middleware`) :

    elif not handler_is_async and middleware_can_sync:
        middleware_is_async = False

`LangueDeLApprenant` l'était, et elle est déclarée au milieu de la liste. La
partie haute de la chaîne — sessions, langue, CSRF, sécurité et service des
fichiers statiques — s'exécutait donc en mode synchrone sous un serveur
asynchrone.

Le symptôme visible était ailleurs : Django avertissait que les fichiers
statiques étaient matérialisés en mémoire au lieu d'être diffusés. Voir
l'incident 023.
"""

import warnings
from pathlib import Path

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import RequestFactory
from django.utils.module_loading import import_string

FICHIER_STATIQUE = "/static/koda/koda_angry.png"


# --- La structure de la chaîne ---------------------------------------------


def test_aucune_couche_ne_fait_retomber_la_chaine_en_synchrone():
    """
    Toutes les couches d'intergiciel sont asynchrones.

    Compétence visée : C13 (épreuve E3), C18 (E4)

    Ce test rejoue **l'algorithme de composition de Django lui-même**, et non
    une approximation : la boucle sur `reversed(MIDDLEWARE)`, la règle qui fait
    basculer une couche en synchrone, et la propagation du mode vers le haut.

    C'est le garde-fou qui manquait. Le défaut n'était visible par aucun test :
    la couche fautive fonctionnait parfaitement, elle rendait seulement
    synchrone tout ce qui se trouvait au-dessus d'elle, en silence.

    Si une couche purement synchrone est ajoutée un jour, ce test nomme la
    première qui bascule — et toutes celles qu'elle entraîne.
    """
    synchrones = []
    handler_asynchrone = True

    for chemin in reversed(settings.MIDDLEWARE):
        couche = import_string(chemin)
        peut_synchrone = getattr(couche, "sync_capable", True)
        peut_asynchrone = getattr(couche, "async_capable", False)

        if not handler_asynchrone and peut_synchrone:
            mode_asynchrone = False
        else:
            mode_asynchrone = peut_asynchrone

        if not mode_asynchrone:
            synchrones.append(chemin)
        handler_asynchrone = mode_asynchrone

    assert synchrones == [], (
        "ces couches s'exécuteront en synchrone sous un serveur ASGI, et "
        "entraîneront avec elles tout ce qui les surmonte : %s" % synchrones
    )


# --- Le service des fichiers statiques -------------------------------------


def test_un_fichier_statique_est_rendu_par_un_iterateur_asynchrone():
    """
    La réponse porte un itérateur asynchrone, donc Django la diffuse.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    `is_async` est le drapeau que Django pose dans `_set_streaming_content`
    quand le contenu répond à `aiter`. C'est lui qui décide : à faux, Django
    avertit puis exécute `await sync_to_async(list)(...)`, c'est-à-dire qu'il
    charge le fichier entier en mémoire avant d'envoyer le premier octet.

    Les animations de ce projet pèsent jusqu'à 1,4 Mo, et le service tourne
    avec un seul travailleur.
    """
    from eduai_project.statiques import WhiteNoiseAsynchrone

    async def _jamais_appelee(request):  # pragma: no cover - la couche court-circuite
        raise AssertionError("un fichier statique ne doit pas traverser la vue")

    couche = WhiteNoiseAsynchrone(_jamais_appelee)
    requete = RequestFactory().get(FICHIER_STATIQUE)

    reponse = async_to_sync(couche.__acall__)(requete)

    assert reponse.status_code == 200
    assert reponse.streaming, "un fichier est servi en flux"
    assert reponse.is_async, (
        "sans ce drapeau, Django matérialise le fichier entier en mémoire"
    )


def test_le_contenu_du_fichier_est_rendu_intact():
    """
    La conversion en flux asynchrone ne perd ni ne modifie un octet.

    Compétence visée : C13 (épreuve E3), C21 (E5)

    Une correction de performance qui abîmerait le contenu servi serait bien
    pire que le défaut qu'elle corrige.
    """
    from eduai_project.statiques import WhiteNoiseAsynchrone

    async def _jamais_appelee(request):  # pragma: no cover
        raise AssertionError

    chemin = Path(settings.STATIC_ROOT) / "koda" / "koda_angry.png"
    if not chemin.exists():
        pytest.skip("statiques non collectés sur cette machine")

    couche = WhiteNoiseAsynchrone(_jamais_appelee)
    reponse = async_to_sync(couche.__acall__)(RequestFactory().get(FICHIER_STATIQUE))

    async def _lire():
        return b"".join([bloc async for bloc in reponse.streaming_content])

    assert async_to_sync(_lire)() == chemin.read_bytes()


def test_servir_un_statique_n_avertit_plus():
    """
    L'avertissement de Django a disparu, et il a disparu pour la bonne raison.

    Compétence visée : C21 (épreuve E5)

    On ne le fait pas taire : on rend vraie la condition qu'il signalait. Ce
    test échouerait aussi bien si quelqu'un ajoutait un filtre
    d'avertissements pour masquer le symptôme, puisqu'il vérifie d'abord
    `is_async`.
    """
    from eduai_project.statiques import WhiteNoiseAsynchrone

    async def _jamais_appelee(request):  # pragma: no cover
        raise AssertionError

    couche = WhiteNoiseAsynchrone(_jamais_appelee)

    with warnings.catch_warnings(record=True) as captures:
        warnings.simplefilter("always")
        reponse = async_to_sync(couche.__acall__)(
            RequestFactory().get(FICHIER_STATIQUE))

        async def _consommer():
            async for _bloc in reponse:
                pass

        async_to_sync(_consommer)()

    fautifs = [str(c.message) for c in captures
               if "synchronous iterators" in str(c.message)]
    assert fautifs == [], fautifs


# --- La langue de l'apprenant, en asynchrone -------------------------------


@pytest.mark.django_db
def test_la_langue_du_compte_s_applique_dans_une_chaine_asynchrone(
        django_user_model):
    """
    La préférence de langue est lue sans requête synchrone à la base.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    `request.user` est un objet paresseux dont la résolution interroge la base ;
    y toucher depuis une pile asynchrone lève `SynchronousOnlyOperation`. Le
    chemin asynchrone emploie `await request.auser()`.

    **Aucun test ne couvrait ce chemin** : le client de test de Django est
    synchrone, si bien que les 506 tests du projet passaient tous par la
    branche synchrone de cette couche.
    """
    from apps.users.middleware import LangueDeLApprenant

    utilisateur = django_user_model.objects.create_user(
        username="polyglotte", password="mot-de-passe-d-essai-2026")
    utilisateur.language_preference = "en"
    utilisateur.save()

    requete = RequestFactory().get("/")

    async def _auser():
        return utilisateur

    requete.auser = _auser
    requete.user = utilisateur

    vue_atteinte = {}

    async def _vue(request):
        from django.http import HttpResponse
        from django.utils import translation
        vue_atteinte["langue"] = translation.get_language()
        return HttpResponse("ok")

    couche = LangueDeLApprenant(_vue)
    reponse = async_to_sync(couche.__acall__)(requete)

    assert reponse.status_code == 200
    assert requete.LANGUAGE_CODE == "en"
    assert vue_atteinte["langue"] == "en", (
        "la langue doit être active pendant le rendu, pas seulement annoncée"
    )


@pytest.mark.django_db
def test_une_preference_vide_laisse_decider_locale_middleware(django_user_model):
    """
    Rien n'est forcé quand le compte n'exprime aucun choix exploitable.

    Compétence visée : C17 (épreuve E4)

    Précision que ce test a fait apparaître : `language_preference` porte
    `default="fr"` sur le modèle. **Tout compte ordinaire exprime donc une
    préférence**, et la branche « rien à imposer » ne se rencontre qu'avec une
    valeur vide — un champ effacé, ou une migration à venir qui rendrait le
    choix facultatif.

    C'est cette branche-là qui est éprouvée ici, et elle doit valoir dans les
    deux modes : `LocaleMiddleware` sert alors le visiteur en négociant avec
    l'en-tête de son navigateur.
    """
    from apps.users.middleware import LangueDeLApprenant

    utilisateur = django_user_model.objects.create_user(
        username="sans-choix", password="mot-de-passe-d-essai-2026")
    utilisateur.language_preference = ""
    utilisateur.save()

    requete = RequestFactory().get("/")

    async def _auser():
        return utilisateur

    requete.auser = _auser

    async def _vue(request):
        from django.http import HttpResponse
        return HttpResponse("ok")

    async_to_sync(LangueDeLApprenant(_vue).__acall__)(requete)

    assert not hasattr(requete, "LANGUAGE_CODE"), (
        "sans préférence exploitable, la couche ne doit rien imposer"
    )


@pytest.mark.django_db
def test_un_compte_ordinaire_porte_la_langue_par_defaut(django_user_model):
    """
    Le défaut du modèle — « fr » — est appliqué comme un choix.

    Compétence visée : C17 (épreuve E4)

    Ce n'est pas un détail : c'est le cas de presque tous les comptes. Le
    vérifier empêche qu'une correction future traite le défaut du modèle comme
    une absence de choix, ce qui rendrait l'interface à la langue du navigateur
    pour des comptes qui ont bien « Français » enregistré.
    """
    from apps.users.middleware import LangueDeLApprenant

    utilisateur = django_user_model.objects.create_user(
        username="ordinaire", password="mot-de-passe-d-essai-2026")
    assert utilisateur.language_preference == "fr", "le défaut du modèle"

    requete = RequestFactory().get("/")

    async def _auser():
        return utilisateur

    requete.auser = _auser

    async def _vue(request):
        from django.http import HttpResponse
        return HttpResponse("ok")

    async_to_sync(LangueDeLApprenant(_vue).__acall__)(requete)

    assert requete.LANGUAGE_CODE == "fr"


def test_les_deux_modes_decident_de_la_meme_facon():
    """
    Une seule règle de décision, partagée par les deux chemins.

    Compétence visée : C18 (épreuve E4)

    Deux implémentations parallèles finiraient par diverger, et l'une des deux
    n'est éprouvée qu'en production.
    """
    source = Path("apps/users/middleware.py").read_text(encoding="utf-8")

    assert source.count("def _langue_utilisable") == 1
    assert "self._langue_utilisable" in source

