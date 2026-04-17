import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email=None, password=None, **extra_fields):
        user_id = extra_fields.pop('id', None)
        if not user_id:
            raise ValueError('L’identifiant id est obligatoire.')
        if not username:
            raise ValueError('Le nom d’utilisateur est obligatoire.')
        email = self.normalize_email(email) if email else ''
        user = self.model(id=user_id, username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.SUPERADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser doit avoir is_superuser=True.')
        return self.create_user(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    """
    Utilisateur applicatif : identifiant personnalisable (ex. use01) en clé primaire.
    Rôle métier pour la gestion des accès (complémentaire à is_staff / is_superuser Django).
    """

    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Super administrateur'
        ADMIN = 'admin', 'Administrateur entreprise'
        AGENT = 'agent', 'Agent'

    id = models.CharField(
        max_length=32,
        primary_key=True,
        verbose_name='Identifiant',
        help_text='Identifiant personnalisable, ex. use01.',
    )
    # Surcharge : sans UnicodeUsernameValidator (pas de restriction @/./+/-/_ uniquement)
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='nom d’utilisateur',
        help_text='150 caractères maximum.',
        validators=[],
        error_messages={
            'unique': 'Un utilisateur avec ce nom existe déjà.',
        },
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.AGENT,
        verbose_name='rôle',
        help_text=(
            'superadmin : techniciens système (accès global). '
            'admin : propriétaire ou gestionnaire d’entreprise. '
            'agent : employé, droits limités.'
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['id']

    class Meta:
        verbose_name = 'utilisateur'
        verbose_name_plural = 'utilisateurs'

    def __str__(self):
        return f'{self.id} ({self.username})'

    def is_superadmin_role(self) -> bool:
        return self.role == self.Role.SUPERADMIN

    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    def is_agent_role(self) -> bool:
        return self.role == self.Role.AGENT

    def header_avatar_initial(self) -> str:
        """
        Initiale pour l’avatar du header : 1ᵉ lettre du 3ᵉ mot du nom complet
        (ex. « Jean Pierre Dupont » → D). S’il n’y a que deux mots, on prend
        le 2ᵉ (souvent le nom) ; un seul mot → 1ᵉ lettre ; vide → initiale du username.
        """
        display = (self.get_full_name() or '').strip()
        if not display:
            u = (self.username or '').strip()
            return (u[:1] or '?').upper()
        parts = display.split()
        if len(parts) >= 3:
            target = parts[2]
        elif len(parts) == 2:
            target = parts[1]
        else:
            target = parts[0]
        if not target:
            return '?'
        return target[0].upper()

    def entreprises_autorisees(self):
        from users.models import Entreprise as EntrepriseModel

        return EntrepriseModel.objects.filter(affectation_liens__source=self.pk).distinct()

    def generate_default_id(self) -> str:
        """Identifiant unique pour inscription (ex. use_a1b2c3d4)."""
        for _ in range(50):
            candidate = f'use_{secrets.token_hex(4)}'
            if not User.objects.filter(pk=candidate).exists():
                return candidate
        raise RuntimeError('Impossible de générer un identifiant utilisateur unique.')


class Client(models.Model):
    """
    Client B2B : identifiant personnalisable (ex. cli01).
    Le champ password stocke le hash pour l’espace client (connexion e-mail), pas le texte clair.
    """

    id = models.CharField(
        max_length=32,
        primary_key=True,
        verbose_name='Identifiant',
        help_text='Identifiant personnalisable, ex. cli01.',
    )
    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(
        blank=True,
        null=True,
        unique=True,
        help_text='Identifiant de connexion portail client (unique).',
    )
    password = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name='Mot de passe (hash)',
        help_text=(
            'Hash du mot de passe pour l’espace client (connexion par e-mail). '
            'Laisser vide si le client n’a pas accès au portail.'
        ),
    )
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'client'
        verbose_name_plural = 'clients'
        ordering = ['-date_enregistrement']

    def __str__(self):
        return f'{self.id} — {self.nom}'

    def set_portal_password(self, raw_password):
        """Définit le mot de passe portail (hash). Passer None ou '' pour désactiver l’accès."""
        if raw_password:
            self.password = make_password(raw_password)
        else:
            self.password = None

    def check_portal_password(self, raw_password):
        """Vérifie le mot de passe portail contre le hash stocké."""
        if not self.password or not raw_password:
            return False
        return check_password(raw_password, self.password)

    def header_avatar_initial(self) -> str:
        """Initiale affichée dans l’en-tête portail (e-mail ou nom)."""
        if self.email:
            return self.email.strip()[:1].upper() or '?'
        if self.nom:
            return self.nom.strip()[:1].upper() or '?'
        return '?'

    @staticmethod
    def generate_default_id() -> str:
        """Identifiant unique pour un client (ex. cli_a1b2c3d4)."""
        for _ in range(50):
            candidate = f'cli_{secrets.token_hex(4)}'
            if not Client.objects.filter(pk=candidate).exists():
                return candidate
        raise RuntimeError('Impossible de générer un identifiant client unique.')


class Entreprise(models.Model):
    """Création / fiche entreprise (tenant ou société cliente du SaaS)."""

    nom = models.CharField(max_length=255)
    secteur = models.CharField(max_length=255)
    pays = models.CharField(max_length=100)
    adresse = models.CharField(max_length=255)
    telephone = models.CharField(max_length=50)
    email = models.EmailField()
    nif = models.CharField(max_length=100, verbose_name='NIF')
    responsable = models.CharField(max_length=255)
    logo = models.ImageField(
        upload_to='entreprises/logos/',
        blank=True,
        null=True,
    )
    slogan = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Devise ou slogan de l'entreprise (affiché dans l'en-tête des rapports)",
    )

    class Meta:
        verbose_name = 'entreprise'
        verbose_name_plural = 'entreprises'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class AffectationEntreprise(models.Model):
    """
    Rattachement métier ↔ entreprise : ``source`` contient la clé primaire du compte
    (``User.id`` pour le staff ou ``Client.id`` pour le portail client), sans FK explicite.
    """

    source = models.CharField(
        max_length=255,
        verbose_name='source',
        help_text='Identifiant du compte lié (pk utilisateur staff ou pk client portail).',
    )
    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name='affectation_liens',
    )

    class Meta:
        verbose_name = 'affectation entreprise'
        verbose_name_plural = 'affectations entreprise'
        constraints = [
            models.UniqueConstraint(
                fields=('source', 'entreprise'),
                name='unique_source_entreprise_affectation',
            ),
        ]

    def __str__(self):
        return f'{self.source} → {self.entreprise_id}'
