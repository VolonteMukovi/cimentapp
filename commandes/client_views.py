from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import ListView, View

from articles.models import Article
from caisse.models import CaisseCompte
from commandes.models import Commande, CommandeLigne
from commandes.models import ClientSoldeMouvement
from users.constants import SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, SESSION_CLIENT_ID
from users.models import Client


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
        return Commande.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        ).order_by('-date_commande', '-commande_id')


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

        prix = art.prix_catalogue or Decimal('0')
        total_ligne = (qte * prix).quantize(Decimal('0.01'))
        caisse_id = int(caisse_id_raw) if caisse_id_raw.isdigit() else None

        with transaction.atomic():
            cmd = Commande(
                commande_id=Commande.generate_id(),
                entreprise_id=self.entreprise_id,
                client_id=str(self.client.pk),
                statut=Commande.Statut.RESERVEE,
                devise='USD',
                total=total_ligne,
                caisse_id=caisse_id,
                note_client=note,
                date_commande=timezone.now(),
            )
            if preuve:
                cmd.preuve_paiement = preuve
            cmd.save()
            CommandeLigne.objects.create(
                commande_id=cmd.commande_id,
                article_id=art.article_id,
                quantite=qte,
                prix_unitaire=prix,
                total_ligne=total_ligne,
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

        daily = qs.annotate(day=TruncDate('date_commande')).values('day').annotate(total=Sum('total')).order_by('day')
        rows = list(daily)
        results = [
            {
                'day': (r['day'].isoformat() if r['day'] else None),
                'total': str(r['total'] or Decimal('0')),
            }
            for r in rows
        ]
        total = qs.aggregate(total=Sum('total')).get('total') or Decimal('0')
        count_cmd = qs.count()
        return JsonResponse(
            {
                'results': results,
                'count': len(results),
                'page': 1,
                'page_size': 25,
                'stats': {'total': str(total), 'commandes': count_cmd},
            },
            status=200,
        )


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
        caisses = [{'id': c.id, 'nom': c.nom} for c in caisses_qs]

        return JsonResponse(
            {
                'results': {'articles': articles, 'caisses': caisses},
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

        credits = (
            ClientSoldeMouvement.objects.filter(
                entreprise_id=self.entreprise_id,
                client_id=str(self.client.pk),
                type='credit',
            )
            .aggregate(s=Sum('montant'))
            .get('s')
            or Decimal('0')
        )
        debits = (
            ClientSoldeMouvement.objects.filter(
                entreprise_id=self.entreprise_id,
                client_id=str(self.client.pk),
                type='debit',
            )
            .aggregate(s=Sum('montant'))
            .get('s')
            or Decimal('0')
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
        qs = ClientSoldeMouvement.objects.filter(
            entreprise_id=self.entreprise_id,
            client_id=str(self.client.pk),
        )
        daily = (
            qs.annotate(day=TruncDate('date_mouvement'))
            .values('day', 'type')
            .annotate(total=Sum('montant'))
            .order_by('day')
        )
        rows = list(daily)
        by_day = {}
        for r in rows:
            day = r['day'].isoformat() if r['day'] else None
            if not day:
                continue
            by_day.setdefault(day, {'credit': Decimal('0'), 'debit': Decimal('0')})
            by_day[day][r['type']] = r['total'] or Decimal('0')
        out = [
            {'day': d, 'credit': str(v.get('credit') or Decimal('0')), 'debit': str(v.get('debit') or Decimal('0'))}
            for d, v in sorted(by_day.items(), key=lambda x: x[0])
        ]
        return JsonResponse({'results': out, 'count': len(out), 'page': 1, 'page_size': 25}, status=200)

