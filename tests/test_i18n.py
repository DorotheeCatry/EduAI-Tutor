"""
Tests de l'internationalisation de l'interface.

Compétence visée : C18 (épreuve E4) — tests automatisés
Compétences concernées : C17 (E4) — application web ; C13 (E3) — accessibilité

Ces tests portent sur un écart précis, et c'est leur raison d'être : le champ
`language_preference` existait, la page de profil proposait un sélecteur, la
valeur était enregistrée en base — et rien ne la lisait pour l'affichage. Un
réglage stocké et jamais lu se voit d'autant moins qu'il est accepté sans
erreur.

Ils vérifient donc l'EFFET du réglage sur la page servie, jamais sa présence
en base.
"""

import pytest
from django.urls import reverse


@pytest.fixture
def apprenant_francophone(django_user_model):
    """
    Compte dont la langue d'interface est le français.

    Compétence visée : C17 (épreuve E4)
    """
    return django_user_model.objects.create_user(
        username="apprenante_fr",
        email="fr@exemple.test",
        password="mot-de-passe-d-essai-2026",
        language_preference="fr",
    )


@pytest.fixture
def apprenant_anglophone(django_user_model):
    """
    Compte dont la langue d'interface est l'anglais.

    Compétence visée : C17 (épreuve E4)
    """
    return django_user_model.objects.create_user(
        username="apprenante_en",
        email="en@exemple.test",
        password="mot-de-passe-d-essai-2026",
        language_preference="en",
    )


@pytest.mark.django_db
def test_la_langue_par_defaut_du_service_est_le_francais(client):
    """
    Un visiteur non connecté reçoit une page en français.

    Compétence visée : C17 (épreuve E4)

    `LANGUAGE_CODE` valait `en` alors que le seul catalogue traduit était `fr` :
    aucune traduction n'était donc jamais appliquée, et l'interface affichait
    ses chaînes sources anglaises à côté des quelques messages écrits en
    français. C'est l'origine du mélange des deux langues sur une même page.
    """
    reponse = client.get(reverse("users:login"), secure=True,
                         HTTP_ACCEPT_LANGUAGE="fr")

    assert reponse.status_code == 200
    contenu = reponse.content.decode("utf-8")
    assert "Se connecter" in contenu, "la page de connexion n'est pas en français"


@pytest.mark.django_db
def test_le_choix_de_langue_du_compte_change_la_page_servie(
        client, apprenant_anglophone):
    """
    Le réglage enregistré agit sur l'interface, et pas seulement en base.

    Compétence visée : C17 (épreuve E4)

    C'est le test qui manquait : la préférence était lue par l'orchestrateur
    d'agents, pour la langue des quiz générés, et par personne d'autre. Elle
    n'avait aucun effet sur les pages.
    """
    client.force_login(apprenant_anglophone)

    reponse = client.get(reverse("users:profile"), secure=True)

    assert reponse.status_code == 200
    contenu = reponse.content.decode("utf-8")
    assert "Sign Out" in contenu, "l'interface n'est pas passée en anglais"
    assert "Se déconnecter" not in contenu


@pytest.mark.django_db
def test_deux_comptes_recoivent_chacun_leur_langue(
        client, apprenant_francophone, apprenant_anglophone):
    """
    La langue suit le compte, pas le serveur.

    Compétence visée : C17 (épreuve E4)

    Deux requêtes successives sur la même page, par deux comptes différents,
    doivent donner deux langues. Un test sur un seul compte ne distinguerait
    pas un réglage effectif d'un réglage global figé.
    """
    client.force_login(apprenant_francophone)
    en_francais = client.get(reverse("users:profile"), secure=True).content.decode("utf-8")

    client.force_login(apprenant_anglophone)
    en_anglais = client.get(reverse("users:profile"), secure=True).content.decode("utf-8")

    assert "Se déconnecter" in en_francais
    assert "Sign Out" in en_anglais
    assert en_francais != en_anglais


@pytest.mark.django_db
def test_l_attribut_lang_suit_la_langue_servie(client, apprenant_anglophone,
                                               apprenant_francophone):
    """
    L'attribut `lang` de la balise <html> annonce la langue réellement servie.

    Compétence visée : C13 (épreuve E3) — accessibilité
    Compétence visée : C17 (épreuve E4)

    Il était écrit en dur — `lang="fr"` — alors que `LANGUAGE_CODE` valait
    `en`. Un lecteur d'écran s'en sert pour choisir sa synthèse vocale : un
    attribut qui ment fait lire de l'anglais avec une prononciation française,
    ou l'inverse. L'écart était relevé dès l'état des lieux.
    """
    client.force_login(apprenant_francophone)
    assert '<html lang="fr">' in client.get(
        reverse("users:profile"), secure=True).content.decode("utf-8")

    client.force_login(apprenant_anglophone)
    assert '<html lang="en">' in client.get(
        reverse("users:profile"), secure=True).content.decode("utf-8")


@pytest.mark.django_db
def test_une_langue_inconnue_ne_met_pas_la_page_en_erreur(
        client, apprenant_francophone):
    """
    Une préférence hors de `LANGUAGES` est ignorée, la page reste servie.

    Compétence visée : C17 (épreuve E4)

    `LANGUAGES` peut changer : une langue retirée des réglages laisserait des
    comptes portant une valeur devenue invalide. Faire échouer la requête
    punirait l'apprenant pour un changement de configuration.
    """
    apprenant_francophone.language_preference = "eo"
    apprenant_francophone.save(update_fields=["language_preference"])
    client.force_login(apprenant_francophone)

    reponse = client.get(reverse("users:profile"), secure=True)

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_compteur_de_generations_reste_en_francais_pour_un_francophone(
        client, apprenant_francophone):
    """
    Le décompte de quotas traverse la traduction sans perdre son libellé.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Ce message a été réécrit en `blocktrans ... count` pour gérer le pluriel.
    Le libellé français doit rester mot pour mot celui que vérifient
    `tests/test_quotas.py` et le script de vérification du déploiement.
    """
    client.force_login(apprenant_francophone)

    contenu = client.get(reverse("courses:catalogue"),
                         secure=True).content.decode("utf-8")

    assert "Il vous reste" in contenu
