# Generated manually for articles module (paramètres + articles sans FK).

from django.db import migrations, models


def seed_reference_data(apps, schema_editor):
    TypeArticle = apps.get_model('articles', 'TypeArticle')
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    Unite = apps.get_model('articles', 'Unite')

    t1 = TypeArticle.objects.create(code='CIMENT', libelle='Ciment & matériaux', ordre=1, actif=True)
    t2 = TypeArticle.objects.create(code='SERVICE', libelle='Services & logistique', ordre=2, actif=True)

    SousTypeArticle.objects.create(
        type_article_id=t1.id,
        code='PORTLAND',
        libelle='Ciment Portland',
        ordre=1,
        actif=True,
    )
    SousTypeArticle.objects.create(
        type_article_id=t1.id,
        code='COMPO',
        libelle='Ciment composé',
        ordre=2,
        actif=True,
    )
    SousTypeArticle.objects.create(
        type_article_id=t2.id,
        code='LIV',
        libelle='Livraison',
        ordre=1,
        actif=True,
    )

    Unite.objects.create(code='t', libelle='Tonne', actif=True)
    Unite.objects.create(code='sac', libelle='Sac', actif=True)
    Unite.objects.create(code='kg', libelle='Kilogramme', actif=True)
    Unite.objects.create(code='m3', libelle='Mètre cube', actif=True)


def unseed_reference_data(apps, schema_editor):
    Article = apps.get_model('articles', 'Article')
    Article.objects.all().delete()
    SousTypeArticle = apps.get_model('articles', 'SousTypeArticle')
    SousTypeArticle.objects.filter(code__in=('PORTLAND', 'COMPO', 'LIV')).delete()
    TypeArticle = apps.get_model('articles', 'TypeArticle')
    TypeArticle.objects.filter(code__in=('CIMENT', 'SERVICE')).delete()
    Unite = apps.get_model('articles', 'Unite')
    Unite.objects.filter(code__in=('t', 'sac', 'kg', 'm3')).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TypeArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64, unique=True)),
                ('libelle', models.CharField(max_length=255)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'type d’article',
                'verbose_name_plural': 'types d’article',
                'ordering': ['ordre', 'libelle'],
            },
        ),
        migrations.CreateModel(
            name='Unite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=32, unique=True)),
                ('libelle', models.CharField(max_length=128)),
                ('actif', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'unité',
                'verbose_name_plural': 'unités',
                'ordering': ['libelle'],
            },
        ),
        migrations.CreateModel(
            name='SousTypeArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_article_id', models.PositiveIntegerField(db_index=True)),
                ('code', models.CharField(max_length=64)),
                ('libelle', models.CharField(max_length=255)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'sous-type d’article',
                'verbose_name_plural': 'sous-types d’article',
                'ordering': ['type_article_id', 'ordre', 'libelle'],
            },
        ),
        migrations.AddConstraint(
            model_name='soustypearticle',
            constraint=models.UniqueConstraint(
                fields=('type_article_id', 'code'),
                name='articles_uniq_soustype_type',
            ),
        ),
        migrations.CreateModel(
            name='Article',
            fields=[
                (
                    'article_id',
                    models.CharField(
                        editable=False,
                        max_length=32,
                        primary_key=True,
                        serialize=False,
                        verbose_name='identifiant article',
                    ),
                ),
                ('nom_scientifique', models.CharField(max_length=500, verbose_name='nom scientifique')),
                ('nom_commercial', models.CharField(blank=True, max_length=500, verbose_name='nom commercial')),
                ('sous_type_article_id', models.PositiveIntegerField(db_index=True)),
                ('unite_id', models.PositiveIntegerField(db_index=True)),
                ('emplacement', models.CharField(blank=True, max_length=255)),
                (
                    'images',
                    models.TextField(
                        blank=True,
                        help_text='Une URL ou chemin par ligne.',
                        verbose_name='images (texte / URLs)',
                    ),
                ),
                ('entreprise_id', models.PositiveIntegerField(db_index=True)),
                ('succursale_id', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'article',
                'verbose_name_plural': 'articles',
                'ordering': ['nom_scientifique'],
            },
        ),
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['entreprise_id', 'nom_scientifique'], name='articles_art_entrep_nom'),
        ),
        migrations.RunPython(seed_reference_data, unseed_reference_data),
    ]
