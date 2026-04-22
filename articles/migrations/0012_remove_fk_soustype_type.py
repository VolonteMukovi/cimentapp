import django.db.models.deletion
from django.db import migrations, models


def forwards_fk_to_id(apps, schema_editor):
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    for st in SousTypeArticle.objects.all().iterator():
        tid = getattr(st, 'type_id', None)
        if tid:
            SousTypeArticle.objects.filter(pk=st.pk).update(type_article_id=tid)


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0011_simplify_type_soustype_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='soustypearticle',
            name='type_article_id',
            field=models.PositiveIntegerField(db_index=True, null=True),
        ),
        migrations.RunPython(forwards_fk_to_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='soustypearticle',
            name='type_article_id',
            field=models.PositiveIntegerField(db_index=True),
        ),
        migrations.RemoveField(
            model_name='soustypearticle',
            name='type',
        ),
        migrations.AlterModelOptions(
            name='soustypearticle',
            options={
                'ordering': ['type_article_id', 'libelle'],
                'verbose_name': "sous-type d’article",
                'verbose_name_plural': "sous-types d’article",
            },
        ),
    ]

