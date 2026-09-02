"""
Retire la valeur par défaut fantôme du champ `avatar`.

Compétence visée : C4 (épreuve E1) — cohérence des données
Compétence concernée : C17 (E4)

Le défaut valait `koda_base.png`, un chemin de `media/` où ce fichier n'a
jamais été déposé : les avatars Koda sont livrés en fichiers statiques. Chaque
compte portait donc un avatar « rempli » désignant une image absente, ce qui
rendait vraie partout la condition « cet apprenant a envoyé une photo » et
empêchait l'affichage de retomber sur son avatar Koda.

La migration vide aussi les comptes existants qui portent encore ce chemin :
retirer le défaut ne changerait rien pour eux, la valeur étant déjà écrite
dans leur ligne.
"""

from django.db import migrations, models


def vider_les_avatars_fantomes(apps, schema_editor):
    """
    Vide `avatar` là où il désigne le fichier par défaut, qui n'existe pas.

    Compétence visée : C4 (épreuve E1)

    Choix : ne toucher QUE cette valeur précise, jamais une photo envoyée.
    Motivation : les images déposées par les apprenants sont leurs données ;
    une migration qui les effacerait au passage serait une perte, pas un
    nettoyage.
    """
    Utilisateur = apps.get_model("users", "KodaUser")
    Utilisateur.objects.filter(avatar="koda_base.png").update(avatar=None)


def rien_a_defaire(apps, schema_editor):
    """
    Retour en arrière volontairement sans effet.

    Compétence visée : C4 (épreuve E1)

    Réécrire `koda_base.png` dans les comptes vidés y remettrait le défaut
    fantôme. Un retour arrière ne doit pas restaurer une donnée fausse.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_kodauser_animation_koda'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kodauser',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/',
                                    verbose_name='Avatar'),
        ),
        migrations.RunPython(vider_les_avatars_fantomes, rien_a_defaire),
    ]
