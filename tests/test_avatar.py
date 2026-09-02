"""
Choix et affichage de l'avatar d'un apprenant.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C18 (E3) — tests ; C21 (E5) — incidents

Ces tests défendent une seule idée, en trois endroits : **un avatar choisi
doit s'afficher**. Trois défauts l'en empêchaient, tous mesurés avant d'être
corrigés.

1. La liste proposée était lue dans `STATIC_ROOT`, où `collectstatic` place
   chaque avatar deux fois — l'original et sa copie empreintée. Vingt avatars
   en donnaient quarante.
2. Choisir une de ces copies empreintées provoquait une erreur 500 :
   l'enregistrement ouvre le dossier source, où ce nom n'existe pas.
3. L'avatar Koda retenu était recopié dans `media/`, dont rien ne sert le
   contenu quand DEBUG vaut False. Il était bien en base, et invisible.

Les requêtes sont émises en HTTPS (`secure=True`) : hors DEBUG, le projet
redirige tout appel en clair, et un test en clair ne toucherait jamais la vue.
"""

import base64

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.users.views import avatars_koda_disponibles

Utilisateur = get_user_model()

#: Le plus petit PNG valide : un pixel transparent. Sert d'image envoyée.
PNG_D_UN_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def champs_du_profil(**surcharges):
    """Le formulaire de profil exige ses champs obligatoires à chaque envoi."""
    donnees = {
        "username": "apprenante",
        "email": "apprenante@example.org",
        "bio": "",
        "language_preference": "fr",
        "animation_koda": True,
    }
    donnees.update(surcharges)
    return donnees


@pytest.fixture
def apprenante(db):
    return Utilisateur.objects.create_user(
        username="apprenante", password="mot-de-passe-de-test-1"
    )


def test_la_liste_ne_propose_aucun_nom_empreinte():
    """
    Les avatars proposés viennent du dossier source, sans doublon.

    Compétence visée : C17 (épreuve E4)

    Un nom empreinté porte deux points (`koda_base.82694b6f3cf9.png`). En
    proposer un revenait à proposer un fichier que l'enregistrement ne sait
    pas ouvrir.
    """
    avatars = avatars_koda_disponibles()

    assert avatars, "le dossier des avatars Koda ne doit pas être vide"
    noms = [avatar["filename"] for avatar in avatars]
    assert len(noms) == len(set(noms)), "un avatar est proposé deux fois"
    for nom in noms:
        assert nom.count(".") == 1, f"{nom} est un nom empreinté par collectstatic"


@pytest.mark.django_db
def test_choisir_un_avatar_koda_l_enregistre_et_l_affiche(client, apprenante):
    """
    L'avatar choisi est retenu, et l'URL rendue est une URL statique.

    Compétence visée : C17 (épreuve E4)

    Le cœur du défaut signalé : l'avatar était enregistré dans `media/`, donc
    invisible en production. Il doit désormais être retenu comme nom de
    fichier statique, servi depuis l'image.
    """
    choisi = avatars_koda_disponibles()[0]["filename"]
    client.force_login(apprenante)

    reponse = client.post(
        reverse("users:profile"),
        secure=True,
        data=champs_du_profil(selected_koda_avatar=choisi),
    )
    assert reponse.status_code == 302, "l'enregistrement doit rediriger"

    apprenante.refresh_from_db()
    assert apprenante.koda_avatar == choisi
    assert not apprenante.avatar, "un avatar Koda ne doit rien déposer dans media/"

    page = client.get(reverse("users:profile"), secure=True)
    assert f"/static/koda/{choisi}".encode() in page.content


@pytest.mark.django_db
def test_un_avatar_inconnu_est_refuse_sans_erreur_500(client, apprenante):
    """
    Un nom absent de la liste est refusé par un message, pas par une panne.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    C'est le cas exact remonté : le nom empreinté proposé par l'ancienne
    liste faisait remonter une `FileNotFoundError` jusqu'à l'erreur 500.
    """
    client.force_login(apprenante)

    reponse = client.post(
        reverse("users:profile"),
        secure=True,
        data=champs_du_profil(selected_koda_avatar="koda_base.82694b6f3cf9.png"),
    )

    assert reponse.status_code == 200, "le formulaire doit être réaffiché, pas planter"
    apprenante.refresh_from_db()
    assert apprenante.koda_avatar != "koda_base.82694b6f3cf9.png"


@pytest.mark.django_db
def test_une_image_envoyee_est_servie_hors_debug(client, apprenante, settings, tmp_path):
    """
    Une photo déposée par l'apprenante est réellement servie.

    Compétence visée : C17 (épreuve E4)

    Jusqu'ici, `/media/` n'était routé que si DEBUG valait vrai : l'image
    était enregistrée et toute requête vers elle rendait 404.
    """
    settings.MEDIA_ROOT = tmp_path
    assert not settings.DEBUG, "ce test ne vaut que hors DEBUG"
    client.force_login(apprenante)

    image = "data:image/png;base64," + base64.b64encode(PNG_D_UN_PIXEL).decode()
    reponse = client.post(
        reverse("users:profile"),
        secure=True,
        data=champs_du_profil(cropped_avatar=image),
    )
    assert reponse.status_code == 302

    apprenante.refresh_from_db()
    assert apprenante.avatar, "l'image envoyée doit être enregistrée"

    servie = client.get(apprenante.avatar.url, secure=True)
    assert servie.status_code == 200, "l'image enregistrée doit être servie"
    assert b"".join(servie.streaming_content) == PNG_D_UN_PIXEL


@pytest.mark.django_db
def test_un_compte_neuf_n_a_pas_d_avatar_fantome(client, apprenante):
    """
    Un compte qui n'a rien envoyé porte un champ `avatar` vide.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C4 (E1)

    Le champ portait par défaut `koda_base.png`, un chemin de `media/` où ce
    fichier n'a jamais existé. Tout compte neuf se présentait donc comme ayant
    envoyé une photo, et l'affichage ne retombait jamais sur l'avatar Koda.
    """
    assert not apprenante.avatar, "un compte neuf ne doit pas porter de photo"

    client.force_login(apprenante)
    page = client.get(reverse("users:profile"), secure=True)

    assert page.status_code == 200
    assert b"/media/koda_base.png" not in page.content
