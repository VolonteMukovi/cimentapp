from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lots', '0002_lottransit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lotstock',
            name='devise',
            field=models.CharField(default='USD', max_length=10),
        ),
        migrations.AddField(
            model_name='depenselot',
            name='devise',
            field=models.CharField(default='USD', max_length=10),
        ),
        migrations.AddField(
            model_name='lottransit',
            name='devise',
            field=models.CharField(default='USD', max_length=10),
        ),
        migrations.AddField(
            model_name='lottransit',
            name='fournisseur_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
