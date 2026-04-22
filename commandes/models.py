from __future__ import annotations

import secrets
from decimal import Decimal

from django.db import models


class Commande(models.Model):
    class Statut(models.TextChoices):
        RESERVEE = 'reservee', 'Réservée'
        VALIDEE = 'validee', 'Validée'
        LIVREE = 'livree', 'Livrée'
        ANNULEE = 'annulee', 'Annulée'

    commande_id = models.CharField(max_length=32, primary_key=True, editable=False)
    entreprise_id = models.PositiveIntegerField(db_index=True)
    client_id = models.CharField(max_length=32, blank=True, db_index=True)

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.RESERVEE, db_index=True)
    devise = models.CharField(max_length=10, default='USD')
    total = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    class PaiementStatut(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        EN_ATTENTE = 'en_attente', 'En attente'
        CONFIRME = 'confirme', 'Confirmé'
        REFUSE = 'refuse', 'Refusé'

    caisse_id = models.BigIntegerField(null=True, blank=True, db_index=True)  # dépôt indiqué par le client
    preuve_paiement = models.ImageField(upload_to='commandes/preuves/', blank=True, null=True)
    note_client = models.CharField(max_length=500, blank=True)
    paiement_statut = models.CharField(
        max_length=20,
        choices=PaiementStatut.choices,
        default=PaiementStatut.AUCUN,
        db_index=True,
    )
    depot_montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    date_commande = models.DateTimeField(db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_commande', '-commande_id']
        indexes = [
            models.Index(fields=['entreprise_id', 'date_commande']),
            models.Index(fields=['entreprise_id', 'client_id', 'date_commande']),
        ]

    @staticmethod
    def generate_id() -> str:
        return f'cmd_{secrets.token_hex(6)}'


class CommandeLigne(models.Model):
    commande_id = models.CharField(max_length=32, db_index=True)
    article_id = models.CharField(max_length=32, db_index=True)

    quantite = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal('0'))
    prix_unitaire = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    total_ligne = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['commande_id', 'article_id'])]


class ClientSoldeMouvement(models.Model):
    class Type(models.TextChoices):
        CREDIT = 'credit', 'Crédit'
        DEBIT = 'debit', 'Débit'

    entreprise_id = models.PositiveIntegerField(db_index=True)
    client_id = models.CharField(max_length=32, db_index=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    montant = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    devise = models.CharField(max_length=10, default='USD')
    date_mouvement = models.DateTimeField(db_index=True)
    source_type = models.CharField(max_length=30, blank=True)  # commande/vente/paiement
    source_id = models.CharField(max_length=64, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_mouvement', '-id']
        indexes = [
            models.Index(fields=['entreprise_id', 'client_id', 'date_mouvement']),
        ]

