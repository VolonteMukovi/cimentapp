from django.db import migrations, models


def copy_settings_per_entreprise(apps, schema_editor):
    alias = schema_editor.connection.alias
    Article = apps.get_model('articles', 'Article')
    TypeArticle = apps.get_model('articles', 'TypeArticle')
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    Unite = apps.get_model('articles', 'Unite')
    Entreprise = apps.get_model('users', 'Entreprise')

    entreprise_ids = set(
        Entreprise.objects.using(alias).values_list('pk', flat=True)
    )
    entreprise_ids.update(
        Article.objects.using(alias).values_list('entreprise_id', flat=True).distinct()
    )

    types = list(TypeArticle.objects.using(alias).all())
    sous_types = list(SousTypeArticle.objects.using(alias).all())
    unites = list(Unite.objects.using(alias).all())

    for entreprise_id in entreprise_ids:
        type_ids = {}
        for old in types:
            new = TypeArticle.objects.using(alias).create(
                entreprise_id=entreprise_id,
                libelle=old.libelle,
                description=old.description,
            )
            type_ids[old.pk] = new.pk

        sous_type_ids = {}
        for old in sous_types:
            new = SousTypeArticle.objects.using(alias).create(
                entreprise_id=entreprise_id,
                type_article_id=type_ids.get(old.type_article_id, old.type_article_id),
                libelle=old.libelle,
                description=old.description,
            )
            sous_type_ids[old.pk] = new.pk

        unite_ids = {}
        for old in unites:
            new = Unite.objects.using(alias).create(
                entreprise_id=entreprise_id,
                code=old.code,
                libelle=old.libelle,
                actif=old.actif,
            )
            unite_ids[old.pk] = new.pk

        articles = Article.objects.using(alias).filter(entreprise_id=entreprise_id)
        for article in articles.iterator():
            updates = {}
            if article.sous_type_article_id in sous_type_ids:
                updates['sous_type_article_id'] = sous_type_ids[article.sous_type_article_id]
            if article.unite_id in unite_ids:
                updates['unite_id'] = unite_ids[article.unite_id]
            if updates:
                Article.objects.using(alias).filter(pk=article.pk).update(**updates)


def restore_shared_settings(apps, schema_editor):
    alias = schema_editor.connection.alias
    Article = apps.get_model('articles', 'Article')
    TypeArticle = apps.get_model('articles', 'TypeArticle')
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    Unite = apps.get_model('articles', 'Unite')

    legacy_type_by_value = {}
    for row in TypeArticle.objects.using(alias).filter(entreprise_id__isnull=True):
        legacy_type_by_value.setdefault((row.libelle, row.description), row.pk)

    legacy_type_ids = {}
    for row in TypeArticle.objects.using(alias).exclude(entreprise_id__isnull=True):
        value = (row.libelle, row.description)
        legacy_id = legacy_type_by_value.get(value)
        if legacy_id is None:
            legacy_id = TypeArticle.objects.using(alias).create(
                entreprise_id=None,
                libelle=row.libelle,
                description=row.description,
            ).pk
            legacy_type_by_value[value] = legacy_id
        legacy_type_ids[(row.entreprise_id, row.pk)] = legacy_id

    legacy_subtype_by_value = {}
    for row in SousTypeArticle.objects.using(alias).filter(entreprise_id__isnull=True):
        legacy_subtype_by_value.setdefault(
            (row.type_article_id, row.libelle, row.description),
            row.pk,
        )

    legacy_subtype_ids = {}
    for row in SousTypeArticle.objects.using(alias).exclude(entreprise_id__isnull=True):
        legacy_type_id = legacy_type_ids.get((row.entreprise_id, row.type_article_id))
        if legacy_type_id is None:
            continue
        value = (legacy_type_id, row.libelle, row.description)
        legacy_id = legacy_subtype_by_value.get(value)
        if legacy_id is None:
            legacy_id = SousTypeArticle.objects.using(alias).create(
                entreprise_id=None,
                type_article_id=legacy_type_id,
                libelle=row.libelle,
                description=row.description,
            ).pk
            legacy_subtype_by_value[value] = legacy_id
        legacy_subtype_ids[(row.entreprise_id, row.pk)] = legacy_id

    legacy_unit_by_code = {
        row.code: row.pk
        for row in Unite.objects.using(alias).filter(entreprise_id__isnull=True)
    }
    legacy_unit_ids = {}
    for row in Unite.objects.using(alias).exclude(entreprise_id__isnull=True):
        legacy_id = legacy_unit_by_code.get(row.code)
        if legacy_id is None:
            legacy_id = Unite.objects.using(alias).create(
                entreprise_id=None,
                code=row.code,
                libelle=row.libelle,
                actif=row.actif,
            ).pk
            legacy_unit_by_code[row.code] = legacy_id
        legacy_unit_ids[(row.entreprise_id, row.pk)] = legacy_id

    for article in Article.objects.using(alias).iterator():
        updates = {}
        legacy_subtype_id = legacy_subtype_ids.get(
            (article.entreprise_id, article.sous_type_article_id),
        )
        if legacy_subtype_id is not None:
            updates['sous_type_article_id'] = legacy_subtype_id

        legacy_unit_id = legacy_unit_ids.get((article.entreprise_id, article.unite_id))
        if legacy_unit_id is not None:
            updates['unite_id'] = legacy_unit_id

        if updates:
            Article.objects.using(alias).filter(pk=article.pk).update(**updates)

    TypeArticle.objects.using(alias).filter(entreprise_id__isnull=False).delete()
    SousTypeArticle.objects.using(alias).filter(entreprise_id__isnull=False).delete()
    Unite.objects.using(alias).filter(entreprise_id__isnull=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0014_devise'),
        ('users', '0010_entreprise_invitation_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='typearticle',
            name='entreprise_id',
            field=models.PositiveIntegerField(db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='soustypearticle',
            name='entreprise_id',
            field=models.PositiveIntegerField(db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='unite',
            name='entreprise_id',
            field=models.PositiveIntegerField(db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='unite',
            name='code',
            field=models.CharField(max_length=32),
        ),
        migrations.RunPython(copy_settings_per_entreprise, restore_shared_settings),
        migrations.AddConstraint(
            model_name='unite',
            constraint=models.UniqueConstraint(
                fields=('entreprise_id', 'code'),
                name='unique_unite_code_par_entreprise',
            ),
        ),
    ]
