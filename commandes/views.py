from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
import json
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from caisse.models import MouvementCaisse
from commandes.models import ClientSoldeMouvement, Commande, CommandeLigne
from lots.models import DepenseLot, LotStock
from lots.services import sync_lot_transit_closure
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


class CommandesAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'commandes'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class StoreCommandesView(CommandesAccessMixin, TemplateView):
    template_name = 'commandes/store_commandes_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = 'commandes'
        ctx['store_module_title'] = 'Commandes clients'
        return ctx


class CommandesApiListView(CommandesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = Commande.objects.filter(entreprise_id=eid).order_by('-date_commande', '-commande_id')
        statut = (request.GET.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)

        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'commande_id': r.commande_id,
                'client_id': r.client_id,
                'statut': r.statut,
                'total': str(r.total),
                'devise': r.devise,
                'caisse_id': r.caisse_id,
                'paiement_statut': r.paiement_statut,
                'depot_montant': str(r.depot_montant),
                'date_commande': r.date_commande.isoformat(),
            }
            for r in rows
        ]
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


def _d(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


class CommandeConfirmerDepotApiView(CommandesAccessMixin, View):
    """Confirme un dépôt client: mouvement caisse + crédit solde client."""

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, commande_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        cmd = Commande.objects.select_for_update().filter(entreprise_id=eid, commande_id=commande_id).first()
        if not cmd:
            return JsonResponse({'ok': False, 'error': 'Commande introuvable.'}, status=404)
        if not cmd.client_id:
            return JsonResponse({'ok': False, 'error': 'Commande sans client.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        caisse_id = payload.get('caisse_id') or cmd.caisse_id
        if not str(caisse_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'caisse_id requis.'}, status=400)
        caisse_id = int(caisse_id)

        montant = _d(payload.get('montant') or cmd.total)
        if montant <= 0:
            return JsonResponse({'ok': False, 'error': 'montant invalide.'}, status=400)

        dt = timezone.now()

        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=montant,
            date_mouvement=dt,
            libelle=f'Dépôt commande {cmd.commande_id}',
            source_type='commande',
            source_id=cmd.commande_id,
            created_by_user_id=str(request.user.pk),
        )
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=str(cmd.client_id),
            type=ClientSoldeMouvement.Type.CREDIT,
            montant=montant,
            devise=cmd.devise,
            date_mouvement=dt,
            source_type='commande',
            source_id=cmd.commande_id,
        )
        cmd.caisse_id = caisse_id
        cmd.depot_montant = montant
        cmd.paiement_statut = Commande.PaiementStatut.CONFIRME
        cmd.save(update_fields=['caisse_id', 'depot_montant', 'paiement_statut'])
        return JsonResponse({'ok': True}, status=200)


class CommandeCreerVenteApiView(CommandesAccessMixin, View):
    """Crée une vente depuis une commande + FIFO + débit solde client (comptant/crédit)."""

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, commande_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        cmd = Commande.objects.select_for_update().filter(entreprise_id=eid, commande_id=commande_id).first()
        if not cmd:
            return JsonResponse({'ok': False, 'error': 'Commande introuvable.'}, status=404)
        if not cmd.client_id:
            return JsonResponse({'ok': False, 'error': 'Commande sans client.'}, status=400)

        # solde actuel
        credits = (
            ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=str(cmd.client_id), type='credit')
            .aggregate(s=Sum('montant'))
            .get('s')
            or Decimal('0')
        )
        debits = (
            ClientSoldeMouvement.objects.filter(entreprise_id=eid, client_id=str(cmd.client_id), type='debit')
            .aggregate(s=Sum('montant'))
            .get('s')
            or Decimal('0')
        )
        solde = credits - debits
        type_vente = 'comptant' if solde >= (cmd.total or Decimal('0')) else 'credit'

        vente = Vente(
            vente_id=Vente.generate_id(),
            entreprise_id=eid,
            client_id=str(cmd.client_id),
            client_nom='',
            commande_id=cmd.commande_id,
            type_vente=type_vente,
            total=cmd.total,
            devise=cmd.devise,
            caisse_id=cmd.caisse_id if type_vente == 'comptant' else None,
            date_vente=timezone.now(),
            created_by_user_id=str(request.user.pk),
        )
        vente.save()

        lignes_cmd = list(CommandeLigne.objects.filter(commande_id=cmd.commande_id).order_by('id'))
        if not lignes_cmd:
            return JsonResponse({'ok': False, 'error': 'Commande sans lignes.'}, status=400)

        VenteLigne.objects.bulk_create(
            [
                VenteLigne(
                    vente_id=vente.vente_id,
                    article_id=l.article_id,
                    quantite=l.quantite,
                    prix_unitaire_vente=l.prix_unitaire,
                    total_ligne=l.total_ligne,
                )
                for l in lignes_cmd
            ]
        )

        created_lines = list(VenteLigne.objects.filter(vente_id=vente.vente_id).order_by('id'))
        by_article = {}
        for l in created_lines:
            by_article.setdefault(l.article_id, []).append(l)

        cons_rows = []
        for article_id, lines_for_article in by_article.items():
            needed = sum((l.quantite for l in lines_for_article), Decimal('0'))
            lots = (
                LotStock.objects.select_for_update()
                .filter(entreprise_id=eid, article_id=article_id, quantite_restante__gt=0)
                .order_by('date_entree', 'id')
            )
            lots = list(lots)
            if not lots:
                return JsonResponse({'ok': False, 'error': f'Stock insuffisant pour {article_id}.'}, status=400)

            lot_ids = [x.id for x in lots]
            exp = DepenseLot.objects.filter(entreprise_id=eid, lot_id__in=lot_ids).values('lot_id').annotate(total=Sum('montant'))
            exp_map = {e['lot_id']: _d(e['total']) for e in exp}

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
                lot.quantite_restante = lot.quantite_restante - take
                lot.save(update_fields=['quantite_restante'])
                sync_lot_transit_closure(lot.lot_transit_id)

                exp_total = exp_map.get(lot.id, Decimal('0'))
                exp_unit = (exp_total / lot.quantite_entree) if lot.quantite_entree else Decimal('0')
                exp_unit = exp_unit.quantize(Decimal('0.01'))

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
                            cout_unitaire_achat=lot.cout_unitaire_achat,
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
                return JsonResponse({'ok': False, 'error': f'Stock insuffisant pour {article_id}.'}, status=400)

        VenteFifoConsommation.objects.bulk_create(cons_rows)

        # débit client (vente)
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=str(cmd.client_id),
            type=ClientSoldeMouvement.Type.DEBIT,
            montant=cmd.total,
            devise=cmd.devise,
            date_mouvement=timezone.now(),
            source_type='vente',
            source_id=vente.vente_id,
        )

        cmd.statut = Commande.Statut.VALIDEE
        cmd.save(update_fields=['statut'])
        return JsonResponse({'ok': True, 'vente_id': vente.vente_id, 'type_vente': type_vente}, status=201)

