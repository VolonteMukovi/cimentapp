from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AffectationEntreprise, Client, Entreprise, User


class ClientAdminForm(forms.ModelForm):
    """Mot de passe saisi en clair, stocké en hash via set_portal_password."""

    portal_password = forms.CharField(
        label='Nouveau mot de passe portail',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Laisser vide pour ne pas modifier (édition) ou pas d’accès portail (création).',
    )

    class Meta:
        model = Client
        exclude = ('password',)

    def save(self, commit=True):
        obj = super().save(commit=False)
        raw = self.cleaned_data.get('portal_password')
        if raw:
            obj.set_portal_password(raw)
        elif not obj.pk:
            obj.password = None
        if commit:
            obj.save()
        return obj


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ('username',)
    list_display = ('id', 'username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('id', 'username', 'email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('id', 'username', 'password')}),
        ('Rôle et périmètre', {'fields': ('role',)}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('id', 'username', 'role', 'password1', 'password2'),
            },
        ),
    )


@admin.register(AffectationEntreprise)
class AffectationEntrepriseAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'entreprise')
    search_fields = ('source', 'entreprise__nom')


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom', 'secteur', 'pays', 'email', 'telephone', 'responsable')
    search_fields = ('nom', 'email', 'nif', 'telephone', 'responsable', 'secteur')
    list_filter = ('pays', 'secteur')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    form = ClientAdminForm
    list_display = ('id', 'nom', 'email', 'telephone', 'date_enregistrement')
    search_fields = ('id', 'nom', 'email', 'telephone')
    readonly_fields = ('date_enregistrement',)
