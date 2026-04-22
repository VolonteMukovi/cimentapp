from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from caisse.models import MouvementCaisse
from commandes.models import ClientSoldeMouvement
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import Client, User
from users.navigation import can_access_store_module
from ventes.models import Vente


def _d(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


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


class ClientsAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'clients'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class ClientsHomeView(ClientsAccessMixin, TemplateView):
    template_name = 'clients/clients_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'clients'
        ctx['store_module_title'] = 'Clients & garanties'
        return ctx


class ClientsApiListView(ClientsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        # clients liés à l'entreprise
        from users.models import AffectationEntreprise

        client_ids = list(AffectationEntreprise.objects.filter(entreprise_id=eid).values_list('source', flat=True))
        qs = Client.objects.filter(id__in=client_ids).order_by('-date_enregistrement')

        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(email__icontains=q))

        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'client_id': c.id,
                'nom': c.nom,
                'email': c.email,
                'telephone': c.telephone,
                'date_enregistrement': c.date_enregistrement.isoformat(),
            }
            for c in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


def _compute_solde(eid: int, client_id: str) -> tuple[Decimal, Decimal, Decimal]:
    credits = (
        ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=client_id, type='credit')
        .aggregate(s=Sum('montant'))
        .get('s')
        or Decimal('0')
    )
    debits = (
        ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=client_id, type='debit')
        .aggregate(s=Sum('montant'))
        .get('s')
        or Decimal('0')
    )
    solde = credits - debits
    garantie = solde if solde > 0 else Decimal('0')
    dette = (solde * Decimal('-1')) if solde < 0 else Decimal('0')
    return solde, garantie, dette


class ClientResumeApiView(ClientsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        solde, garantie, dette = _compute_solde(eid, client_id)
        ventes_count = Vente.objects.filter(entreprise_id=eid, client_id=client_id).count()
        return JsonResponse(
            {
                'ok': True,
                'client_id': client_id,
                'stats': {
                    'solde': str(solde),
                    'garantie': str(garantie),
                    'dette': str(dette),
                    'ventes': ventes_count,
                },
            },
            status=200,
        )


class ClientMouvementsApiView(ClientsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)
        qs = ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=client_id).order_by(
            '-date_mouvement',
            '-id',
        )
        rows, count, page, page_size = _paginate(qs, request)
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


class ClientVentesApiView(ClientsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)
        qs = Vente.objects.filter(entreprise_id=eid, client_id=client_id).order_by('-date_vente', '-vente_id')
        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'vente_id': r.vente_id,
                'type_vente': r.type_vente,
                'total': str(r.total),
                'devise': r.devise,
                'date_vente': r.date_vente.isoformat(),
                'commande_id': r.commande_id,
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class ClientStatsApiView(ClientsAccessMixin, View):
    """Série temporelle des mouvements (crédit/débit) pour graphiques."""

    http_method_names = ['get']

    def get(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=client_id)
        daily = (
            qs.annotate(day=TruncDate('date_mouvement'))
            .values('day', 'type')
            .annotate(total=Sum('montant'))
            .order_by('day')
        )
        rows = list(daily)
        # regroupe en {day: {credit, debit}}
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


class ClientCrediterApiView(ClientsAccessMixin, View):
    """Créditer garantie (dépôt/versement) + entrée caisse."""

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        caisse_id = payload.get('caisse_id')
        if not str(caisse_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'caisse_id requis.'}, status=400)
        caisse_id = int(caisse_id)

        montant = _d(payload.get('montant'))
        if montant <= 0:
            return JsonResponse({'ok': False, 'error': 'montant invalide.'}, status=400)

        libelle = str(payload.get('libelle') or 'Dépôt client').strip()[:255]
        dt = timezone.now()

        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=montant,
            date_mouvement=dt,
            libelle=f'{libelle} ({client_id})',
            source_type='client',
            source_id=client_id,
            created_by_user_id=str(request.user.pk),
        )
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=client_id,
            type=ClientSoldeMouvement.Type.CREDIT,
            montant=montant,
            devise=str(payload.get('devise') or 'USD')[:10] or 'USD',
            date_mouvement=dt,
            source_type='depot',
            source_id='',
        )
        return JsonResponse({'ok': True}, status=201)

