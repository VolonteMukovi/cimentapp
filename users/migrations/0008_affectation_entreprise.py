# Unifie UserEntreprise + ClientEntreprise dans AffectationEntreprise ; supprime AffectEntreprise.

import django.db.models.deletion
from django.db import migrations, models


def copy_affectations(apps, schema_editor):
    UserEntreprise = apps.get_model('users', 'UserEntreprise')
    ClientEntreprise = apps.get_model('users', 'ClientEntreprise')
    AffectationEntreprise = apps.get_model('users', 'AffectationEntreprise')
    for row in UserEntreprise.objects.all().iterator():
        AffectationEntreprise.objects.create(
            user_id=row.user_id,
            client_id=None,
            entreprise_id=row.entreprise_id,
            cree_le=row.cree_le,
        )
    for row in ClientEntreprise.objects.all().iterator():
        AffectationEntreprise.objects.create(
            user_id=None,
            client_id=row.client_id,
            entreprise_id=row.entreprise_id,
            cree_le=row.cree_le,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_client_entreprise'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffectationEntreprise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entreprise_liens',
                        to='users.user',
                    ),
                ),
                (
                    'client',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entreprise_liens',
                        to='users.client',
                    ),
                ),
                (
                    'entreprise',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='affectation_liens',
                        to='users.entreprise',
                    ),
                ),
            ],
            options={
                'verbose_name': 'affectation entreprise',
                'verbose_name_plural': 'affectations entreprise',
            },
        ),
        migrations.AddConstraint(
            model_name='affectationentreprise',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, client__isnull=True)
                    | models.Q(user__isnull=True, client__isnull=False)
                ),
                name='affectation_staff_xor_client',
            ),
        ),
        migrations.AddConstraint(
            model_name='affectationentreprise',
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=('user', 'entreprise'),
                name='unique_user_entreprise_affectation',
            ),
        ),
        migrations.AddConstraint(
            model_name='affectationentreprise',
            constraint=models.UniqueConstraint(
                condition=models.Q(client__isnull=False),
                fields=('client', 'entreprise'),
                name='unique_client_entreprise_affectation',
            ),
        ),
        migrations.RunPython(copy_affectations, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='UserEntreprise',
        ),
        migrations.DeleteModel(
            name='ClientEntreprise',
        ),
        migrations.DeleteModel(
            name='AffectEntreprise',
        ),
    ]
