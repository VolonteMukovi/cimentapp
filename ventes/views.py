from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from articles.currency import get_primary_currency_code, resolve_transaction_currency, to_primary_amount
from articles.models import Devise
from caisse.models import MouvementCaisse
from lots.models import DepenseLot, LotStock
from lots.services import sync_lot_transit_closure
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import AffectationEntreprise, Client, User
from users.navigation import can_access_store_module
from ventes.models import Vente, VenteFifoConsommation, VenteLigne


def _d(value) -> Decimal:
    try:
        return Decimal(str(value))
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


class VentesAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'ventes'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class VentesHomeView(VentesAccessMixin, TemplateView):
    template_name = 'ventes/ventes_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'ventes'
        ctx['store_module_title'] = 'Ventes'
        ctx['MEDIA_URL'] = settings.MEDIA_URL
        eid = self.entreprise_id()
        ctx['devise_principale_code'] = get_primary_currency_code(eid)
        ctx['devises'] = Devise.objects.filter(entreprise_id=eid, actif=True).order_by('-principale', 'code') if eid else []
        return ctx


class VentesLookupsApiView(VentesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request: HttpRequest, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': {'clients': [], 'devises': [], 'devise_principale': get_primary_currency_code(None)}})

        client_ids = list(AffectationEntreprise.objects.filter(entreprise_id=eid).values_list('source', flat=True))
        clients = [
            {'client_id': c.id, 'nom': c.nom, 'email': c.email or ''}
            for c in Client.objects.filter(id__in=client_ids).order_by('nom')[:200]
        ]
        devises_qs = Devise.objects.filter(entreprise_id=eid, actif=True).order_by('-principale', 'code')
        devises = [
            {
                'code': d.code,
                'libelle': d.libelle,
                'principale': d.principale,
                'taux_vers_principale': str(d.taux_vers_principale),
            }
            for d in devises_qs
        ]
        if not devises:
            devises = [{'code': get_primary_currency_code(eid), 'libelle': '', 'principale': True, 'taux_vers_principale': '1'}]
        return JsonResponse(
            {
                'results': {
                    'clients': clients,
                    'devises': devises,
                    'devise_principale': get_primary_currency_code(eid),
                },
                'count': len(clients) + len(devises),
                'page': 1,
                'page_size': 25,
            },
            status=200,
        )


class VentesApiListView(VentesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request: HttpRequest, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = Vente.objects.filter(entreprise_id=eid).order_by('-date_vente', '-vente_id')

        dt_from = request.GET.get('date_from')
        dt_to = request.GET.get('date_to')
        if dt_from:
            try:
                qs = qs.filter(date_vente__gte=datetime.fromisoformat(dt_from))
            except Exception:
                pass
        if dt_to:
            try:
                qs = qs.filter(date_vente__lte=datetime.fromisoformat(dt_to))
            except Exception:
                pass

        caisse_id = (request.GET.get('caisse_id') or '').strip()
        if caisse_id.isdigit():
            qs = qs.filter(caisse_id=int(caisse_id))

        rows, count, page, page_size = _paginate(qs, request)
        client_ids = [r.client_id for r in rows if r.client_id]
        client_names = {c.id: c.nom for c in Client.objects.filter(id__in=client_ids)}
        results = [
            {
                'vente_id': r.vente_id,
                'entreprise_id': r.entreprise_id,
                'client_nom': r.client_nom,
                'client_id': r.client_id,
                'client_label': client_names.get(r.client_id) or r.client_nom,
                'total': str(r.total),
                'devise': r.devise,
                'total_principal': str(to_primary_amount(eid, r.total, r.devise)),
                'devise_principale': get_primary_currency_code(eid),
                'caisse_id': r.caisse_id,
                'date_vente': r.date_vente.isoformat(),
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class VenteCreateApiView(VentesAccessMixin, View):
    """
    POST JSON:
    {
      "client_id": "cli_x",
      "caisse_id": 1,
      "devise": "USD",  # optionnel: devise principale si absent
      "date_vente": "2026-04-22T10:00:00",
      "lignes": [{"article_id":"art_x","quantite":"2","prix_unitaire_vente":"10.5"}]
    }
    """

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request: HttpRequest, *args, **kwargs):
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

        try:
            devise = resolve_transaction_currency(eid, payload.get('devise'))
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        client_id = str(payload.get('client_id') or '').strip()[:32]
        if not client_id:
            return JsonResponse({'ok': False, 'error': 'client_id requis.'}, status=400)
        if not AffectationEntreprise.objects.filter(entreprise_id=eid, source=client_id).exists():
            return JsonResponse({'ok': False, 'error': 'Client non rattache a cette entreprise.'}, status=400)
        client = Client.objects.filter(pk=client_id).first()
        if not client:
            return JsonResponse({'ok': False, 'error': 'Client introuvable.'}, status=404)

        dt_raw = payload.get('date_vente')
        if dt_raw:
            try:
                dt = datetime.fromisoformat(dt_raw)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
            except Exception:
                dt = timezone.now()
        else:
            dt = timezone.now()

        lignes = payload.get('lignes') or []
        if not isinstance(lignes, list) or not lignes:
            return JsonResponse({'ok': False, 'error': 'Au moins une ligne est requise.'}, status=400)

        # Pré-validation + totaux
        normalized = []
        total = Decimal('0')
        for ln in lignes:
            if not isinstance(ln, dict):
                continue
            article_id = (ln.get('article_id') or '').strip()
            if not article_id:
                continue
            qte = _d(ln.get('quantite'))
            prix = _d(ln.get('prix_unitaire_vente'))
            if qte <= 0 or prix < 0:
                continue
            total_ligne = (qte * prix).quantize(Decimal('0.01'))
            total += total_ligne
            normalized.append(
                {
                    'article_id': article_id,
                    'quantite': qte,
                    'prix_unitaire_vente': prix,
                    'total_ligne': total_ligne,
                }
            )
        if not normalized:
            return JsonResponse({'ok': False, 'error': 'Lignes invalides.'}, status=400)

        # FIFO: pour chaque article, consommer les lots les plus anciens
        vente = Vente(
            vente_id=Vente.generate_id(),
            entreprise_id=eid,
            client_id=client_id,
            client_nom=client.nom,
            total=total,
            devise=devise,
            caisse_id=caisse_id,
            date_vente=dt,
            created_by_user_id=str(request.user.pk),
        )
        vente.save()

        line_objs = []
        for ln in normalized:
            line_objs.append(
                VenteLigne(
                    vente_id=vente.vente_id,
                    article_id=ln['article_id'],
                    quantite=ln['quantite'],
                    prix_unitaire_vente=ln['prix_unitaire_vente'],
                    total_ligne=ln['total_ligne'],
                )
            )
        VenteLigne.objects.bulk_create(line_objs)

        created_lines = list(VenteLigne.objects.filter(vente_id=vente.vente_id).order_by('id'))
        by_article = {}
        for l in created_lines:
            by_article.setdefault(l.article_id, []).append(l)

        cons_rows = []
        for article_id, lines_for_article in by_article.items():
            needed = sum((l.quantite for l in lines_for_article), Decimal('0'))
            if needed <= 0:
                continue

            # lots anciens: date_entree asc, id asc
            lots = (
                LotStock.objects.select_for_update()
                .filter(entreprise_id=eid, article_id=article_id, quantite_restante__gt=0)
                .order_by('date_entree', 'id')
            )
            lots = list(lots)
            if not lots:
                raise ValueError(f'Stock insuffisant pour {article_id}.')

            # pré-calcul dépenses unitaires par lot (prorata sur qte entrée)
            lot_ids = [x.id for x in lots]
            exp_map: dict[int, Decimal] = {}
            for depense in DepenseLot.objects.filter(entreprise_id=eid, lot_id__in=lot_ids).only('lot_id', 'montant', 'devise'):
                exp_map[depense.lot_id] = exp_map.get(depense.lot_id, Decimal('0')) + to_primary_amount(
                    eid,
                    depense.montant,
                    depense.devise,
                )

            # consommation: on ventile par lignes mais FIFO s'applique globalement à l'article
            line_iter = iter(lines_for_article)
            current_line = next(line_iter, None)
            remaining_line_qty = current_line.quantite if current_line else Decimal('0')
            remaining_total_qty = needed

            for lot in lots:
                if remaining_total_qty <= 0:
                    break
                take = min(lot.quantite_restante, remaining_total_qty)
                if take <= 0:
                    continue

                # mettre à jour stock
                lot.quantite_restante = (lot.quantite_restante - take)
                lot.save(update_fields=['quantite_restante'])
                sync_lot_transit_closure(lot.lot_transit_id)

                exp_total = exp_map.get(lot.id, Decimal('0'))
                exp_unit = (exp_total / lot.quantite_entree) if lot.quantite_entree else Decimal('0')
                exp_unit = exp_unit.quantize(Decimal('0.01'))
                cout_unitaire_achat = to_primary_amount(eid, lot.cout_unitaire_achat, getattr(lot, 'devise', '') or devise)

                # enregistrer la traçabilité pour chaque ligne (dans l'ordre des lignes)
                qty_left_from_lot = take
                while current_line and qty_left_from_lot > 0:
                    slice_qty = min(remaining_line_qty, qty_left_from_lot)
                    cons_rows.append(
                        VenteFifoConsommation(
                            vente_id=vente.vente_id,
                            vente_ligne_id=current_line.id,
                            lot_id=lot.id,
                            article_id=article_id,
                            quantite=slice_qty,
                            cout_unitaire_achat=cout_unitaire_achat,
                            cout_unitaire_depenses=exp_unit,
                        )
                    )
                    qty_left_from_lot -= slice_qty
                    remaining_total_qty -= slice_qty
                    remaining_line_qty -= slice_qty
                    if remaining_line_qty <= 0:
                        current_line = next(line_iter, None)
                        remaining_line_qty = current_line.quantite if current_line else Decimal('0')

            if remaining_total_qty > 0:
                raise ValueError(f'Stock insuffisant pour {article_id}.')

        VenteFifoConsommation.objects.bulk_create(cons_rows)

        # Mouvement de caisse (encaissement direct, pas de crédit/garantie)
        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=total,
            devise=devise,
            date_mouvement=dt,
            libelle=f'Encaissement vente {vente.vente_id}',
            source_type='vente',
            source_id=vente.vente_id,
            created_by_user_id=str(request.user.pk),
        )

        return JsonResponse({'ok': True, 'vente_id': vente.vente_id, 'total': str(total)}, status=201)


class VentesStatsApiView(VentesAccessMixin, View):
    """
    Stats globales ventes pour graphiques.
    GET ?date_from=...&date_to=...
    Retour: results = [{day, ca, ventes}]
    """

    http_method_names = ['get']

    def get(self, request: HttpRequest, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse(
                {'results': [], 'count': 0, 'page': 1, 'page_size': 25, 'stats': {'total_ca': '0.00', 'ventes': 0}},
                status=200,
            )

        qs = Vente.objects.filter(entreprise_id=eid)
        dt_from = request.GET.get('date_from')
        dt_to = request.GET.get('date_to')
        if dt_from:
            try:
                qs = qs.filter(date_vente__gte=datetime.fromisoformat(dt_from))
            except Exception:
                pass
        if dt_to:
            try:
                qs = qs.filter(date_vente__lte=datetime.fromisoformat(dt_to))
            except Exception:
                pass

        by_day: dict = {}
        total_ca = Decimal('0')
        for vente in qs.only('date_vente', 'total', 'devise'):
            day = vente.date_vente.date() if vente.date_vente else None
            if not day:
                continue
            amount = to_primary_amount(eid, vente.total, vente.devise)
            by_day[day] = by_day.get(day, Decimal('0')) + amount
            total_ca += amount
        results = [{'day': d.isoformat(), 'ca': str(v)} for d, v in sorted(by_day.items(), key=lambda item: item[0])]
        ventes_count = qs.count()
        return JsonResponse(
            {
                'results': results,
                'count': len(results),
                'page': 1,
                'page_size': 25,
                'stats': {'total_ca': str(total_ca), 'ventes': ventes_count, 'devise_principale': get_primary_currency_code(eid)},
            },
            status=200,
        )

