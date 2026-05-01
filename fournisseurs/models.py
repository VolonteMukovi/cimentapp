from django.db import models

from users.models import Entreprise


class Fournisseur(models.Model):
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        INACTIF = 'inactif', 'Inactif'

    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='fournisseurs')
    nom = models.CharField(max_length=150)
    contact = models.CharField(max_length=150)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'fournisseur'
        verbose_name_plural = 'fournisseurs'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.nom} ({self.get_statut_display()})'

