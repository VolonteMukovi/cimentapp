"""Portail client (invitation, inscription, multi-entreprise)."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID
from users.forms import ClientLoginForm, RegisterClientForm
from users.models import AffectationEntreprise, Client, Entreprise


class RegisterClientView(FormView):
    template_name = 'users/pages/register_client.html'
    form_class = RegisterClientForm

    def dispatch(self, request, *args, **kwargs):
        self.entreprise = Entreprise.objects.filter(pk=kwargs['entreprise_id']).first()
        if not self.entreprise:
            return render(
                request,
                'users/pages/register_client_bad_entreprise.html',
                status=404,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['entreprise'] = self.entreprise
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['entreprise'] = self.entreprise
        return ctx

    def form_valid(self, form):
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        nom = form.cleaned_data['nom'].strip()
        existing = Client.objects.filter(email__iexact=email).first()
        with transaction.atomic():
            if existing:
                if not existing.password:
                    existing.set_portal_password(password)
                    if nom:
                        existing.nom = nom
                    existing.save()
                AffectationEntreprise.objects.get_or_create(
                    source=existing.pk,
                    entreprise=self.entreprise,
                )
                messages.success(
                    self.request,
                    'Votre compte existant a été rattaché à cette entreprise. Vous pouvez vous connecter.',
                )
            else:
                client = Client(
                    id=Client.generate_default_id(),
                    nom=nom,
                    email=email,
                )
                client.set_portal_password(password)
                client.save()
                AffectationEntreprise.objects.create(source=client.pk, entreprise=self.entreprise)
                messages.success(
                    self.request,
                    'Compte client créé. Vous pouvez vous connecter.',
                )
        return redirect('client_login')


class ClientLoginView(FormView):
    template_name = 'users/pages/client_login.html'
    form_class = ClientLoginForm
    success_url = reverse_lazy('client_portal_home')

    def dispatch(self, request, *args, **kwargs):
        if request.session.get(SESSION_CLIENT_ID):
            return redirect('client_portal_home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        client = Client.objects.filter(email__iexact=email).first()
        if not client or not client.check_portal_password(password):
            messages.error(self.request, 'E-mail ou mot de passe incorrect.')
            return self.form_invalid(form)
        self.request.session[SESSION_CLIENT_ID] = client.pk
        self.request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
        n = AffectationEntreprise.objects.filter(source=client.pk).count()
        if n == 0:
            messages.warning(self.request, 'Aucune entreprise associée à ce compte.')
            return redirect('client_login')
        if n > 1:
            return redirect('client_entreprise_select')
        eid = AffectationEntreprise.objects.filter(source=client.pk).values_list('entreprise_id', flat=True).first()
        self.request.session[SESSION_CLIENT_ACTIVE_ENTREPRISE_ID] = eid
        messages.success(self.request, 'Bienvenue sur votre espace client.')
        return redirect(self.get_success_url())


class ClientLogoutView(View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        request.session.pop(SESSION_CLIENT_ID, None)
        request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
        messages.info(request, 'Vous êtes déconnecté.')
        return redirect('client_login')


class ClientEntrepriseSelectView(TemplateView):
    template_name = 'users/pages/client_select_entreprise.html'

    def dispatch(self, request, *args, **kwargs):
        cid = request.session.get(SESSION_CLIENT_ID)
        if not cid:
            return redirect('client_login')
        self.client = Client.objects.filter(pk=cid).first()
        if not self.client:
            request.session.pop(SESSION_CLIENT_ID, None)
            return redirect('client_login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['client'] = self.client
        ctx['entreprises'] = Entreprise.objects.filter(
            affectation_liens__source=self.client.pk,
        ).distinct().order_by('nom')
        return ctx

    def post(self, request, *args, **kwargs):
        eid = request.POST.get('entreprise_id')
        if not eid:
            messages.error(request, 'Veuillez choisir une entreprise.')
            return redirect('client_entreprise_select')
        if not AffectationEntreprise.objects.filter(source=self.client.pk, entreprise_id=eid).exists():
            messages.error(request, 'Entreprise non autorisée.')
            return redirect('client_entreprise_select')
        request.session[SESSION_CLIENT_ACTIVE_ENTREPRISE_ID] = int(eid)
        messages.info(request, 'Entreprise active mise à jour.')
        return redirect('client_portal_home')


class ClientPortalHomeView(TemplateView):
    template_name = 'users/pages/client_portal_home.html'


class ClientCatalogSimView(TemplateView):
    """Simulation — gestion articles / catalogue (cahier des charges)."""

    template_name = 'users/pages/client_portal/sim_page.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sim_title'] = 'Catalogue & articles'
        ctx['sim_intro'] = (
            'Prévu : fiches articles avec images, prix catalogue fixe, '
            'et possibilité d’ajuster le prix unitaire lors d’une vente selon le client.'
        )
        ctx['sim_points'] = [
            'Enregistrement des articles avec visuels.',
            'Prix de référence + personnalisation à la vente.',
            'Affichage des images dans l’espace commande client.',
        ]
        return ctx


class ClientCatalogView(TemplateView):
    """Catalogue réel : articles de l'entreprise active + images + prix catalogue."""

    template_name = 'users/pages/client_catalogue.html'

    def dispatch(self, request, *args, **kwargs):
        from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID

        if not request.session.get(SESSION_CLIENT_ID):
            return redirect('client_login')
        if not request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID):
            return redirect('client_entreprise_select')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID
        from users.models import Client
        from articles.models import Article
        from django.conf import settings

        cid = self.request.session.get(SESSION_CLIENT_ID)
        eid = int(self.request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID))
        client = Client.objects.filter(pk=cid).first()
        ctx['client'] = client
        ctx['entreprise_id'] = eid

        q = (self.request.GET.get('q') or '').strip()
        qs = Article.objects.filter(entreprise_id=eid)
        if q:
            qs = qs.filter(nom__icontains=q)
        qs = qs.order_by('nom')

        try:
            page = int(self.request.GET.get('page') or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        page_size = 12
        total = qs.count()
        offset = (page - 1) * page_size
        items = list(qs[offset : offset + page_size])

        mu = settings.MEDIA_URL
        if not str(mu).endswith('/'):
            mu = f'{mu}/'
        rows = []
        for a in items:
            main_img = ''
            if isinstance(a.images, list):
                for im in a.images:
                    if isinstance(im, dict) and im.get('image') and im.get('is_main'):
                        main_img = f"{mu}{str(im['image']).lstrip('/')}"
                        break
                if not main_img:
                    for im in a.images:
                        if isinstance(im, dict) and im.get('image'):
                            main_img = f"{mu}{str(im['image']).lstrip('/')}"
                            break
            rows.append(
                {
                    'article_id': a.article_id,
                    'nom': a.nom,
                    'prix_catalogue': a.prix_catalogue,
                    'image': main_img,
                }
            )

        ctx['q'] = q
        ctx['page'] = page
        ctx['page_size'] = page_size
        ctx['count'] = total
        ctx['has_prev'] = page > 1
        ctx['has_next'] = (offset + page_size) < total
        ctx['results'] = rows
        return ctx


class ClientTransactionsSimView(TemplateView):
    """Simulation — historique des transactions (paiements, mouvements)."""

    template_name = 'users/pages/client_portal/sim_page.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sim_title'] = 'Historique des transactions'
        ctx['sim_intro'] = (
            'Prévu : liste chronologique des paiements, mouvements de garantie, '
            'règlements de dettes et statuts associés à l’entreprise active.'
        )
        ctx['sim_points'] = [
            'Filtre par période et par type (commande, acompte, solde).',
            'Lien vers la commande ou le document source.',
            'Export ou partage (phase ultérieure).',
        ]
        return ctx


class ClientTransactionsView(TemplateView):
    """Historique réel (les données viennent des APIs client sous /fr/client/commandes/api/...)."""

    template_name = 'users/pages/client_transactions.html'


class ClientOrdersSimView(TemplateView):
    """Simulation — commandes client."""

    template_name = 'users/pages/client_portal/sim_page.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sim_title'] = 'Mes commandes'
        ctx['sim_intro'] = (
            'Prévu : passer commande avec preuve de paiement ou choix d’un sous-compte caisse '
            '(Cash, Coopec, Equity, etc.), ou envoi WhatsApp en alternative.'
        )
        ctx['sim_points'] = [
            'Soumission de preuve de paiement.',
            'Choix du sous-compte de dépôt (mouvement de caisse).',
            'Historique filtré par entreprise active.',
        ]
        return ctx


class ClientWalletSimView(TemplateView):
    """Simulation — caisse, sous-comptes, garantie d’achat."""

    template_name = 'users/pages/client_portal/sim_page.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sim_title'] = 'Solde & garantie d’achat'
        ctx['sim_intro'] = (
            'Prévu : compte cash principal et sous-comptes (Caisse Cash, Coopec Sadac Beni, '
            'Coopec Sadac Kasindi, Coopec Paidec, Equity BCDC, Dépôt Neema…). '
            'Un mouvement sur commande augmente la garantie affichée (ex. +1000 $) ; dette en crédit ajustée automatiquement au règlement.'
        )
        ctx['sim_points'] = [
            'Entrées clients vers sous-comptes identifiés.',
            'Sorties depuis un sous-compte précis.',
            'Lecture comptant / crédit à partir du solde garantie sur le tableau de bord.',
        ]
        return ctx


class ClientWalletView(TemplateView):
    """Vue réelle (simple) : activité commandes + total réservé sur entreprise active."""

    template_name = 'users/pages/client_wallet.html'

    def dispatch(self, request, *args, **kwargs):
        from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID

        if not request.session.get(SESSION_CLIENT_ID):
            return redirect('client_login')
        if not request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID):
            return redirect('client_entreprise_select')
        return super().dispatch(request, *args, **kwargs)

