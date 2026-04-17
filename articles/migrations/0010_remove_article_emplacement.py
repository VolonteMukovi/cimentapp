from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0003_rename_articles_art_entrep_nom_v2_articles_ar_entrepr_e24361_idx_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='article',
            name='emplacement',
        ),
    ]
