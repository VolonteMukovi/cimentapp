from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0012_remove_fk_soustype_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='prix_catalogue',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Prix normal (catalogue). Modifiable lors d’une vente.',
                max_digits=18,
                verbose_name='prix catalogue',
            ),
        ),
    ]

