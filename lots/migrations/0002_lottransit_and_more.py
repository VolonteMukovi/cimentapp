from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('lots', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lotstock',
            name='lot_transit_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name='LotTransit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entreprise_id', models.PositiveIntegerField(db_index=True)),
                ('reference', models.CharField(db_index=True, max_length=64)),
                ('fournisseur', models.CharField(max_length=150)),
                ('date_expedition', models.DateField()),
                ('date_arrivee_prevue', models.DateField()),
                (
                    'statut',
                    models.CharField(
                        choices=[('en_transit', 'En transit'), ('arrive', 'Arrivé'), ('cloture', 'Clôturé')],
                        db_index=True,
                        default='en_transit',
                        max_length=20,
                    ),
                ),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date_creation', '-id'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('entreprise_id', 'reference'),
                        name='unique_lot_transit_reference_par_entreprise',
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name='LotTransitArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('article_id', models.CharField(db_index=True, max_length=32)),
                ('quantite', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=18)),
                ('prix_unitaire_achat', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                ('cout_total', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                ('pu_reel_propose', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                ('lot_stock_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                (
                    'lot_transit',
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='articles', to='lots.lottransit'),
                ),
            ],
            options={
                'ordering': ['id'],
                'indexes': [models.Index(fields=['lot_transit', 'article_id'], name='lots_lottra_lot_tra_cc915f_idx')],
            },
        ),
        migrations.CreateModel(
            name='LotTransitArticleFinancement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caisse_id', models.BigIntegerField(db_index=True)),
                ('montant', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                (
                    'lot_article',
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name='financements',
                        to='lots.lottransitarticle',
                    ),
                ),
            ],
            options={
                'ordering': ['id'],
                'indexes': [models.Index(fields=['lot_article', 'caisse_id'], name='lots_lottra_lot_art_b1f033_idx')],
            },
        ),
        migrations.CreateModel(
            name='LotTransitFrais',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=255)),
                ('montant', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=18)),
                ('caisse_id', models.BigIntegerField(db_index=True)),
                (
                    'lot_transit',
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='frais', to='lots.lottransit'),
                ),
            ],
            options={
                'ordering': ['id'],
                'indexes': [models.Index(fields=['lot_transit', 'caisse_id'], name='lots_lottra_lot_tra_c779ad_idx')],
            },
        ),
    ]

