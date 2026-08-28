"""
Contrôles de l'effacement d'un compte apprenant.

Compétence visée : C4 (épreuve E1) — droit à l'effacement, article 17 du RGPD
Compétence visée : C18 (épreuve E4) — tests automatisés
Compétence visée : C17 (épreuve E4)

**Un effacement partiel est pire qu'un effacement absent**, parce qu'il donne
l'illusion d'être conforme. Ces tests ne vérifient donc pas que la fonction
d'effacement a été appelée, ni qu'elle a rendu un rapport satisfait : ils
relisent la base et le disque après coup et exigent qu'il ne reste rien.

Deux reliquats sont visés en particulier, parce qu'aucune cascade de Django ne
les atteint :

  - le fichier d'avatar, que la suppression de la ligne ne touche pas ;
  - la session ouverte, stockée dans une table sans clé étrangère vers
    l'utilisateur.

Ce sont exactement les deux que produirait une vue qui se contenterait
d'appeler `user.delete()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.files.base import ContentFile

pytestmark = pytest.mark.django_db


@pytest.fixture
def apprenant(django_user_model):
    """Un compte apprenant avec un avatar qui lui est propre."""
    utilisateur = django_user_model.objects.create_user(
        username="apprenant_effacement",
        email="apprenant.effacement@exemple.test",
        password="motdepasse-de-test-sans-valeur",
    )
    utilisateur.avatar.save(
        "avatar_effacement.png", ContentFile(b"pixels"), save=True,
    )
    return utilisateur


# --- L'effacement laisse-t-il quelque chose ? -----------------------------

def test_l_effacement_ne_laisse_rien_en_base(apprenant):
    """
    Après effacement, plus aucune ligne ne référence l'utilisateur.

    Compétence visée : C4 (épreuve E1)

    Le rapport n'est pas cru sur parole : `subsiste` est construit en relisant
    la base après la suppression, pas en soustrayant ce qu'on croit avoir
    supprimé.
    """
    from apps.users.effacement import supprimer_compte

    identifiant = apprenant.pk
    rapport = supprimer_compte(apprenant)

    assert rapport.subsiste == {}, (
        f"l'effacement laisse des données en base : {rapport.subsiste}"
    )
    assert rapport.identifiant == identifiant


def test_le_fichier_d_avatar_est_reellement_supprime_du_disque(apprenant):
    """
    Le fichier d'avatar disparaît du disque, pas seulement de la base.

    Compétence visée : C4 (épreuve E1)

    C'est le reliquat le plus facile à manquer : `user.delete()` retire la ligne
    qui désigne le fichier et laisse le fichier. Une photo de profil est une
    donnée personnelle ; la conserver après un effacement demandé est un
    manquement à l'article 17.
    """
    from apps.users.effacement import supprimer_compte

    chemin = Path(settings.MEDIA_ROOT) / apprenant.avatar.name
    assert chemin.is_file(), "le fichier doit exister avant l'effacement"

    rapport = supprimer_compte(apprenant)

    assert not chemin.exists(), "le fichier d'avatar subsiste sur le disque"
    assert str(chemin) in rapport.fichiers_supprimes
    assert rapport.fichiers_subsistants == []


def test_l_avatar_partage_n_est_pas_supprime(django_user_model):
    """
    L'avatar livré avec l'application survit à l'effacement d'un compte.

    Compétence visée : C4 (épreuve E1)

    Contre-test. Le fichier par défaut appartient à l'application, non à la
    personne : le supprimer casserait l'affichage de tous les autres comptes.
    Un effacement trop large est une régression, pas un excès de zèle.
    """
    from apps.users.effacement import _chemin_avatar

    utilisateur = django_user_model.objects.create_user(
        username="apprenant_avatar_defaut",
        email="avatar.defaut@exemple.test",
        password="motdepasse-de-test-sans-valeur",
    )
    # L'avatar vaut le fichier partagé par défaut.
    assert _chemin_avatar(utilisateur) is None, (
        "un avatar partagé ne doit jamais être désigné pour suppression"
    )


def test_la_session_ouverte_est_supprimee(client, django_user_model):
    """
    Une session ouverte ne survit pas à la suppression du compte.

    Compétence visée : C4 (épreuve E1)

    La table des sessions ne porte aucune clé étrangère vers l'utilisateur :
    aucune cascade ne l'atteint. Une session laissée derrière garde, jusqu'à son
    expiration, une trace rattachable à une personne dont on a effacé le
    dossier — et laisse un utilisateur authentifié sans compte.
    """
    from apps.users.effacement import _sessions_de, supprimer_compte

    utilisateur = django_user_model.objects.create_user(
        username="apprenant_session",
        email="session@exemple.test",
        password="motdepasse-de-test-sans-valeur",
    )
    client.force_login(utilisateur)
    identifiant = utilisateur.pk

    assert _sessions_de(identifiant), "une session doit exister avant l'effacement"
    avant = Session.objects.count()

    rapport = supprimer_compte(utilisateur)

    assert _sessions_de(identifiant) == [], "une session survit à l'effacement"
    assert Session.objects.count() < avant
    assert rapport.supprime["sessions"] >= 1


def test_le_rapport_declare_l_effacement_conforme(apprenant):
    """
    `conforme` ne vaut vrai que si rien ne subsiste, en base comme sur disque.

    Compétence visée : C4 (épreuve E1)
    """
    from apps.users.effacement import supprimer_compte

    assert supprimer_compte(apprenant).conforme is True


# --- La vue ne supprime pas sans confirmation exacte ----------------------

def test_une_confirmation_incorrecte_ne_supprime_rien(client, apprenant,
                                                      django_user_model):
    """
    Une saisie qui ne correspond pas à l'adresse laisse le compte intact.

    Compétence visée : C4 (épreuve E1), C17 (épreuve E4)

    L'effacement est irréversible : il ne doit pas pouvoir être déclenché par
    une soumission approximative.
    """
    client.force_login(apprenant)
    reponse = client.post("/auth/profile/supprimer/",
                          {"confirmation": "pas la bonne adresse"})

    assert reponse.status_code == 200
    assert django_user_model.objects.filter(pk=apprenant.pk).exists(), (
        "le compte a été supprimé malgré une confirmation incorrecte"
    )


def test_la_confirmation_exacte_supprime_le_compte(client, apprenant,
                                                   django_user_model):
    """
    La saisie exacte de l'adresse déclenche l'effacement.

    Compétence visée : C4 (épreuve E1), C17 (épreuve E4)
    """
    identifiant = apprenant.pk
    chemin = Path(settings.MEDIA_ROOT) / apprenant.avatar.name
    client.force_login(apprenant)

    reponse = client.post("/auth/profile/supprimer/",
                          {"confirmation": apprenant.email}, follow=False)

    assert reponse.status_code == 302
    assert not django_user_model.objects.filter(pk=identifiant).exists()
    assert not chemin.exists(), "le fichier d'avatar subsiste après la vue"


def test_l_ecran_annonce_ce_qui_sera_supprime(client, apprenant):
    """
    L'écran de confirmation présente le décompte réel, pas une formule.

    Compétence visée : C4 (épreuve E1) — article 12.1, information claire
    """
    client.force_login(apprenant)
    reponse = client.get("/auth/profile/supprimer/")

    assert reponse.status_code == 200
    assert "effets" in reponse.context
    assert reponse.context["effets"]["compte"] == 1


# --- Non-régression : le champ ip_address a bien disparu ------------------

def test_les_soumissions_ne_portent_plus_d_adresse_ip():
    """
    `ExerciseSubmission` n'a plus de champ `ip_address`.

    Compétence visée : C4 (épreuve E1) — minimisation, article 5.1.c

    Une adresse IP est une donnée personnelle au sens du considérant 26. Le
    champ était renseigné à chaque soumission et n'était lu par aucun code : une
    collecte sans finalité. Il a été supprimé, non doté d'une durée de
    conservation — donner une durée à une donnée qui n'aurait pas dû être
    collectée régularise la collecte au lieu de la corriger.
    """
    from apps.exercises.models import ExerciseSubmission

    champs = {champ.name for champ in ExerciseSubmission._meta.get_fields()}
    assert "ip_address" not in champs, (
        "le champ ip_address est réapparu : collecte sans finalité établie"
    )
