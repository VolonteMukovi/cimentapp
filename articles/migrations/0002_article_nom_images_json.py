# Migration Article : nom unique, images JSON, suppression champs obsolètes.

from django.db import migrations, models
from django.db.models import Index


def drop_article_entrep_nom_index_if_exists(apps, schema_editor):
    """DB may lack this index (partial migrate, manual change). State must still drop it."""
    connection = schema_editor.connection
    Article = apps.get_model('articles', 'Article')
    table = Article._meta.db_table
    index_name = 'articles_art_entrep_nom'
    with connection.cursor() as cursor:
        if index_name not in connection.introspection.get_constraints(cursor, table):
            return
    index = Index(fields=['entreprise_id', 'nom_scientifique'], name=index_name)
    schema_editor.remove_index(Article, index)


def forwards_text_to_json(apps, schema_editor):
    Article = apps.get_model('articles', 'Article')
    # Explicit order_by: migration Meta can still reference the old ordering field
    # after RenameField until AlterModelOptions runs.
    for row in Article.objects.order_by('article_id').iterator():
        text = getattr(row, 'images', None)
        if text is None:
            text = ''
        if isinstance(text, (list, dict)):
            row.images_new = text if isinstance(text, list) else []
        else:
            t = str(text).strip()
            if not t:
                row.images_new = []
            else:
                lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
                row.images_new = [{'image': ln, 'is_main': i == 0} for i, ln in enumerate(lines)]
        row.save(update_fields=['images_new'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(model_name='article', name='articles_art_entrep_nom'),
            ],
            database_operations=[
                migrations.RunPython(
                    drop_article_entrep_nom_index_if_exists,
                    migrations.RunPython.noop,
                ),
            ],
        ),
        migrations.RenameField(
            model_name='article',
            old_name='nom_scientifique',
            new_name='nom',
        ),
        migrations.AlterModelOptions(
            name='article',
            options={
                'ordering': ['nom'],
                'verbose_name': 'article',
                'verbose_name_plural': 'articles',
            },
        ),
        migrations.RemoveField(model_name='article', name='nom_commercial'),
        migrations.RemoveField(model_name='article', name='succursale_id'),
        migrations.AddField(
            model_name='article',
            name='images_new',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='images (JSON)'),
        ),
        migrations.RunPython(forwards_text_to_json, noop_reverse),
        migrations.RemoveField(model_name='article', name='images'),
        migrations.RenameField(
            model_name='article',
            old_name='images_new',
            new_name='images',
        ),
        migrations.AlterField(
            model_name='article',
            name='images',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Liste d’objets {image, is_main} ; chemins relatifs sous MEDIA.',
                verbose_name='images',
            ),
        ),
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['entreprise_id', 'nom'], name='articles_art_entrep_nom_v2'),
        ),
    ]
