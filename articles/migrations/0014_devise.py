# Generated manually for currency settings.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0013_article_prix_catalogue'),
    ]

    operations = [
        migrations.CreateModel(
            name='Devise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entreprise_id', models.PositiveIntegerField(db_index=True)),
                ('code', models.CharField(max_length=10)),
                ('libelle', models.CharField(blank=True, max_length=64)),
                ('principale', models.BooleanField(db_index=True, default=False)),
                (
                    'taux_vers_principale',
                    models.DecimalField(
                        decimal_places=6,
                        default=Decimal('1'),
                        help_text='Valeur de 1 unite de cette devise dans la devise principale.',
                        max_digits=18,
                    ),
                ),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'devise',
                'verbose_name_plural': 'devises',
                'ordering': ['-principale', 'code'],
            },
        ),
        migrations.AddIndex(
            model_name='devise',
            index=models.Index(fields=['entreprise_id', 'principale', 'actif'], name='articles_de_entrepr_d1d402_idx'),
        ),
        migrations.AddConstraint(
            model_name='devise',
            constraint=models.UniqueConstraint(fields=('entreprise_id', 'code'), name='unique_devise_code_par_entreprise'),
        ),
    ]
