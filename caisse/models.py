from __future__ import annotations

from decimal import Decimal

from django.db import models


class CaisseCompte(models.Model):
    """Sous-compte caisse (cash, banque, mobile money...)."""

    entreprise_id = models.PositiveIntegerField(db_index=True)
    nom = models.CharField(max_length=120)
    actif = models.BooleanField(default=True)
    created_by_user_id = models.CharField(max_length=32, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation', '-id']
        indexes = [models.Index(fields=['entreprise_id', 'actif', 'nom'])]


class MouvementCaisse(models.Model):
    class Type(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'

    entreprise_id = models.PositiveIntegerField(db_index=True)
    caisse_id = models.BigIntegerField(db_index=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    date_mouvement = models.DateTimeField(db_index=True)
    libelle = models.CharField(max_length=255, blank=True)

    source_type = models.CharField(max_length=30, blank=True)  # ex: 'vente'
    source_id = models.CharField(max_length=64, blank=True)  # id vente

    created_by_user_id = models.CharField(max_length=32, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_mouvement', '-id']
        indexes = [
            models.Index(fields=['entreprise_id', 'caisse_id', 'date_mouvement']),
        ]

