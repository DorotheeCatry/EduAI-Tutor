"""
Suppression du champ `ip_address` de `ExerciseSubmission`.

Compétence visée : C4 (épreuve E1) — protection des données personnelles

Une adresse IP est une donnée personnelle : le considérant 26 du RGPD retient
qu'une personne est identifiable dès lors que des moyens raisonnablement
susceptibles d'être utilisés permettent de l'identifier — ce qui est le cas
d'une IP rapprochée des journaux d'un fournisseur d'accès.

Choix : SUPPRIMER le champ, et non lui affecter une durée de conservation.
Motivation : le principe de minimisation de l'article 5.1.c porte d'abord sur
la COLLECTE. Une donnée dont la finalité n'est pas établie ne se conserve pas,
fût-ce brièvement — lui donner une durée reviendrait à régulariser une collecte
qui n'aurait pas dû avoir lieu. Or aucune finalité n'était établie ici : le
champ était renseigné à chaque soumission d'exercice et n'était lu par aucun
code du projet. Ni sécurité, ni lutte contre la fraude, ni statistique : rien.

Conséquence : les valeurs déjà collectées sont détruites avec la colonne. C'est
l'effet recherché, et il est irréversible. Aucune sauvegarde n'en conserve de
copie exploitable.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0002_alter_exercise_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='exercisesubmission',
            name='ip_address',
        ),
    ]
