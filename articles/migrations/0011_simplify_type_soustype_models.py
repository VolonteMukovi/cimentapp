import django.db.models.deletion
from django.db import migrations, models


def forwards_copy_type_and_soustype(apps, schema_editor):
    TypeArticle = apps.get_model('articles', 'TypeArticle')
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    # Type: description is new; keep libelle, drop other fields later.
    TypeArticle.objects.all().update(description=None)
    # Sous-type: create FK type from legacy type_article_id
    for st in SousTypeArticle.objects.all().iterator():
        if getattr(st, 'type_id', None):
            continue
        tid = getattr(st, 'type_article_id', None)
        if not tid:
            continue
        if TypeArticle.objects.filter(pk=tid).exists():
            SousTypeArticle.objects.filter(pk=st.pk).update(type_id=tid, description=None)


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0010_remove_article_emplacement'),
    ]

    operations = [
        migrations.AddField(
            model_name='typearticle',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='soustypearticle',
            name='type',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sous_types',
                to='articles.typearticle',
            ),
        ),
        migrations.AddField(
            model_name='soustypearticle',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_copy_type_and_soustype, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='typearticle',
            name='code',
        ),
        migrations.RemoveField(
            model_name='typearticle',
            name='ordre',
        ),
        migrations.RemoveField(
            model_name='typearticle',
            name='actif',
        ),
        migrations.RemoveConstraint(
            model_name='soustypearticle',
            name='articles_uniq_soustype_type',
        ),
        migrations.RemoveField(
            model_name='soustypearticle',
            name='type_article_id',
        ),
        migrations.RemoveField(
            model_name='soustypearticle',
            name='code',
        ),
        migrations.RemoveField(
            model_name='soustypearticle',
            name='ordre',
        ),
        migrations.RemoveField(
            model_name='soustypearticle',
            name='actif',
        ),
        migrations.AlterField(
            model_name='soustypearticle',
            name='type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sous_types',
                to='articles.typearticle',
            ),
        ),
        migrations.AlterModelOptions(
            name='typearticle',
            options={'ordering': ['libelle'], 'verbose_name': "type d’article", 'verbose_name_plural': "types d’article"},
        ),
        migrations.AlterModelOptions(
            name='soustypearticle',
            options={'ordering': ['type_id', 'libelle'], 'verbose_name': "sous-type d’article", 'verbose_name_plural': "sous-types d’article"},
        ),
    ]

