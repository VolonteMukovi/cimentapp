from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caisse', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mouvementcaisse',
            name='devise',
            field=models.CharField(default='USD', max_length=10),
        ),
    ]
