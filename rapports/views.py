from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from caisse.models import MouvementCaisse
from lots.models import DepenseLot, LotStock
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import User
from users.navigation import can_access_store_module
from ventes.models import Vente, VenteFifoConsommation, VenteLigne


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


class RapportsAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'rapports'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class RapportsHomeView(RapportsAccessMixin, TemplateView):
    template_name = 'rapports/rapports_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'rapports'
        ctx['store_module_title'] = 'Rapports'
        return ctx


class BeneficesParLotApiView(RapportsAccessMixin, View):
    """
    Agrégation bénéfice par lot:
    bénéfice = CA - (coût_achat + dépenses_lot_prorata)
    """

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        dt_from = request.GET.get('date_from')
        dt_to = request.GET.get('date_to')

        ventes = Vente.objects.filter(entreprise_id=eid)
        if dt_from:
            try:
                ventes = ventes.filter(date_vente__gte=datetime.fromisoformat(dt_from))
            except Exception:
                pass
        if dt_to:
            try:
                ventes = ventes.filter(date_vente__lte=datetime.fromisoformat(dt_to))
            except Exception:
                pass
        vente_ids = list(ventes.values_list('vente_id', flat=True))
        if not vente_ids:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        # consommation FIFO groupée par lot (coûts FIFO)
        cons = (
            VenteFifoConsommation.objects.filter(vente_id__in=vente_ids)
            .values('lot_id', 'article_id')
            .annotate(
                qte=Sum('quantite'),
                cout_achat=Sum(F('quantite') * F('cout_unitaire_achat')),
                cout_dep=Sum(F('quantite') * F('cout_unitaire_depenses')),
            )
            .order_by('-lot_id')
        )

        cons_rows, count, page, page_size = _paginate(cons, request)

        lot_ids = [r['lot_id'] for r in cons_rows]
        lots = {x.id: x for x in LotStock.objects.filter(entreprise_id=eid, id__in=lot_ids)}

        # CA par lot: consommation détaillée -> lignes -> prix_unitaire_vente
        cons_detail = list(
            VenteFifoConsommation.objects.filter(lot_id__in=lot_ids, vente_id__in=vente_ids).values(
                'lot_id',
                'vente_ligne_id',
                'quantite',
            )
        )
        line_ids = [x['vente_ligne_id'] for x in cons_detail]
        line_prices = {
            x.id: (x.prix_unitaire_vente or Decimal('0'))
            for x in VenteLigne.objects.filter(id__in=line_ids).only('id', 'prix_unitaire_vente')
        }
        ca_by_lot: dict[int, Decimal] = {}
        for row in cons_detail:
            lot_id = int(row['lot_id'])
            qte = row['quantite'] or Decimal('0')
            prix = line_prices.get(int(row['vente_ligne_id']), Decimal('0'))
            ca_by_lot[lot_id] = ca_by_lot.get(lot_id, Decimal('0')) + (qte * prix)

        # dépenses totales par lot (info)
        exp = (
            DepenseLot.objects.filter(entreprise_id=eid, lot_id__in=lot_ids)
            .values('lot_id')
            .annotate(total=Sum('montant'))
        )
        exp_map = {e['lot_id']: (e['total'] or Decimal('0')) for e in exp}

        results = []
        for r in cons_rows:
            lot = lots.get(r['lot_id'])
            ca = ca_by_lot.get(int(r['lot_id']), Decimal('0'))
            cout = (r['cout_achat'] or Decimal('0')) + (r['cout_dep'] or Decimal('0'))
            benef = ca - cout
            results.append(
                {
                    'lot_id': r['lot_id'],
                    'article_id': r['article_id'],
                    'quantite_vendue_fifo': str(r['qte'] or Decimal('0')),
                    'chiffre_affaires': str(ca),
                    'cout_total_fifo': str(cout),
                    'depenses_lot_total': str(exp_map.get(r['lot_id'], Decimal('0'))),
                    'benefice_estime': str(benef),
                    'lot_date_entree': lot.date_entree.isoformat() if lot else None,
                }
            )

        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class RapportsStatsApiView(RapportsAccessMixin, View):
    """
    Stats globales bénéfices pour graphiques (par jour).
    CA: somme(Vente.total) par jour.
    COGS: somme FIFO (achat + depenses unitaires) rattachée à la date de la vente.
    GET ?date_from=...&date_to=...
    """

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse(
                {
                    'results': [],
                    'count': 0,
                    'page': 1,
                    'page_size': 25,
                    'stats': {'total_ca': '0.00', 'total_cogs': '0.00', 'total_benef': '0.00'},
                },
                status=200,
            )

        ventes = Vente.objects.filter(entreprise_id=eid)
        dt_from = request.GET.get('date_from')
        dt_to = request.GET.get('date_to')
        if dt_from:
            try:
                ventes = ventes.filter(date_vente__gte=datetime.fromisoformat(dt_from))
            except Exception:
                pass
        if dt_to:
            try:
                ventes = ventes.filter(date_vente__lte=datetime.fromisoformat(dt_to))
            except Exception:
                pass

        vente_map = {v.vente_id: v.date_vente.date() for v in ventes.only('vente_id', 'date_vente')}
        if not vente_map:
            return JsonResponse(
                {
                    'results': [],
                    'count': 0,
                    'page': 1,
                    'page_size': 25,
                    'stats': {'total_ca': '0.00', 'total_cogs': '0.00', 'total_benef': '0.00'},
                },
                status=200,
            )

        # CA par jour (SQL)
        ca_daily = (
            ventes.annotate(day=TruncDate('date_vente'))
            .values('day')
            .annotate(ca=Sum('total'))
            .order_by('day')
        )
        ca_by_day = {r['day']: (r['ca'] or Decimal('0')) for r in ca_daily}

        # COGS par vente (SQL), puis regroupement par jour en Python
        cogs_rows = (
            VenteFifoConsommation.objects.filter(vente_id__in=list(vente_map.keys()))
            .values('vente_id')
            .annotate(
                cogs=Sum(F('quantite') * (F('cout_unitaire_achat') + F('cout_unitaire_depenses'))),
            )
        )
        cogs_by_day: dict[datetime.date, Decimal] = {}
        for r in cogs_rows:
            vid = r['vente_id']
            day = vente_map.get(vid)
            if not day:
                continue
            cogs_by_day[day] = cogs_by_day.get(day, Decimal('0')) + (r['cogs'] or Decimal('0'))

        # union days
        all_days = sorted(set(list(ca_by_day.keys()) + list(cogs_by_day.keys())))
        results = []
        total_ca = Decimal('0')
        total_cogs = Decimal('0')
        for day in all_days:
            ca = ca_by_day.get(day, Decimal('0'))
            cogs = cogs_by_day.get(day, Decimal('0'))
            benef = ca - cogs
            total_ca += ca
            total_cogs += cogs
            results.append(
                {
                    'day': day.isoformat(),
                    'ca': str(ca),
                    'cogs': str(cogs),
                    'benefice': str(benef),
                }
            )

        return JsonResponse(
            {
                'results': results,
                'count': len(results),
                'page': 1,
                'page_size': 25,
                'stats': {'total_ca': str(total_ca), 'total_cogs': str(total_cogs), 'total_benef': str(total_ca - total_cogs)},
            },
            status=200,
        )

