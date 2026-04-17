"""Effets de bord métier (sans FK sur ``AffectationEntreprise.source``)."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from users.models import AffectationEntreprise, Client, User


@receiver(post_delete, sender=User)
def _purge_affectations_user(sender, instance, **kwargs):
    AffectationEntreprise.objects.filter(source=instance.pk).delete()


@receiver(post_delete, sender=Client)
def _purge_affectations_client(sender, instance, **kwargs):
    AffectationEntreprise.objects.filter(source=instance.pk).delete()
