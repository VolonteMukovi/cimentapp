from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Case, DecimalField, F, Value, When
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from caisse.models import MouvementCaisse
from lots.models import DepenseLot, LotStock
from lots.models import LotTransit, LotTransitArticle, LotTransitArticleFinancement, LotTransitFrais
from lots.services import sync_lot_transit_closure
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


def _d(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


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
        ctx['store_module_title'] = 'Lots & Transit'
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


class LotTransitCreateApiView(LotsAccessMixin, View):
    """Crée un lot transit complet (articles + frais + financements caisses)."""

    http_method_names = ['post']

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        reference = str(payload.get('reference') or '').strip()[:64]
        fournisseur = str(payload.get('fournisseur') or '').strip()[:150]
        if not reference or not fournisseur:
            return JsonResponse({'ok': False, 'error': 'reference et fournisseur sont requis.'}, status=400)
        date_expedition = _parse_dt(str(payload.get('date_expedition') or ''))
        date_arrivee = _parse_dt(str(payload.get('date_arrivee_prevue') or ''))
        if not date_expedition or not date_arrivee:
            return JsonResponse({'ok': False, 'error': 'Dates d’expédition et d’arrivée prévues requises.'}, status=400)

        articles = payload.get('articles') or []
        frais = payload.get('frais') or []
        if not isinstance(articles, list) or not articles:
            return JsonResponse({'ok': False, 'error': 'Au moins un article est requis.'}, status=400)

        # Solde disponible par sous-compte caisse
        signed = Case(
            When(type=MouvementCaisse.Type.ENTREE, then=F('montant')),
            When(type=MouvementCaisse.Type.SORTIE, then=F('montant') * Value(Decimal('-1'))),
            default=Value(Decimal('0')),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        current_balances = {
            int(r['caisse_id']): (_d(r['solde']))
            for r in MouvementCaisse.objects.filter(entreprise_id=eid)
            .values('caisse_id')
            .annotate(solde=Sum(signed))
        }
        planned_debits: dict[int, Decimal] = {}
        normalized_articles = []
        total_articles = Decimal('0')

        for row in articles:
            if not isinstance(row, dict):
                continue
            article_id = str(row.get('article_id') or '').strip()
            qte = _d(row.get('quantite'))
            pu = _d(row.get('prix_unitaire_achat'))
            if not article_id or qte <= 0 or pu < 0:
                continue
            montant = (qte * pu).quantize(Decimal('0.01'))
            financements = row.get('financements') or []
            if not isinstance(financements, list) or not financements:
                return JsonResponse({'ok': False, 'error': f'Financement requis pour article {article_id}.'}, status=400)
            total_fin = Decimal('0')
            fin_rows = []
            for f in financements:
                caisse_id = f.get('caisse_id')
                mnt = _d(f.get('montant')).quantize(Decimal('0.01'))
                if not str(caisse_id).isdigit() or mnt <= 0:
                    return JsonResponse({'ok': False, 'error': f'Financement invalide pour article {article_id}.'}, status=400)
                caisse_id = int(caisse_id)
                total_fin += mnt
                fin_rows.append({'caisse_id': caisse_id, 'montant': mnt})
                planned_debits[caisse_id] = planned_debits.get(caisse_id, Decimal('0')) + mnt
            if total_fin != montant:
                return JsonResponse(
                    {
                        'ok': False,
                        'error': f'Incohérence de financement article {article_id}: attendu {montant}, obtenu {total_fin}.',
                    },
                    status=400,
                )
            normalized_articles.append({'article_id': article_id, 'quantite': qte, 'pu': pu, 'montant': montant, 'financements': fin_rows})
            total_articles += montant

        normalized_frais = []
        total_frais = Decimal('0')
        for fr in frais:
            if not isinstance(fr, dict):
                continue
            libelle = str(fr.get('libelle') or '').strip()[:255]
            montant = _d(fr.get('montant')).quantize(Decimal('0.01'))
            caisse_id = fr.get('caisse_id')
            if not libelle:
                continue
            if montant < 0 or not str(caisse_id).isdigit():
                return JsonResponse({'ok': False, 'error': f'Frais invalide: {libelle}.'}, status=400)
            caisse_id = int(caisse_id)
            normalized_frais.append({'libelle': libelle, 'montant': montant, 'caisse_id': caisse_id})
            total_frais += montant
            planned_debits[caisse_id] = planned_debits.get(caisse_id, Decimal('0')) + montant

        # Vérification de fonds disponibles (avec agrégat des débits planifiés)
        insufficient = []
        for caisse_id, need in planned_debits.items():
            available = current_balances.get(caisse_id, Decimal('0'))
            if available < need:
                insufficient.append({'caisse_id': caisse_id, 'disponible': str(available), 'requis': str(need)})
        if insufficient:
            return JsonResponse(
                {'ok': False, 'error': 'Fonds insuffisants sur un ou plusieurs sous-comptes.', 'details': insufficient},
                status=400,
            )

        lot = LotTransit.objects.create(
            entreprise_id=eid,
            reference=reference,
            fournisseur=fournisseur,
            date_expedition=date_expedition.date(),
            date_arrivee_prevue=date_arrivee.date(),
            statut=LotTransit.Statut.EN_TRANSIT,
        )

        created_articles = []
        total_qte = Decimal('0')
        for ar in normalized_articles:
            stock = LotStock.objects.create(
                entreprise_id=eid,
                article_id=ar['article_id'],
                lot_transit_id=lot.id,
                reference=reference,
                quantite_entree=ar['quantite'],
                quantite_restante=ar['quantite'],
                cout_unitaire_achat=ar['pu'],
                date_entree=timezone.now(),
            )
            line = LotTransitArticle.objects.create(
                lot_transit=lot,
                article_id=ar['article_id'],
                quantite=ar['quantite'],
                prix_unitaire_achat=ar['pu'],
                cout_total=ar['montant'],
                lot_stock_id=stock.id,
            )
            for fin in ar['financements']:
                LotTransitArticleFinancement.objects.create(
                    lot_article=line, caisse_id=fin['caisse_id'], montant=fin['montant']
                )
                MouvementCaisse.objects.create(
                    entreprise_id=eid,
                    caisse_id=fin['caisse_id'],
                    type=MouvementCaisse.Type.SORTIE,
                    montant=fin['montant'],
                    date_mouvement=timezone.now(),
                    libelle=f'Approvisionnement lot {reference} - article {ar["article_id"]}',
                    source_type='lot_article',
                    source_id=str(line.id),
                    created_by_user_id=str(request.user.pk),
                )
            created_articles.append(line)
            total_qte += ar['quantite']

        for fr in normalized_frais:
            fee = LotTransitFrais.objects.create(
                lot_transit=lot, libelle=fr['libelle'], montant=fr['montant'], caisse_id=fr['caisse_id']
            )
            MouvementCaisse.objects.create(
                entreprise_id=eid,
                caisse_id=fr['caisse_id'],
                type=MouvementCaisse.Type.SORTIE,
                montant=fr['montant'],
                date_mouvement=timezone.now(),
                libelle=f'Frais lot {reference} - {fee.libelle}',
                source_type='lot_frais',
                source_id=str(fee.id),
                created_by_user_id=str(request.user.pk),
            )

        # Alimente DepenseLot par lot FIFO (LotStock) pour conserver la logique coûts existante.
        for line in created_articles:
            if total_articles > 0:
                ratio = (line.cout_total / total_articles)
            else:
                ratio = Decimal('0')
            allocated = (total_frais * ratio).quantize(Decimal('0.01'))
            if allocated > 0 and line.lot_stock_id:
                DepenseLot.objects.create(
                    entreprise_id=eid,
                    lot_id=line.lot_stock_id,
                    libelle=f'Frais répartis lot {reference}',
                    montant=allocated,
                    date_depense=timezone.now(),
                )

        # PU réel proposé = PU achat + prorata frais / quantité totale du lot
        frais_per_unit = (total_frais / total_qte).quantize(Decimal('0.01')) if total_qte > 0 else Decimal('0')
        for line in created_articles:
            line.pu_reel_propose = (line.prix_unitaire_achat + frais_per_unit).quantize(Decimal('0.01'))
            line.save(update_fields=['pu_reel_propose'])

        cout_total_lot = (total_articles + total_frais).quantize(Decimal('0.01'))
        return JsonResponse(
            {
                'ok': True,
                'lot_id': lot.id,
                'reference': lot.reference,
                'cout_articles': str(total_articles),
                'cout_frais': str(total_frais),
                'cout_total_lot': str(cout_total_lot),
                'frais_unitaire_reparti': str(frais_per_unit),
            },
            status=201,
        )


class LotTransitApiListView(LotsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'results': [], 'count': 0, 'page': 1, 'page_size': 25}, status=200)
        qs = LotTransit.objects.filter(entreprise_id=eid).order_by('-date_creation', '-id')
        statut = (request.GET.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        rows, count, page, page_size = _paginate(qs, request)
        results = []
        for lot in rows:
            total_articles = (
                LotTransitArticle.objects.filter(lot_transit_id=lot.id).aggregate(s=Sum('cout_total')).get('s') or Decimal('0')
            )
            total_frais = LotTransitFrais.objects.filter(lot_transit_id=lot.id).aggregate(s=Sum('montant')).get('s') or Decimal('0')
            results.append(
                {
                    'id': lot.id,
                    'reference': lot.reference,
                    'fournisseur': lot.fournisseur,
                    'date_expedition': lot.date_expedition.isoformat(),
                    'date_arrivee_prevue': lot.date_arrivee_prevue.isoformat(),
                    'statut': lot.statut,
                    'cout_total_lot': str(total_articles + total_frais),
                }
            )
        return JsonResponse({'results': results, 'count': count, 'page': page, 'page_size': page_size}, status=200)


class LotTransitStatusUpdateApiView(LotsAccessMixin, View):
    http_method_names = ['post']

    def post(self, request, lot_id: int, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': False, 'error': 'Entreprise active requise.'}, status=400)
        lot = LotTransit.objects.filter(entreprise_id=eid, id=lot_id).first()
        if not lot:
            return JsonResponse({'ok': False, 'error': 'Lot introuvable.'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        statut = str(payload.get('statut') or '').strip()
        if statut not in (LotTransit.Statut.EN_TRANSIT, LotTransit.Statut.ARRIVE):
            return JsonResponse({'ok': False, 'error': 'Statut autorisé: en_transit ou arrive.'}, status=400)
        lot.statut = statut
        lot.save(update_fields=['statut'])
        sync_lot_transit_closure(lot.id)
        return JsonResponse({'ok': True}, status=200)


class LotTransitStatsApiView(LotsAccessMixin, View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            return JsonResponse({'ok': True, 'stats': {'total': 0, 'en_transit': 0, 'arrive': 0, 'cloture': 0}}, status=200)
        base = LotTransit.objects.filter(entreprise_id=eid)
        stats = {
            'total': base.count(),
            'en_transit': base.filter(statut=LotTransit.Statut.EN_TRANSIT).count(),
            'arrive': base.filter(statut=LotTransit.Statut.ARRIVE).count(),
            'cloture': base.filter(statut=LotTransit.Statut.CLOTURE).count(),
        }
        return JsonResponse({'ok': True, 'stats': stats}, status=200)

