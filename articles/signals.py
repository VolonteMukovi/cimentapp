from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


def copy_default_article_settings(entreprise_id):
    from articles.models import SousTypeArticle, TypeArticle, Unite

    with transaction.atomic():
        types_by_id = {}
        for source in TypeArticle.objects.filter(entreprise_id__isnull=True):
            copied = TypeArticle.objects.create(
                entreprise_id=entreprise_id,
                libelle=source.libelle,
                description=source.description,
            )
            types_by_id[source.pk] = copied.pk

        for source in SousTypeArticle.objects.filter(entreprise_id__isnull=True):
            SousTypeArticle.objects.create(
                entreprise_id=entreprise_id,
                type_article_id=types_by_id.get(source.type_article_id, source.type_article_id),
                libelle=source.libelle,
                description=source.description,
            )

        for source in Unite.objects.filter(entreprise_id__isnull=True):
            Unite.objects.create(
                entreprise_id=entreprise_id,
                code=source.code,
                libelle=source.libelle,
                actif=source.actif,
            )


@receiver(post_save, sender='users.Entreprise')
def initialize_entreprise_article_settings(sender, instance, created, **kwargs):
    if created:
        copy_default_article_settings(instance.pk)
