from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import ListView, View

from articles.currency import get_primary_currency_code, to_primary_amount
from articles.models import Article, Unite
from caisse.models import CaisseCompte
from commandes.models import ClientDettePaiement, ClientSoldeMouvement, Commande, CommandeLigne
from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID
from users.models import Client, Entreprise
from ventes.models import Vente, VenteFifoConsommation, VenteLigne


class ClientPortalRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        cid = request.session.get(SESSION_CLIENT_ID)
        eid = request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID)
        if not cid:
            return redirect('client_login')
        if not eid:
            return redirect('client_entreprise_select')
        self.client = Client.objects.filter(pk=cid).first()
        if not self.client:
            request.session.pop(SESSION_CLIENT_ID, None)
            request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
            return redirect('client_login')
        self.entreprise_id = int(eid)
        return super().dispatch(request, *args, **kwargs)


class ClientOrdersView(ClientPortalRequiredMixin, ListView):
    template_name = 'users/pages/client_orders.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        qs = Commande.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        )
        q = (self.request.GET.get('q') or '').strip()
        if q:
            article_ids = Article.objects.filter(
                entreprise_id=self.entreprise_id,
                nom__icontains=q,
            ).values_list('article_id', flat=True)
            matching_commands = CommandeLigne.objects.filter(
                Q(article_id__in=article_ids) | Q(article_id__icontains=q)
            ).values_list('commande_id', flat=True)
            qs = qs.filter(Q(commande_id__icontains=q) | Q(statut__icontains=q) | Q(commande_id__in=matching_commands))
        return qs.order_by('-date_commande', '-commande_id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orders = list(ctx.get('orders') or [])
        commande_ids = [o.commande_id for o in orders]
        lignes_by_cmd: dict[str, list[CommandeLigne]] = {}
        for line in CommandeLigne.objects.filter(commande_id__in=commande_ids).order_by('id'):
            lignes_by_cmd.setdefault(line.commande_id, []).append(line)
        article_ids = sorted({line.article_id for lines in lignes_by_cmd.values() for line in lines})
        articles = {
            article.article_id: article
            for article in Article.objects.filter(entreprise_id=self.entreprise_id, article_id__in=article_ids).only(
                'article_id',
                'nom',
                'unite_id',
            )
        }
        unite_ids = sorted({article.unite_id for article in articles.values()})
        unites = {unite.id: unite for unite in Unite.objects.filter(id__in=unite_ids).only('id', 'code', 'libelle')}

        ventes_by_cmd = {
            v.commande_id: v
            for v in Vente.objects.filter(entreprise_id=self.entreprise_id, commande_id__in=commande_ids).only(
                'vente_id',
                'commande_id',
                'total',
                'devise',
            )
        }
        vente_ids = [v.vente_id for v in ventes_by_cmd.values()]
        cost_by_vente: dict[str, Decimal] = {}
        for c in VenteFifoConsommation.objects.filter(vente_id__in=vente_ids).only(
            'vente_id',
            'quantite',
            'cout_unitaire_achat',
            'cout_unitaire_depenses',
        ):
            unit_cost = (c.cout_unitaire_achat or Decimal('0')) + (c.cout_unitaire_depenses or Decimal('0'))
            cost_by_vente[c.vente_id] = cost_by_vente.get(c.vente_id, Decimal('0')) + (c.quantite * unit_cost)

        for order in orders:
            lines = lignes_by_cmd.get(order.commande_id, [])
            for line in lines:
                article = articles.get(line.article_id)
                unite = unites.get(article.unite_id) if article else None
                line.client_article_nom = article.nom if article else line.article_id
                line.client_unite_mesure = (unite.libelle or unite.code) if unite else 'unite(s)'
            vente = ventes_by_cmd.get(order.commande_id)
            order.client_vente_creee = bool(vente)
            order.client_lignes = lines
            order.client_total_unites = sum((line.quantite for line in lines), Decimal('0'))
            order.client_cout_achat_reel = (cost_by_vente.get(vente.vente_id, Decimal('0')).quantize(Decimal('0.01')) if vente else Decimal('0'))
            order.client_credit_accorde = Decimal('0')
            if vente:
                depot = order.depot_montant or Decimal('0')
                credit = (vente.total or Decimal('0')) - depot
                order.client_credit_accorde = credit.quantize(Decimal('0.01')) if credit > 0 else Decimal('0')
        ctx['orders'] = orders
        ctx['object_list'] = orders
        ctx['q'] = (self.request.GET.get('q') or '').strip()
        return ctx


class ClientCommandePreuveView(ClientPortalRequiredMixin, View):
    template_name = 'commandes/payment_proof_print.html'
    http_method_names = ['get']

    def get(self, request, commande_id: str, *args, **kwargs):
        commande = Commande.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
            commande_id=commande_id,
        ).first()
        if not commande:
            raise Http404('Commande introuvable.')
        vente = Vente.objects.filter(entreprise_id=self.entreprise_id, commande_id=commande.commande_id).first()
        if not vente:
            raise Http404('La preuve sera disponible apres creation de la vente.')
        caisse = (
            CaisseCompte.objects.filter(entreprise_id=self.entreprise_id, pk=commande.caisse_id).first()
            if commande.caisse_id
            else None
        )
        vente_lignes = list(VenteLigne.objects.filter(vente_id=vente.vente_id).order_by('id'))
        article_ids = [line.article_id for line in vente_lignes]
        articles = {
            article.article_id: article
            for article in Article.objects.filter(
                entreprise_id=self.entreprise_id,
                article_id__in=article_ids,
            ).only('article_id', 'nom', 'unite_id')
        }
        unite_ids = [article.unite_id for article in articles.values()]
        unites = {unite.id: unite for unite in Unite.objects.filter(id__in=unite_ids).only('id', 'libelle', 'code')}
        produits = []
        for line in vente_lignes:
            article = articles.get(line.article_id)
            unite = unites.get(article.unite_id) if article else None
            produits.append(
                {
                    'nom': article.nom if article else line.article_id,
                    'quantite': line.quantite,
                    'unite': (unite.libelle or unite.code) if unite else '',
                    'prix_unitaire': line.prix_unitaire_vente,
                }
            )
        return render(
            request,
            self.template_name,
            {
                'entreprise': Entreprise.objects.filter(pk=self.entreprise_id).first(),
                'client': self.client,
                'caisse': caisse,
                'payment': commande,
                'vente': vente,
                'produits': produits,
                'proof_type': 'commande',
                'reference': commande.commande_id,
                'montant': commande.depot_montant,
                'devise': commande.devise,
                'statut': commande.get_paiement_statut_display(),
                'date_operation': commande.date_commande,
                'note': commande.note_client,
                'preuve_url': commande.preuve_paiement.url if commande.preuve_paiement else '',
            },
        )


class ClientOrderCreateView(ClientPortalRequiredMixin, View):
    template_name = 'users/pages/client_order_create.html'
    http_method_names = ['get', 'post']

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {})

    # Form minimal via POST direct (sans ModelForm pour garder léger)
    def post(self, request, *args, **kwargs):
        article_id = (request.POST.get('article_id') or '').strip()
        qte_raw = (request.POST.get('quantite') or '').strip()
        note = (request.POST.get('note_client') or '').strip()[:500]
        caisse_id_raw = (request.POST.get('caisse_id') or '').strip()
        preuve = request.FILES.get('preuve_paiement')

        art = Article.objects.filter(entreprise_id=self.entreprise_id, article_id=article_id).first()
        if not art:
            messages.error(request, 'Article introuvable.')
            return redirect('client_catalogue')
        try:
            qte = Decimal(qte_raw)
        except Exception:
            qte = Decimal('0')
        if qte <= 0:
            messages.error(request, 'Quantité invalide.')
            return redirect('client_catalogue')

        caisse_id = int(caisse_id_raw) if caisse_id_raw.isdigit() else None

        with transaction.atomic():
            cmd = Commande(
                commande_id=Commande.generate_id(),
                entreprise_id=self.entreprise_id,
                client_id=str(self.client.pk),
                statut=Commande.Statut.EN_ATTENTE,
                devise=get_primary_currency_code(self.entreprise_id),
                total=Decimal('0'),
                caisse_id=caisse_id,
                note_client=note,
                paiement_statut=Commande.PaiementStatut.EN_ATTENTE if (caisse_id or preuve) else Commande.PaiementStatut.AUCUN,
                date_commande=timezone.now(),
            )
            if preuve:
                cmd.preuve_paiement = preuve
            cmd.save()
            CommandeLigne.objects.create(
                commande_id=cmd.commande_id,
                article_id=art.article_id,
                quantite=qte,
                prix_unitaire=Decimal('0'),
                total_ligne=Decimal('0'),
            )

        messages.success(request, 'Commande enregistrée.')
        return redirect('/fr/client/commandes/')


class ClientOrdersStatsApiView(ClientPortalRequiredMixin, View):
    """
    Stats globales commandes du client (par jour).
    GET ?date_from=...&date_to=...
    """

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        qs = Commande.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        )

        dt_from = (request.GET.get('date_from') or '').strip()
        dt_to = (request.GET.get('date_to') or '').strip()
        if dt_from:
            try:
                qs = qs.filter(date_commande__gte=datetime.fromisoformat(dt_from))
            except Exception:
                pass
        if dt_to:
            try:
                qs = qs.filter(date_commande__lte=datetime.fromisoformat(dt_to))
            except Exception:
                pass

        by_day = {}
        total = Decimal('0')
        for cmd in qs.only('date_commande', 'total', 'devise'):
            day = cmd.date_commande.date().isoformat() if cmd.date_commande else None
            if not day:
                continue
            amount = to_primary_amount(self.entreprise_id, cmd.total, cmd.devise)
            by_day[day] = by_day.get(day, Decimal('0')) + amount
            total += amount
        results = [{'day': day, 'total': str(amount)} for day, amount in sorted(by_day.items(), key=lambda item: item[0])]
        count_cmd = qs.count()
        return JsonResponse(
            {
                'results': results,
                'count': len(results),
                'page': 1,
                'page_size': 25,
                'stats': {'total': str(total), 'commandes': count_cmd, 'devise_principale': get_primary_currency_code(self.entreprise_id)},
            },
            status=200,
        )


class ClientDettePaiementCreateView(ClientPortalRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        caisse_id_raw = (request.POST.get('caisse_id') or '').strip()
        montant_raw = (request.POST.get('montant') or '').strip()
        note = (request.POST.get('note_client') or '').strip()[:500]
        preuve = request.FILES.get('preuve_paiement')

        if not caisse_id_raw.isdigit():
            messages.error(request, 'Veuillez choisir un sous-compte caisse.')
            return redirect('client_wallet')
        caisse_id = int(caisse_id_raw)
        if not CaisseCompte.objects.filter(entreprise_id=self.entreprise_id, actif=True, pk=caisse_id).exists():
            messages.error(request, 'Sous-compte caisse invalide.')
            return redirect('client_wallet')
        try:
            montant = Decimal(montant_raw)
        except Exception:
            montant = Decimal('0')
        if montant <= 0:
            messages.error(request, 'Montant invalide.')
            return redirect('client_wallet')
        if not preuve:
            messages.error(request, 'Veuillez joindre une preuve de paiement.')
            return redirect('client_wallet')

        ClientDettePaiement.objects.create(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
            caisse_id=caisse_id,
            montant=montant,
            devise=get_primary_currency_code(self.entreprise_id),
            preuve_paiement=preuve,
            note_client=note,
            date_soumission=timezone.now(),
        )
        messages.success(request, 'Paiement transmis. Il sera pris en compte apres confirmation.')
        return redirect('client_wallet')


class ClientDettePaiementsApiView(ClientPortalRequiredMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        qs = ClientDettePaiement.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        ).order_by('-date_soumission', '-id')
        rows, count, page, page_size = _paginate(qs, request, default_page_size=10)
        results = [
            {
                'id': row.id,
                'caisse_id': row.caisse_id,
                'montant': str(row.montant),
                'devise': row.devise,
                'statut': row.statut,
                'date_soumission': row.date_soumission.isoformat(),
            }
            for row in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class ClientOrderLookupsApiView(ClientPortalRequiredMixin, View):
    """Lookups pour UI (articles + caisses actives) sans saisir d'IDs."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        # Articles (limite pour perf, recherche optionnelle)
        q = (request.GET.get('q') or '').strip()
        aqs = Article.objects.filter(entreprise_id=self.entreprise_id)
        if q:
            aqs = aqs.filter(nom__icontains=q)
        aqs = aqs.order_by('nom')[:200]
        articles = [
            {
                'article_id': a.article_id,
                'nom': a.nom,
                'prix_catalogue': str(a.prix_catalogue),
            }
            for a in aqs
        ]

        caisses_qs = CaisseCompte.objects.filter(entreprise_id=self.entreprise_id, actif=True).order_by('nom')[:200]
        caisses = [
            {
                'id': c.id,
                'nom': c.nom,
                'banque_nom': c.banque_nom,
                'compte_intitule': c.compte_intitule,
                'numero_compte': c.numero_compte,
            }
            for c in caisses_qs
        ]

        return JsonResponse(
            {
                'results': {
                    'articles': articles,
                    'caisses': caisses,
                    'devise_principale': get_primary_currency_code(self.entreprise_id),
                },
                'count': len(articles) + len(caisses),
                'page': 1,
                'page_size': 25,
            },
            status=200,
        )


class ClientSoldeApiView(ClientPortalRequiredMixin, View):
    """Solde garantie/dette du client (dynamique, sans données test)."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        from commandes.models import ClientSoldeMouvement

        credits = sum(
            (
                to_primary_amount(self.entreprise_id, row.montant, row.devise)
                for row in ClientSoldeMouvement.objects.filter(
                    entreprise_id=self.entreprise_id,
                    client_id=str(self.client.pk),
                    type='credit',
                ).only('montant', 'devise')
            ),
            Decimal('0'),
        )
        debits = sum(
            (
                to_primary_amount(self.entreprise_id, row.montant, row.devise)
                for row in ClientSoldeMouvement.objects.filter(
                    entreprise_id=self.entreprise_id,
                    client_id=str(self.client.pk),
                    type='debit',
                ).only('montant', 'devise')
            ),
            Decimal('0'),
        )
        solde = credits - debits
        garantie = solde if solde > 0 else Decimal('0')
        dette = (solde * Decimal('-1')) if solde < 0 else Decimal('0')
        return JsonResponse(
            {
                'results': [],
                'count': 0,
                'page': 1,
                'page_size': 25,
                'stats': {
                    'solde': str(solde),
                    'garantie': str(garantie),
                    'dette': str(dette),
                    'devise_principale': get_primary_currency_code(self.entreprise_id),
                },
            },
            status=200,
        )


def _paginate(qs, request, *, default_page_size: int = 25):
    try:
        page = int(request.GET.get('page') or 1)
    except Exception:
        page = 1
    if page < 1:
        page = 1
    try:
        page_size = int(request.GET.get('page_size') or default_page_size)
    except Exception:
        page_size = default_page_size
    if page_size < 1:
        page_size = default_page_size
    if page_size > 200:
        page_size = 200
    count = qs.count()
    offset = (page - 1) * page_size
    results = list(qs[offset : offset + page_size])
    return results, count, page, page_size


class ClientTransactionsView(ClientPortalRequiredMixin, View):
    template_name = 'users/pages/client_transactions.html'
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {})


class ClientTransactionsApiView(ClientPortalRequiredMixin, View):
    """Timeline des mouvements client (garantie/dette) sur entreprise active."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        qs = ClientSoldeMouvement.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        ).order_by('-date_mouvement', '-id')
        rows, count, page, page_size = _paginate(qs, request, default_page_size=25)
        results = [
            {
                'id': r.id,
                'type': r.type,
                'montant': str(r.montant),
                'devise': r.devise,
                'montant_principal': str(to_primary_amount(self.entreprise_id, r.montant, r.devise)),
                'devise_principale': get_primary_currency_code(self.entreprise_id),
                'date_mouvement': r.date_mouvement.isoformat(),
                'source_type': r.source_type,
                'source_id': r.source_id,
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class ClientTransactionsStatsApiView(ClientPortalRequiredMixin, View):
    """Stats par jour (crédit/débit) pour graphique."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        by_day = {}
        for r in ClientSoldeMouvement.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        ).only('date_mouvement', 'type', 'montant', 'devise'):
            day = r.date_mouvement.date().isoformat() if r.date_mouvement else None
            if not day:
                continue
            by_day.setdefault(day, {'credit': Decimal('0'), 'debit': Decimal('0')})
            by_day[day][r.type] = by_day[day].get(r.type, Decimal('0')) + to_primary_amount(
                self.entreprise_id,
                r.montant,
                r.devise,
            )
        out = [
            {'day': d, 'credit': str(v.get('credit') or Decimal('0')), 'debit': str(v.get('debit') or Decimal('0'))}
            for d, v in sorted(by_day.items(), key=lambda x: x[0])
        ]
        return JsonResponse(
            {'results': out, 'count': len(out), 'page': 1, 'page_size': 25, 'devise_principale': get_primary_currency_code(self.entreprise_id)},
            status=200,
        )

