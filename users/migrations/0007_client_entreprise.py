# Generated manually for module Clients (multi-entreprise)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_user_username_no_validator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='email',
            field=models.EmailField(
                blank=True,
                help_text='Identifiant de connexion portail client (unique).',
                max_length=254,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name='ClientEntreprise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                (
                    'client',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entreprise_liens',
                        to='users.client',
                    ),
                ),
                (
                    'entreprise',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='client_liens',
                        to='users.entreprise',
                    ),
                ),
            ],
            options={
                'verbose_name': 'affectation client — entreprise',
                'verbose_name_plural': 'affectations client — entreprise',
            },
        ),
        migrations.AddConstraint(
            model_name='cliententreprise',
            constraint=models.UniqueConstraint(
                fields=('client', 'entreprise'),
                name='unique_client_entreprise',
            ),
        ),
    ]
