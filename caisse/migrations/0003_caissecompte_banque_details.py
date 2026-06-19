from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caisse', '0002_mouvementcaisse_devise'),
    ]

    operations = [
        migrations.AddField(
            model_name='caissecompte',
            name='banque_nom',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='caissecompte',
            name='compte_intitule',
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name='caissecompte',
            name='numero_compte',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
