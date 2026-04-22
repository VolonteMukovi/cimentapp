from __future__ import annotations

import secrets
from decimal import Decimal

from django.db import models


class Vente(models.Model):
    vente_id = models.CharField(max_length=32, primary_key=True, editable=False)
    entreprise_id = models.PositiveIntegerField(db_index=True)

    client_nom = models.CharField(max_length=255, blank=True)  # client occasionnel (non enregistré)
    client_id = models.CharField(max_length=32, blank=True, db_index=True)
    commande_id = models.CharField(max_length=32, blank=True, db_index=True)
    type_vente = models.CharField(max_length=10, default='comptant', db_index=True)  # comptant|credit
    total = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    devise = models.CharField(max_length=10, default='USD')

    caisse_id = models.BigIntegerField(null=True, blank=True, db_index=True)  # sous-compte encaissé
    date_vente = models.DateTimeField(db_index=True)
    created_by_user_id = models.CharField(max_length=32, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_vente', '-vente_id']
        indexes = [
            models.Index(fields=['entreprise_id', 'date_vente']),
            models.Index(fields=['entreprise_id', 'caisse_id', 'date_vente']),
        ]

    @staticmethod
    def generate_id() -> str:
        return f'vte_{secrets.token_hex(6)}'


class VenteLigne(models.Model):
    vente_id = models.CharField(max_length=32, db_index=True)
    article_id = models.CharField(max_length=32, db_index=True)

    quantite = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'))
    prix_unitaire_vente = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    total_ligne = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['vente_id', 'article_id'])]


class VenteFifoConsommation(models.Model):
    """Trace FIFO: quelle quantité provient de quel lot."""

    vente_id = models.CharField(max_length=32, db_index=True)
    vente_ligne_id = models.BigIntegerField(db_index=True)
    lot_id = models.BigIntegerField(db_index=True)
    article_id = models.CharField(max_length=32, db_index=True)

    quantite = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'))
    cout_unitaire_achat = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    cout_unitaire_depenses = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['vente_id', 'article_id']),
            models.Index(fields=['lot_id']),
        ]

