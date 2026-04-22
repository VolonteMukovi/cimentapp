from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.http import JsonResponse
from django.views.generic import TemplateView, View

from caisse.models import CaisseCompte, MouvementCaisse
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import User
from users.navigation import can_access_store_module


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


class CaisseAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'caisse'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class CaisseHomeView(CaisseAccessMixin, TemplateView):
    template_name = 'caisse/caisse_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'caisse'
        ctx['store_module_title'] = 'Caisse & sous-comptes'
        return ctx


class CaisseApiListView(CaisseAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = CaisseCompte.objects.filter(entreprise_id=eid).order_by('-date_creation', '-id')
        actif = (request.GET.get('actif') or '').strip().lower()
        if actif in ('0', 'false', 'non'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'oui'):
            qs = qs.filter(actif=True)

        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'id': r.id,
                'entreprise_id': r.entreprise_id,
                'nom': r.nom,
                'actif': r.actif,
                'created_by_user_id': r.created_by_user_id,
                'date_creation': r.date_creation.isoformat(),
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class CaisseCreateApiView(CaisseAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        nom = (payload.get('nom') or '').strip()[:120]
        if not nom:
            return JsonResponse({'ok': False, 'error': 'nom requis.'}, status=400)
        actif = payload.get('actif')
        actif = bool(actif) if actif is not None else True
        obj = CaisseCompte.objects.create(
            entreprise_id=eid,
            nom=nom,
            actif=actif,
            created_by_user_id=str(request.user.pk),
        )
        return JsonResponse({'ok': True, 'id': obj.id}, status=201)


class CaisseUpdateApiView(CaisseAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, caisse_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        obj = CaisseCompte.objects.filter(entreprise_id=eid, id=caisse_id).first()
        if not obj:
            return JsonResponse({'ok': False, 'error': 'Caisse introuvable.'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        nom = payload.get('nom')
        if nom is not None:
            nom = str(nom).strip()[:120]
            if not nom:
                return JsonResponse({'ok': False, 'error': 'nom invalide.'}, status=400)
            obj.nom = nom
        actif = payload.get('actif')
        if actif is not None:
            obj.actif = bool(actif)
        obj.save()
        return JsonResponse({'ok': True}, status=200)


class CaisseDeleteApiView(CaisseAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, caisse_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        obj = CaisseCompte.objects.filter(entreprise_id=eid, id=caisse_id).first()
        if not obj:
            return JsonResponse({'ok': False, 'error': 'Caisse introuvable.'}, status=404)
        # suppression logique
        obj.actif = False
        obj.save(update_fields=['actif'])
        return JsonResponse({'ok': True}, status=200)


class CaisseSoldeApiView(CaisseAccessMixin, View):
    """Solde total + solde par caisse (paginé)."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse(
                {'results': [], 'count': 0, 'page': 1, 'page_size': 25, 'stats': {'total': '0.00'}},
                status=200,
            )

        # solde par caisse = somme(ENTREE) - somme(SORTIE)
        signed = Case(
            When(type=MouvementCaisse.Type.ENTREE, then=F('montant')),
            When(type=MouvementCaisse.Type.SORTIE, then=F('montant') * Value(Decimal('-1'))),
            default=Value(Decimal('0')),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        base = (
            MouvementCaisse.objects.filter(entreprise_id=eid)
            .values('caisse_id')
            .annotate(solde=Sum(signed))
            .order_by('-caisse_id')
        )

        caisse_id = (request.GET.get('caisse_id') or '').strip()
        if caisse_id.isdigit():
            base = base.filter(caisse_id=int(caisse_id))

        count = base.count()
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

        offset = (page - 1) * page_size
        rows = list(base[offset : offset + page_size])
        caisse_ids = [r['caisse_id'] for r in rows]
        names = {x.id: x.nom for x in CaisseCompte.objects.filter(entreprise_id=eid, id__in=caisse_ids)}

        results = [
            {
                'caisse_id': r['caisse_id'],
                'nom': names.get(r['caisse_id'], ''),
                'solde': str(r['solde'] or Decimal('0')),
            }
            for r in rows
        ]
        total = base.aggregate(total=Sum('solde')).get('total') or Decimal('0')
        return JsonResponse(
            {'results': results, 'count': count, 'page': page, 'page_size': page_size, 'stats': {'total': str(total)}},
            status=200,
        )


class CaisseStatsApiView(CaisseAccessMixin, View):
    """Stats globales caisse (total + répartition) pour graphiques."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse(
                {'results': [], 'count': 0, 'page': 1, 'page_size': 25, 'stats': {'total': '0.00'}},
                status=200,
            )

        signed = Case(
            When(type=MouvementCaisse.Type.ENTREE, then=F('montant')),
            When(type=MouvementCaisse.Type.SORTIE, then=F('montant') * Value(Decimal('-1'))),
            default=Value(Decimal('0')),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        base = (
            MouvementCaisse.objects.filter(entreprise_id=eid)
            .values('caisse_id')
            .annotate(solde=Sum(signed))
            .order_by('-solde', '-caisse_id')
        )
        rows = list(base[:50])
        caisse_ids = [r['caisse_id'] for r in rows]
        names = {x.id: x.nom for x in CaisseCompte.objects.filter(entreprise_id=eid, id__in=caisse_ids)}
        results = [
            {'caisse_id': r['caisse_id'], 'nom': names.get(r['caisse_id'], ''), 'solde': str(r['solde'] or Decimal('0'))}
            for r in rows
        ]
        total = base.aggregate(total=Sum('solde')).get('total') or Decimal('0')
        return JsonResponse(
            {'results': results, 'count': len(results), 'page': 1, 'page_size': 25, 'stats': {'total': str(total)}},
            status=200,
        )

