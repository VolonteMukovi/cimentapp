from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from users.models import AffectationEntreprise, Client, Entreprise, User

# Champs formulaires (auth + inscriptions) — aligné thème « banking light » app
INPUT = 'mt-1 block w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-black focus:outline-none focus:ring-2 focus:ring-black/10'

INPUT_APP = INPUT


class AppAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d’utilisateur",
        widget=forms.TextInput(attrs={'class': INPUT, 'autocomplete': 'username', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT, 'autocomplete': 'current-password'}),
    )


class SignupForm(forms.ModelForm):
    """Inscription : création d'un utilisateur rôle admin (identifiant `id` généré automatiquement)."""

    password = forms.CharField(
        label='Mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': INPUT}),
    )
    password_confirm = forms.CharField(
        label='Confirmer le mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': INPUT}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        widgets = {
            'username': forms.TextInput(attrs={'class': INPUT, 'autocomplete': 'username'}),
            'email': forms.EmailInput(attrs={'class': INPUT, 'autocomplete': 'email'}),
            'first_name': forms.TextInput(attrs={'class': INPUT}),
            'last_name': forms.TextInput(attrs={'class': INPUT}),
        }

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if pwd:
            password_validation.validate_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            raise ValidationError({'password_confirm': 'Les deux mots de passe ne correspondent pas.'})
        return cleaned

    def save(self, commit=True):
        uid = User().generate_default_id()
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email') or '',
            password=self.cleaned_data['password'],
            id=uid,
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            role=User.Role.ADMIN,
        )
        return user


class EntrepriseForm(forms.ModelForm):
    class Meta:
        model = Entreprise
        fields = (
            'nom',
            'secteur',
            'pays',
            'adresse',
            'telephone',
            'email',
            'nif',
            'responsable',
            'logo',
            'slogan',
        )
        widgets = {
            'nom': forms.TextInput(attrs={'class': INPUT_APP}),
            'secteur': forms.TextInput(attrs={'class': INPUT_APP}),
            'pays': forms.TextInput(attrs={'class': INPUT_APP}),
            'adresse': forms.TextInput(attrs={'class': INPUT_APP}),
            'telephone': forms.TextInput(attrs={'class': INPUT_APP}),
            'email': forms.EmailInput(attrs={'class': INPUT_APP}),
            'nif': forms.TextInput(attrs={'class': INPUT_APP}),
            'responsable': forms.TextInput(attrs={'class': INPUT_APP}),
            'logo': forms.ClearableFileInput(attrs={'class': 'mt-1 block w-full text-sm file:mr-3 file:rounded-xl file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-black'}),
            'slogan': forms.TextInput(attrs={'class': INPUT_APP}),
        }


class RegisterClientForm(forms.Form):
    """Inscription portail client depuis un lien d’invitation entreprise."""

    nom = forms.CharField(
        label='Nom complet',
        max_length=150,
        widget=forms.TextInput(attrs={'class': INPUT, 'autocomplete': 'name', 'autofocus': True}),
    )
    email = forms.EmailField(
        label='Adresse e-mail',
        widget=forms.EmailInput(attrs={'class': INPUT, 'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT, 'autocomplete': 'new-password'}),
    )
    password_confirm = forms.CharField(
        label='Confirmer le mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT, 'autocomplete': 'new-password'}),
    )

    def __init__(self, entreprise, *args, **kwargs):
        self.entreprise = entreprise
        super().__init__(*args, **kwargs)

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if pwd:
            password_validation.validate_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            raise ValidationError({'password_confirm': 'Les deux mots de passe ne correspondent pas.'})
        email = cleaned.get('email')
        if not email or not self.entreprise:
            return cleaned
        client = Client.objects.filter(email__iexact=email).first()
        if not client:
            return cleaned
        if AffectationEntreprise.objects.filter(source=client.pk, entreprise=self.entreprise).exists():
            raise ValidationError('Ce client est déjà associé à cette entreprise.')
        pwd = cleaned.get('password') or ''
        if client.password:
            if not client.check_portal_password(pwd):
                raise ValidationError(
                    'Un compte client existe déjà avec cet e-mail. Saisissez le bon mot de passe pour confirmer le rattachement à cette entreprise.'
                )
        return cleaned


class ClientLoginForm(forms.Form):
    email = forms.EmailField(
        label='Adresse e-mail',
        widget=forms.EmailInput(attrs={'class': INPUT, 'autocomplete': 'email', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Mot de passe',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT, 'autocomplete': 'current-password'}),
    )

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()
