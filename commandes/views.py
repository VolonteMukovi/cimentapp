from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
import json
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView, View

from articles.currency import get_primary_currency_code, to_primary_amount
from articles.models import Article, Unite
from caisse.models import CaisseCompte, MouvementCaisse
from commandes.models import ClientDettePaiement, ClientSoldeMouvement, Commande, CommandeLigne
from lots.models import DepenseLot, LotStock
from lots.services import sync_lot_transit_closure
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import Client, Entreprise, User
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


def _payment_proof_context(eid: int, *, payment, proof_type: str) -> dict:
    client = Client.objects.filter(pk=payment.client_id).first()
    entreprise = Entreprise.objects.filter(pk=eid).first()
    caisse_id = getattr(payment, 'caisse_id', None)
    caisse = CaisseCompte.objects.filter(entreprise_id=eid, pk=caisse_id).first() if caisse_id else None
    vente = None
    produits = []
    if proof_type == 'commande':
        vente = Vente.objects.filter(entreprise_id=eid, commande_id=payment.commande_id).first()
        if vente:
            vente_lignes = list(VenteLigne.objects.filter(vente_id=vente.vente_id).order_by('id'))
            article_ids = [line.article_id for line in vente_lignes]
            articles = {
                article.article_id: article
                for article in Article.objects.filter(entreprise_id=eid, article_id__in=article_ids).only(
                    'article_id',
                    'nom',
                    'unite_id',
                )
            }
            unite_ids = [article.unite_id for article in articles.values()]
            unites = {unite.id: unite for unite in Unite.objects.filter(id__in=unite_ids).only('id', 'libelle', 'code')}
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
        reference = payment.commande_id
        montant = payment.depot_montant
        devise = payment.devise
        statut = payment.get_paiement_statut_display()
        date_operation = payment.date_commande
        note = payment.note_client
    else:
        reference = f'DETTE-{payment.pk}'
        montant = payment.montant
        devise = payment.devise
        statut = payment.get_statut_display()
        date_operation = payment.date_soumission
        note = payment.note_client
    return {
        'entreprise': entreprise,
        'client': client,
        'caisse': caisse,
        'payment': payment,
        'vente': vente,
        'produits': produits,
        'proof_type': proof_type,
        'reference': reference,
        'montant': montant,
        'devise': devise,
        'statut': statut,
        'date_operation': date_operation,
        'note': note,
        'preuve_url': payment.preuve_paiement.url if payment.preuve_paiement else '',
    }


class CommandePreuveImprimerView(CommandesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, commande_id: str, *args, **kwargs):
        eid = self.entreprise_id()
        commande = Commande.objects.filter(entreprise_id=eid, commande_id=commande_id).first()
        if not commande:
            raise Http404('Commande introuvable.')
        if not Vente.objects.filter(entreprise_id=eid, commande_id=commande.commande_id).exists():
            raise Http404('La preuve sera disponible apres creation de la vente.')
        return render(
            request,
            'commandes/payment_proof_print.html',
            _payment_proof_context(eid, payment=commande, proof_type='commande'),
        )


class DettePreuveImprimerView(CommandesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, paiement_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        paiement = ClientDettePaiement.objects.filter(entreprise_id=eid, pk=paiement_id).first()
        if not paiement:
            raise Http404('Paiement introuvable.')
        return render(
            request,
            'commandes/payment_proof_print.html',
            _payment_proof_context(eid, payment=paiement, proof_type='dette'),
        )


class CommandesApiListView(CommandesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)

        qs = Commande.objects.filter(entreprise_id=eid).order_by('-date_commande', '-commande_id')
        q = (request.GET.get('q') or '').strip()
        if q:
            matching_clients = Client.objects.filter(
                Q(id__icontains=q) | Q(nom__icontains=q) | Q(email__icontains=q)
            ).values_list('id', flat=True)
            qs = qs.filter(Q(commande_id__icontains=q) | Q(client_id__in=matching_clients))
        statut = (request.GET.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)

        rows, count, page, page_size = _paginate(qs, request)
        commande_ids = [r.commande_id for r in rows]
        sold_command_ids = set(
            Vente.objects.filter(entreprise_id=eid, commande_id__in=commande_ids).values_list('commande_id', flat=True)
        )
        client_ids = [r.client_id for r in rows if r.client_id]
        clients_by_id = {
            c.id: c
            for c in Client.objects.filter(id__in=client_ids).only('id', 'nom', 'email')
        }
        lignes_by_cmd: dict[str, list[dict]] = {}
        for line in CommandeLigne.objects.filter(commande_id__in=commande_ids).order_by('id'):
            lignes_by_cmd.setdefault(line.commande_id, []).append(
                {
                    'id': line.id,
                    'article_id': line.article_id,
                    'quantite': str(line.quantite),
                    'prix_unitaire': str(line.prix_unitaire),
                    'total_ligne': str(line.total_ligne),
                }
            )

        results = []
        for r in rows:
            solde = _client_solde_principal(eid, r.client_id) if r.client_id else Decimal('0')
            client = clients_by_id.get(r.client_id)
            client_email = (client.email or '') if client else ''
            client_initial = (client_email.strip()[:1] or (client.nom.strip()[:1] if client and client.nom else '?')).upper()
            results.append(
                {
                    'commande_id': r.commande_id,
                    'client_id': r.client_id,
                    'client_nom': client.nom if client else '',
                    'client_email': client_email,
                    'client_email_initial': client_initial,
                    'statut': r.statut,
                    'total': str(r.total),
                    'devise': r.devise,
                    'total_principal': str(to_primary_amount(eid, r.total, r.devise)),
                    'devise_principale': get_primary_currency_code(eid),
                    'solde_client_principal': str(solde),
                    'caisse_id': r.caisse_id,
                    'paiement_statut': r.paiement_statut,
                    'depot_montant': str(r.depot_montant),
                    'preuve_paiement_url': r.preuve_paiement.url if r.preuve_paiement else '',
                    'vente_creee': r.commande_id in sold_command_ids,
                    'date_commande': r.date_commande.isoformat(),
                    'lignes': lignes_by_cmd.get(r.commande_id, []),
                }
            )
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


def _d(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


def _client_solde_principal(eid: int, client_id: str) -> Decimal:
    credits = sum(
        (
            to_primary_amount(eid, mv.montant, mv.devise)
            for mv in ClientSoldeMouvement.objects.filter(
                entreprise_id=eid,
                client_id=str(client_id),
                type=ClientSoldeMouvement.Type.CREDIT,
            ).only('montant', 'devise')
        ),
        Decimal('0'),
    )
    debits = sum(
        (
            to_primary_amount(eid, mv.montant, mv.devise)
            for mv in ClientSoldeMouvement.objects.filter(
                entreprise_id=eid,
                client_id=str(client_id),
                type=ClientSoldeMouvement.Type.DEBIT,
            ).only('montant', 'devise')
        ),
        Decimal('0'),
    )
    return credits - debits


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
        if Vente.objects.filter(entreprise_id=eid, commande_id=cmd.commande_id).exists():
            return JsonResponse({'ok': False, 'error': 'Commande verrouillee: une vente existe deja.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        caisse_id = payload.get('caisse_id') or cmd.caisse_id
        if not str(caisse_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'caisse_id requis.'}, status=400)
        caisse_id = int(caisse_id)

        montant = _d(payload.get('montant') or cmd.depot_montant)
        if montant <= 0:
            return JsonResponse({'ok': False, 'error': 'montant invalide.'}, status=400)
        if cmd.statut == Commande.Statut.LIVREE:
            return JsonResponse({'ok': False, 'error': 'Cette commande est deja livree.'}, status=400)

        dt = timezone.now()

        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=montant,
            devise=cmd.devise,
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
        cmd.statut = Commande.Statut.RESERVEE
        cmd.save(update_fields=['caisse_id', 'depot_montant', 'paiement_statut', 'statut'])
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
        if cmd.statut != Commande.Statut.RESERVEE:
            return JsonResponse({'ok': False, 'error': 'La commande doit etre reservee avant livraison.'}, status=400)
        if Vente.objects.filter(entreprise_id=eid, commande_id=cmd.commande_id).exists():
            return JsonResponse({'ok': False, 'error': 'Une vente existe deja pour cette commande.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        lignes_cmd = list(CommandeLigne.objects.filter(commande_id=cmd.commande_id).order_by('id'))
        if not lignes_cmd:
            return JsonResponse({'ok': False, 'error': 'Commande sans lignes.'}, status=400)

        delivered_by_line_id: dict[int, Decimal] = {}
        unit_price_by_line_id: dict[int, Decimal] = {}
        delivered_payload = payload.get('lignes') or []
        if isinstance(delivered_payload, list):
            for row in delivered_payload:
                if not isinstance(row, dict):
                    continue
                line_id = row.get('id') or row.get('ligne_id')
                qte = _d(row.get('quantite'))
                prix = _d(row.get('prix_unitaire'))
                if str(line_id).isdigit() and qte > 0:
                    delivered_by_line_id[int(line_id)] = qte
                    if prix > 0:
                        unit_price_by_line_id[int(line_id)] = prix

        normalized_lines = []
        total_livre = Decimal('0')
        for line in lignes_cmd:
            qte_livree = delivered_by_line_id.get(line.id, line.quantite)
            prix_unitaire = unit_price_by_line_id.get(line.id)
            if qte_livree <= 0:
                return JsonResponse({'ok': False, 'error': f'Quantite livree invalide pour {line.article_id}.'}, status=400)
            if prix_unitaire is None or prix_unitaire <= 0:
                return JsonResponse({'ok': False, 'error': f'Prix de vente unitaire requis pour {line.article_id}.'}, status=400)
            total_ligne = (qte_livree * prix_unitaire).quantize(Decimal('0.01'))
            total_livre += total_ligne
            normalized_lines.append(
                {
                    'source': line,
                    'quantite': qte_livree,
                    'prix_unitaire': prix_unitaire,
                    'total_ligne': total_ligne,
                }
            )

        # La vente est comptant si la garantie d'achat couvre le total livre, sinon credit.
        solde = _client_solde_principal(eid, str(cmd.client_id))
        total_livre_principal = to_primary_amount(eid, total_livre, cmd.devise)
        type_vente = 'comptant' if solde >= (total_livre_principal or Decimal('0')) else 'credit'

        vente = Vente(
            vente_id=Vente.generate_id(),
            entreprise_id=eid,
            client_id=str(cmd.client_id),
            client_nom='',
            commande_id=cmd.commande_id,
            type_vente=type_vente,
            total=total_livre,
            devise=cmd.devise,
            caisse_id=cmd.caisse_id if type_vente == 'comptant' else None,
            date_vente=timezone.now(),
            created_by_user_id=str(request.user.pk),
        )
        vente.save()

        VenteLigne.objects.bulk_create(
            [
                VenteLigne(
                    vente_id=vente.vente_id,
                    article_id=row['source'].article_id,
                    quantite=row['quantite'],
                    prix_unitaire_vente=row['prix_unitaire'],
                    total_ligne=row['total_ligne'],
                )
                for row in normalized_lines
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
                transaction.set_rollback(True)
                return JsonResponse({'ok': False, 'error': f'Stock insuffisant pour {article_id}.'}, status=400)

            lot_ids = [x.id for x in lots]
            exp_map: dict[int, Decimal] = {}
            for depense in DepenseLot.objects.filter(entreprise_id=eid, lot_id__in=lot_ids).only('lot_id', 'montant', 'devise'):
                exp_map[depense.lot_id] = exp_map.get(depense.lot_id, Decimal('0')) + to_primary_amount(
                    eid,
                    depense.montant,
                    depense.devise,
                )

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
                cout_unitaire_achat = to_primary_amount(eid, lot.cout_unitaire_achat, getattr(lot, 'devise', '') or cmd.devise)

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
                transaction.set_rollback(True)
                return JsonResponse({'ok': False, 'error': f'Stock insuffisant pour {article_id}.'}, status=400)

        VenteFifoConsommation.objects.bulk_create(cons_rows)

        # débit client (vente)
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=str(cmd.client_id),
            type=ClientSoldeMouvement.Type.DEBIT,
            montant=total_livre,
            devise=cmd.devise,
            date_mouvement=timezone.now(),
            source_type='vente',
            source_id=vente.vente_id,
        )

        for row in normalized_lines:
            source = row['source']
            source.quantite = row['quantite']
            source.prix_unitaire = row['prix_unitaire']
            source.total_ligne = row['total_ligne']
            source.save(update_fields=['quantite', 'prix_unitaire', 'total_ligne'])
        cmd.statut = Commande.Statut.LIVREE
        cmd.total = total_livre
        cmd.save(update_fields=['statut', 'total'])
        nouveau_solde = solde - total_livre_principal
        return JsonResponse(
            {
                'ok': True,
                'vente_id': vente.vente_id,
                'type_vente': type_vente,
                'total_livre': str(total_livre),
                'solde_client_avant': str(solde),
                'solde_client_apres': str(nouveau_solde),
                'devise_principale': get_primary_currency_code(eid),
            },
            status=201,
        )


class DettesPaiementsApiListView(CommandesAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)
        qs = ClientDettePaiement.objects.filter(entreprise_id=eid).order_by('-date_soumission', '-id')
        statut = (request.GET.get('statut') or '').strip()
        client_id = (request.GET.get('client_id') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        if client_id:
            qs = qs.filter(client_id=client_id)
        rows, count, page, page_size = _paginate(qs, request)
        results = [
            {
                'id': row.id,
                'client_id': row.client_id,
                'caisse_id': row.caisse_id,
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


class DettePaiementConfirmerApiView(CommandesAccessMixin, View):
    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, paiement_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        paiement = ClientDettePaiement.objects.select_for_update().filter(
            entreprise_id=eid,
            pk=paiement_id,
        ).first()
        if not paiement:
            return JsonResponse({'ok': False, 'error': 'Paiement introuvable.'}, status=404)
        if paiement.statut != ClientDettePaiement.Statut.EN_ATTENTE:
            return JsonResponse({'ok': False, 'error': 'Ce paiement a deja ete traite.'}, status=400)

        dt = timezone.now()
        MouvementCaisse.objects.create(
            entreprise_id=eid,
            caisse_id=paiement.caisse_id,
            type=MouvementCaisse.Type.ENTREE,
            montant=paiement.montant,
            devise=paiement.devise,
            date_mouvement=dt,
            libelle=f'Paiement dette client {paiement.client_id}',
            source_type='dette_client',
            source_id=str(paiement.pk),
            created_by_user_id=str(request.user.pk),
        )
        ClientSoldeMouvement.objects.create(
            entreprise_id=eid,
            client_id=paiement.client_id,
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

