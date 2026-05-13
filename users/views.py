from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from decimal import Decimal
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, RedirectView, TemplateView
from django.views.generic.edit import CreateView

from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.forms import AppAuthenticationForm, EntrepriseForm, SignupForm
from users.models import AffectationEntreprise, Entreprise, User
from users.navigation import staff_nav_for_user


class HomeRedirectView(RedirectView):
    """Racine : tableau de bord si connecté, sinon connexion."""

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse_lazy('dashboard')
        return reverse_lazy('login')


class AppLoginView(LoginView):
    template_name = 'users/pages/login.html'
    authentication_form = AppAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return str(reverse_lazy('dashboard'))


class AppLogoutView(LogoutView):
    next_page = reverse_lazy('login')


class SignupView(FormView):
    template_name = 'users/pages/signup.html'
    form_class = SignupForm
    success_url = reverse_lazy('entreprises_create')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx['form']
        step1_fields = ('first_name', 'last_name', 'email')
        step2_fields = ('username', 'password', 'password_confirm')
        if form.is_bound and form.errors:
            has1 = any(f in form.errors for f in step1_fields)
            has2 = any(f in form.errors for f in step2_fields)
            if has1 and not has2:
                ctx['signup_initial_step'] = 1
            elif has2 and not has1:
                ctx['signup_initial_step'] = 2
            elif has1 and has2:
                ctx['signup_initial_step'] = 1
            else:
                ctx['signup_initial_step'] = 1
        else:
            ctx['signup_initial_step'] = 1
        return ctx

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(
            self.request,
            'Compte créé. Créez maintenant votre entreprise pour accéder au tableau de bord.',
        )
        return redirect(self.get_success_url())


class EntrepriseCreateView(LoginRequiredMixin, CreateView):
    model = Entreprise
    form_class = EntrepriseForm
    template_name = 'users/pages/entreprise_form.html'

    _ENTREPRISE_WIZARD_STEPS = (
        ('nom', 'secteur', 'slogan'),
        ('pays', 'adresse', 'telephone', 'email'),
        ('nif', 'responsable', 'logo'),
    )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx['form']
        if form.is_bound and form.errors:
            if '__all__' in form.errors:
                ctx['entreprise_initial_step'] = 1
            else:
                for i, fields in enumerate(self._ENTREPRISE_WIZARD_STEPS, start=1):
                    if any(f in form.errors for f in fields):
                        ctx['entreprise_initial_step'] = i
                        break
                else:
                    ctx['entreprise_initial_step'] = 1
        else:
            ctx['entreprise_initial_step'] = 1
        return ctx

    def get_success_url(self):
        return str(reverse_lazy('dashboard'))

    def form_valid(self, form):
        with transaction.atomic():
            entreprise = form.save()
            AffectationEntreprise.objects.get_or_create(
                source=self.request.user.pk,
                entreprise=entreprise,
            )
        self.request.session[SESSION_ACTIVE_ENTREPRISE_ID] = entreprise.pk
        messages.success(self.request, f'Entreprise « {entreprise.nom} » enregistrée. Bienvenue !')
        return redirect(self.get_success_url())


class EntrepriseListView(LoginRequiredMixin, ListView):
    model = Entreprise
    template_name = 'users/pages/entreprise_list.html'
    context_object_name = 'entreprises'

    def get_queryset(self):
        return Entreprise.objects.filter(affectation_liens__source=self.request.user.pk).distinct().order_by('nom')


class EntrepriseSelectView(LoginRequiredMixin, TemplateView):
    template_name = 'users/pages/entreprise_select.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['entreprises'] = Entreprise.objects.filter(
            affectation_liens__source=self.request.user.pk,
        ).distinct().order_by('nom')
        return ctx

    def post(self, request, *args, **kwargs):
        eid = request.POST.get('entreprise_id')
        if not eid:
            messages.error(request, 'Veuillez choisir une entreprise.')
            return redirect('entreprise_select')
        if not AffectationEntreprise.objects.filter(source=request.user.pk, entreprise_id=eid).exists():
            messages.error(request, 'Entreprise non autorisée.')
            return redirect('entreprise_select')
        request.session[SESSION_ACTIVE_ENTREPRISE_ID] = int(eid)
        messages.info(request, 'Entreprise active mise à jour.')
        return redirect('dashboard')


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'users/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated and isinstance(user, User):
            if user.is_superadmin_role():
                ctx['superadmin_mode'] = True
            ctx['dashboard_store_links'] = [
                x
                for x in staff_nav_for_user(user)
                if x['id'] not in ('dashboard', 'compte')
            ]
        else:
            ctx['dashboard_store_links'] = []
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        ctx['dashboard_currency'] = 'USD'
        ctx['dashboard_total_ventes'] = Decimal('0')
        ctx['dashboard_ventes_jour'] = Decimal('0')
        ctx['dashboard_total_caisse'] = Decimal('0')
        ctx['dashboard_situation_nette'] = Decimal('0')
        ctx['dashboard_dettes_clients'] = Decimal('0')
        ctx['dashboard_commandes_en_cours'] = 0
        ctx['dashboard_caisse_ops'] = 0
        # KPI produits (articles) : compte réel en base, borné à l'entreprise active.
        # Superadmin sans entreprise active : compte global (lecture).
        try:
            from articles.models import Article

            if eid is not None:
                ctx['kpi_produits_count'] = Article.objects.filter(entreprise_id=int(eid)).count()
            elif user.is_authenticated and isinstance(user, User) and user.is_superadmin_role():
                ctx['kpi_produits_count'] = Article.objects.count()
            else:
                ctx['kpi_produits_count'] = 0
        except Exception:
            ctx['kpi_produits_count'] = 0

        if eid is not None:
            try:
                from articles.currency import get_primary_currency_code, to_primary_amount
                from caisse.models import MouvementCaisse
                from caisse.services import cash_balances_by_caisse
                from commandes.models import ClientSoldeMouvement, Commande
                from ventes.models import Vente

                eid_int = int(eid)
                ctx['dashboard_currency'] = get_primary_currency_code(eid_int)
                today = timezone.localdate()
                total_ventes = Decimal('0')
                ventes_jour = Decimal('0')
                for vente in Vente.objects.filter(entreprise_id=eid_int).only('total', 'devise', 'date_vente'):
                    amount = to_primary_amount(eid_int, vente.total, vente.devise)
                    total_ventes += amount
                    if vente.date_vente and vente.date_vente.date() == today:
                        ventes_jour += amount
                ctx['dashboard_total_ventes'] = total_ventes
                ctx['dashboard_ventes_jour'] = ventes_jour
                ctx['dashboard_total_caisse'] = sum(cash_balances_by_caisse(eid_int).values(), Decimal('0'))
                ctx['dashboard_situation_nette'] = ctx['dashboard_total_caisse']
                ctx['dashboard_caisse_ops'] = MouvementCaisse.objects.filter(entreprise_id=eid_int).count()
                ctx['dashboard_commandes_en_cours'] = Commande.objects.filter(
                    entreprise_id=eid_int,
                    statut__in=[Commande.Statut.EN_ATTENTE, Commande.Statut.RESERVEE],
                ).count()

                by_client: dict[str, Decimal] = {}
                for mv in ClientSoldeMouvement.objects.filter(entreprise_id=eid_int).only('client_id', 'type', 'montant', 'devise'):
                    signed = to_primary_amount(eid_int, mv.montant, mv.devise)
                    if mv.type == ClientSoldeMouvement.Type.DEBIT:
                        signed = -signed
                    by_client[mv.client_id] = by_client.get(mv.client_id, Decimal('0')) + signed
                ctx['dashboard_dettes_clients'] = sum((-v for v in by_client.values() if v < 0), Decimal('0'))
            except Exception:
                pass

        can_invite_client = (
            eid
            and user.is_authenticated
            and isinstance(user, User)
            and (user.is_admin_role() or user.is_superadmin_role())
        )
        if can_invite_client:
            ctx['client_invite_absolute_url'] = self.request.build_absolute_uri(
                reverse('register_client', kwargs={'entreprise_id': int(eid)}),
            )
        else:
            ctx['client_invite_absolute_url'] = ''
        return ctx


class ActivityPlaceholderView(LoginRequiredMixin, TemplateView):
    """Ecran placeholder (équivalent « Marché » de la maquette) — à brancher plus tard."""

    template_name = 'users/pages/activity_placeholder.html'


class AccountView(LoginRequiredMixin, TemplateView):
    """Profil minimal : infos utilisateur + déconnexion."""

    template_name = 'users/pages/account.html'
