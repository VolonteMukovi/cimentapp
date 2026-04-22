from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from lots.models import DepenseLot, LotStock
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import User
from users.navigation import can_access_store_module


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # accepte YYYY-MM-DD ou ISO
        if len(value) == 10:
            return datetime.fromisoformat(value + 'T00:00:00')
        return datetime.fromisoformat(value)
    except Exception:
        return None


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


class LotsAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'lots'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class LotStockListView(LotsAccessMixin, TemplateView):
    template_name = 'lots/lots_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'lots'
        ctx['store_module_title'] = 'Lots produits'
        ctx['MEDIA_URL'] = settings.MEDIA_URL
        return ctx


class LotStockApiListView(LotsAccessMixin, View):
    """GET paginé des lots (sans FK)."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = LotStock.objects.filter(entreprise_id=eid).order_by('-date_entree', '-id')

        article_id = (request.GET.get('article_id') or '').strip()
        if article_id:
            qs = qs.filter(article_id=article_id)

        dt_from = _parse_dt(request.GET.get('date_from'))
        dt_to = _parse_dt(request.GET.get('date_to'))
        if dt_from:
            qs = qs.filter(date_entree__gte=dt_from)
        if dt_to:
            qs = qs.filter(date_entree__lte=dt_to)

        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'id': r.id,
                'entreprise_id': r.entreprise_id,
                'article_id': r.article_id,
                'reference': r.reference,
                'quantite_entree': str(r.quantite_entree),
                'quantite_restante': str(r.quantite_restante),
                'cout_unitaire_achat': str(r.cout_unitaire_achat),
                'date_entree': r.date_entree.isoformat(),
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class LotStockCreateApiView(LotsAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        article_id = (payload.get('article_id') or '').strip()
        if not article_id:
            return JsonResponse({'ok': False, 'error': 'article_id requis.'}, status=400)

        try:
            qte = Decimal(str(payload.get('quantite_entree') or '0'))
        except Exception:
            qte = Decimal('0')
        if qte <= 0:
            return JsonResponse({'ok': False, 'error': 'quantite_entree doit être > 0.'}, status=400)

        try:
            cout = Decimal(str(payload.get('cout_unitaire_achat') or '0'))
        except Exception:
            cout = Decimal('0')
        if cout < 0:
            return JsonResponse({'ok': False, 'error': 'cout_unitaire_achat invalide.'}, status=400)

        reference = (payload.get('reference') or '').strip()[:255]
        dt_raw = payload.get('date_entree')
        if dt_raw:
            dt = _parse_dt(str(dt_raw))
            dt = dt or timezone.now()
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
        else:
            dt = timezone.now()

        obj = LotStock.objects.create(
            entreprise_id=eid,
            article_id=article_id,
            reference=reference,
            quantite_entree=qte,
            quantite_restante=qte,
            cout_unitaire_achat=cout,
            date_entree=dt,
        )
        return JsonResponse({'ok': True, 'id': obj.id}, status=201)


class DepenseLotCreateApiView(LotsAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, lot_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)

        lot = LotStock.objects.filter(entreprise_id=eid, id=lot_id).first()
        if not lot:
            return JsonResponse({'ok': False, 'error': 'Lot introuvable.'}, status=404)

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        libelle = (payload.get('libelle') or '').strip()[:255]
        if not libelle:
            return JsonResponse({'ok': False, 'error': 'libelle requis.'}, status=400)

        try:
            montant = Decimal(str(payload.get('montant') or '0'))
        except Exception:
            montant = Decimal('0')
        if montant < 0:
            return JsonResponse({'ok': False, 'error': 'montant invalide.'}, status=400)

        dt_raw = payload.get('date_depense')
        if dt_raw:
            dt = _parse_dt(str(dt_raw)) or timezone.now()
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
        else:
            dt = timezone.now()

        obj = DepenseLot.objects.create(
            entreprise_id=eid,
            lot_id=lot.id,
            libelle=libelle,
            montant=montant,
            date_depense=dt,
        )
        return JsonResponse({'ok': True, 'id': obj.id}, status=201)


class StockRestantApiView(LotsAccessMixin, View):
    """GET stock restant par article (pagination + filtres)."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = (
            LotStock.objects.filter(entreprise_id=eid)
            .values('article_id')
            .annotate(quantite_restante=Sum('quantite_restante'))
            .order_by('-article_id')
        )

        article_id = (request.GET.get('article_id') or '').strip()
        if article_id:
            qs = qs.filter(article_id=article_id)

        # pagination sur queryset values()
        try:
            page = int(request.GET.get('page') or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        try:
            page_size = int(request.GET.get('page_size') or 25)
        except Exception:
            page_size = 25
        if page_size < 1:
            page_size = 25
        if page_size > 200:
            page_size = 200

        count = qs.count()
        offset = (page - 1) * page_size
        rows = list(qs[offset : offset + page_size])
        results = [
            {
                'article_id': r['article_id'],
                'quantite_restante': str(r['quantite_restante'] or Decimal('0')),
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class StockStatsApiView(LotsAccessMixin, View):
    """
    Stats globales stock (rapide) pour graphiques.
    GET ?top_n=8
    """

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse(
                {'results': [], 'count': 0, 'page': 1, 'page_size': 25, 'stats': {'stock_total': '0'}},
                status=200,
            )

        try:
            top_n = int(request.GET.get('top_n') or 8)
        except Exception:
            top_n = 8
        if top_n < 1:
            top_n = 8
        if top_n > 50:
            top_n = 50

        qs = (
            LotStock.objects.filter(entreprise_id=eid)
            .values('article_id')
            .annotate(quantite_restante=Sum('quantite_restante'))
            .order_by('-quantite_restante')
        )

        rows = list(qs[:top_n])
        results = [
            {
                'article_id': r['article_id'],
                'quantite_restante': str(r['quantite_restante'] or Decimal('0')),
            }
            for r in rows
        ]
        stock_total = qs.aggregate(total=Sum('quantite_restante')).get('total') or Decimal('0')
        return JsonResponse(
            {
                'results': results,
                'count': len(results),
                'page': 1,
                'page_size': 25,
                'stats': {'stock_total': str(stock_total)},
            },
            status=200,
        )

