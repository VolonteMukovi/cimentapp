from __future__ import annotations

from decimal import Decimal

from django.db import models


class LotStock(models.Model):
    """
    Entrée de stock (lot) — relations via champs *_id (pas de ForeignKey).
    FIFO = tri par date_entree puis id.
    """

    entreprise_id = models.PositiveIntegerField(db_index=True)
    article_id = models.CharField(max_length=32, db_index=True)

    reference = models.CharField(max_length=255, blank=True)
    quantite_entree = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'))
    quantite_restante = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'), db_index=True)
    cout_unitaire_achat = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    date_entree = models.DateTimeField(db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_entree', '-id']
        indexes = [
            models.Index(fields=['entreprise_id', 'article_id', 'date_entree']),
        ]


class DepenseLot(models.Model):
    """Dépenses additionnelles sur un lot (transport, manutention...)."""

    entreprise_id = models.PositiveIntegerField(db_index=True)
    lot_id = models.BigIntegerField(db_index=True)

    libelle = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    date_depense = models.DateTimeField(db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_depense', '-id']
        indexes = [
            models.Index(fields=['entreprise_id', 'lot_id', 'date_depense']),
        ]

