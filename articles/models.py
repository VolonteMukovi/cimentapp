"""Modèles articles : références par identifiants entiers uniquement (pas de ForeignKey)."""

from __future__ import annotations

import secrets

from django.db import models


class TypeArticle(models.Model):
    """Paramétrage système — type d’article (référencé par id numérique ailleurs)."""

    libelle = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['libelle']
        verbose_name = 'type d’article'
        verbose_name_plural = 'types d’article'

    def __str__(self) -> str:
        return self.libelle


class SousTypeArticle(models.Model):
    """Paramétrage système — sous-type rattaché à un type_article_id (int, sans FK)."""

    type_article_id = models.PositiveIntegerField(db_index=True)
    libelle = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['type_article_id', 'libelle']
        verbose_name = 'sous-type d’article'
        verbose_name_plural = 'sous-types d’article'

    def __str__(self) -> str:
        return f'{self.libelle} (#{self.type_article_id})'


class Unite(models.Model):
    """Paramétrage système — unité de mesure (référencée par unite_id)."""

    code = models.CharField(max_length=32, unique=True)
    libelle = models.CharField(max_length=128)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']
        verbose_name = 'unité'
        verbose_name_plural = 'unités'

    def __str__(self) -> str:
        return f'{self.libelle} ({self.code})'


class Article(models.Model):
    """
    Article stocké sans relations ORM : uniquement des identifiants entiers.
    `images` : liste JSON [{\"image\": \"chemin/relatif\", \"is_main\": bool}, …]
    """

    article_id = models.CharField(
        max_length=32,
        primary_key=True,
        editable=False,
        verbose_name='identifiant article',
    )
    nom = models.CharField(max_length=500, verbose_name='nom')
    sous_type_article_id = models.PositiveIntegerField(db_index=True)
    unite_id = models.PositiveIntegerField(db_index=True)
    images = models.JSONField(
        default=list,
        blank=True,
        help_text='Liste d’objets {image, is_main} ; chemins relatifs sous MEDIA.',
        verbose_name='images',
    )
    prix_catalogue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text='Prix normal (catalogue). Modifiable lors d’une vente.',
        verbose_name='prix catalogue',
    )
    entreprise_id = models.PositiveIntegerField(db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom']
        verbose_name = 'article'
        verbose_name_plural = 'articles'
        indexes = [
            models.Index(fields=['entreprise_id', 'nom']),
        ]

    def __str__(self) -> str:
        return self.nom

    @staticmethod
    def generate_article_id() -> str:
        for _ in range(50):
            candidate = f'art_{secrets.token_hex(6)}'
            if not Article.objects.filter(pk=candidate).exists():
                return candidate
        raise RuntimeError('Impossible de générer un identifiant article unique.')
