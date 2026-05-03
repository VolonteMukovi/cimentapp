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
    lot_transit_id = models.BigIntegerField(null=True, blank=True, db_index=True)

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


class LotTransit(models.Model):
    class Statut(models.TextChoices):
        EN_TRANSIT = 'en_transit', 'En transit'
        ARRIVE = 'arrive', 'Arrivé'
        CLOTURE = 'cloture', 'Clôturé'

    entreprise_id = models.PositiveIntegerField(db_index=True)
    reference = models.CharField(max_length=64, db_index=True)
    fournisseur = models.CharField(max_length=150)
    date_expedition = models.DateField()
    date_arrivee_prevue = models.DateField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_TRANSIT, db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=('entreprise_id', 'reference'),
                name='unique_lot_transit_reference_par_entreprise',
            ),
        ]


class LotTransitArticle(models.Model):
    lot_transit = models.ForeignKey(LotTransit, on_delete=models.CASCADE, related_name='articles')
    article_id = models.CharField(max_length=32, db_index=True)
    quantite = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'))
    prix_unitaire_achat = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    cout_total = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    pu_reel_propose = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    lot_stock_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['lot_transit', 'article_id'])]


class LotTransitArticleFinancement(models.Model):
    lot_article = models.ForeignKey(LotTransitArticle, on_delete=models.CASCADE, related_name='financements')
    caisse_id = models.BigIntegerField(db_index=True)
    montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['lot_article', 'caisse_id'])]


class LotTransitFrais(models.Model):
    lot_transit = models.ForeignKey(LotTransit, on_delete=models.CASCADE, related_name='frais')
    libelle = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    caisse_id = models.BigIntegerField(db_index=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['lot_transit', 'caisse_id'])]

