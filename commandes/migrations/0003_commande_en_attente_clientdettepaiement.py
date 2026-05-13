from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0002_commande_depot_montant_commande_paiement_statut_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commande',
            name='statut',
            field=models.CharField(
                choices=[
                    ('en_attente', 'En attente'),
                    ('reservee', 'RÃ©servÃ©e'),
                    ('validee', 'ValidÃ©e'),
                    ('livree', 'LivrÃ©e'),
                    ('annulee', 'AnnulÃ©e'),
                ],
                db_index=True,
                default='en_attente',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='ClientDettePaiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entreprise_id', models.PositiveIntegerField(db_index=True)),
                ('client_id', models.CharField(db_index=True, max_length=32)),
                ('caisse_id', models.BigIntegerField(db_index=True)),
                ('montant', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                ('devise', models.CharField(default='USD', max_length=10)),
                ('preuve_paiement', models.ImageField(blank=True, null=True, upload_to='dettes/preuves/')),
                ('note_client', models.CharField(blank=True, max_length=500)),
                (
                    'statut',
                    models.CharField(
                        choices=[
                            ('en_attente', 'En attente'),
                            ('confirme', 'ConfirmÃ©'),
                            ('refuse', 'RefusÃ©'),
                        ],
                        db_index=True,
                        default='en_attente',
                        max_length=20,
                    ),
                ),
                ('date_soumission', models.DateTimeField(db_index=True)),
                ('date_confirmation', models.DateTimeField(blank=True, null=True)),
                ('confirmed_by_user_id', models.CharField(blank=True, max_length=64)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date_soumission', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='clientdettepaiement',
            index=models.Index(fields=['entreprise_id', 'client_id', 'date_soumission'], name='commandes_c_entrepr_5bc032_idx'),
        ),
        migrations.AddIndex(
            model_name='clientdettepaiement',
            index=models.Index(fields=['entreprise_id', 'statut', 'date_soumission'], name='commandes_c_entrepr_2579f9_idx'),
        ),
    ]
