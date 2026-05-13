from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from articles.currency import get_primary_currency_code, resolve_transaction_currency, to_primary_amount
from caisse.models import CaisseCompte, MouvementCaisse
from commandes.models import ClientDettePaiement, ClientSoldeMouvement
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import AffectationEntreprise, Client, User
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
        eid = self.entreprise_id()
        ctx['store_module_key'] = 'clients'
        ctx['store_module_title'] = 'Clients & garanties'
        ctx['devise_principale_code'] = get_primary_currency_code(eid)
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
    credits = sum(
        (
            to_primary_amount(eid, row.montant, row.devise)
            for row in ClientSoldeMouvement.objects.filter(
                entreprise_id=eid,
                client_id=client_id,
                type='credit',
            ).only('montant', 'devise')
        ),
        Decimal('0'),
    )
    debits = sum(
        (
            to_primary_amount(eid, row.montant, row.devise)
            for row in ClientSoldeMouvement.objects.filter(
                entreprise_id=eid,
                client_id=client_id,
                type='debit',
            ).only('montant', 'devise')
        ),
        Decimal('0'),
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
                    'devise_principale': get_primary_currency_code(eid),
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
                'montant_principal': str(to_primary_amount(eid, r.montant, r.devise)),
                'devise_principale': get_primary_currency_code(eid),
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
                'total_principal': str(to_primary_amount(eid, r.total, r.devise)),
                'devise_principale': get_primary_currency_code(eid),
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

        by_day = {}
        for r in ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=client_id).only(
            'date_mouvement',
            'type',
            'montant',
            'devise',
        ):
            day = r.date_mouvement.date().isoformat() if r.date_mouvement else None
            if not day:
                continue
            by_day.setdefault(day, {'credit': Decimal('0'), 'debit': Decimal('0')})
            by_day[day][r.type] = by_day[day].get(r.type, Decimal('0')) + to_primary_amount(eid, r.montant, r.devise)
        out = [
            {'day': d, 'credit': str(v.get('credit') or Decimal('0')), 'debit': str(v.get('debit') or Decimal('0'))}
            for d, v in sorted(by_day.items(), key=lambda x: x[0])
        ]
        return JsonResponse(
            {'results': out, 'count': len(out), 'page': 1, 'page_size': 25, 'devise_principale': get_primary_currency_code(eid)},
            status=200,
        )


class ClientCrediterApiView(ClientsAccessMixin, View):
    """Créditer garantie (dépôt/versement) + entrée caisse."""

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        if not AffectationEntreprise.objects.filter(entreprise_id=eid, source=client_id).exists():
            return JsonResponse({'ok': False, 'error': 'Client non rattache a cette entreprise.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        caisse_id = payload.get('caisse_id')
        if not str(caisse_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'caisse_id requis.'}, status=400)
        caisse_id = int(caisse_id)
        if not CaisseCompte.objects.filter(entreprise_id=eid, id=caisse_id, actif=True).exists():
            return JsonResponse({'ok': False, 'error': 'Sous-compte caisse introuvable ou inactif.'}, status=400)

        montant = _d(payload.get('montant'))
        if montant <= 0:
            return JsonResponse({'ok': False, 'error': 'montant invalide.'}, status=400)
        try:
            devise = resolve_transaction_currency(eid, payload.get('devise'))
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        libelle = str(payload.get('libelle') or 'Dépôt client').strip()[:255]
        dt = timezone.now()

        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=montant,
            devise=devise,
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
            devise=devise,
            date_mouvement=dt,
            source_type='depot',
            source_id='',
        )
        return JsonResponse({'ok': True}, status=201)


class ClientDettePaiementsApiView(ClientsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, client_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)
        if not AffectationEntreprise.objects.filter(entreprise_id=eid, source=client_id).exists():
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = ClientDettePaiement.objects.filter(entreprise_id=eid, client_id=client_id).order_by('-date_soumission', '-id')
        statut = (request.GET.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        rows, count, page, page_size = _paginate(qs, request, default_page_size=10)
        caisse_ids = [row.caisse_id for row in rows]
        caisses = {c.id: c.nom for c in CaisseCompte.objects.filter(entreprise_id=eid, id__in=caisse_ids)}
        results = [
            {
                'id': row.id,
                'client_id': row.client_id,
                'caisse_id': row.caisse_id,
                'caisse_nom': caisses.get(row.caisse_id, ''),
                'montant': str(row.montant),
                'devise': row.devise,
                'montant_principal': str(to_primary_amount(eid, row.montant, row.devise)),
                'devise_principale': get_primary_currency_code(eid),
                'statut': row.statut,
                'note_client': row.note_client,
                'preuve_paiement_url': row.preuve_paiement.url if row.preuve_paiement else '',
                'date_soumission': row.date_soumission.isoformat(),
            }
            for row in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class ClientDettePaiementConfirmerApiView(ClientsAccessMixin, View):
    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, client_id: str, paiement_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        if not AffectationEntreprise.objects.filter(entreprise_id=eid, source=client_id).exists():
            return JsonResponse({'ok': False, 'error': 'Client non rattache a cette entreprise.'}, status=400)
        paiement = ClientDettePaiement.objects.select_for_update().filter(
            entreprise_id=eid,
            client_id=client_id,
            pk=paiement_id,
        ).first()
        if not paiement:
            return JsonResponse({'ok': False, 'error': 'Paiement introuvable.'}, status=404)
        if paiement.statut != ClientDettePaiement.Statut.EN_ATTENTE:
            return JsonResponse({'ok': False, 'error': 'Ce paiement a deja ete traite.'}, status=400)
        if not CaisseCompte.objects.filter(entreprise_id=eid, id=paiement.caisse_id, actif=True).exists():
            return JsonResponse({'ok': False, 'error': 'Sous-compte caisse introuvable ou inactif.'}, status=400)

        dt = timezone.now()
        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=paiement.caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=paiement.montant,
            devise=paiement.devise,
            date_mouvement=dt,
            libelle=f'Paiement dette client {client_id}',
            source_type='dette_client',
            source_id=str(paiement.pk),
            created_by_user_id=str(request.user.pk),
        )
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=client_id,
            type=ClientSoldeMouvement.Type.CREDIT,
            montant=paiement.montant,
            devise=paiement.devise,
            date_mouvement=dt,
            source_type='paiement_dette',
            source_id=str(paiement.pk),
        )
        paiement.statut = ClientDettePaiement.Statut.CONFIRME
        paiement.date_confirmation = dt
        paiement.confirmed_by_user_id = str(request.user.pk)
        paiement.save(update_fields=['statut', 'date_confirmation', 'confirmed_by_user_id'])
        return JsonResponse({'ok': True}, status=200)

