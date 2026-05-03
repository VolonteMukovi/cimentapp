from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from lots.models import LotStock, LotTransit


def sync_lot_transit_closure(lot_transit_id: int | None) -> None:
    """Passe le lot en statut Clôturé quand tout le stock FIFO est consommé."""
    if not lot_transit_id:
        return
    lot = LotTransit.objects.filter(pk=lot_transit_id).first()
    if not lot or lot.statut == LotTransit.Statut.CLOTURE:
        return
    remaining = (
        LotStock.objects.filter(entreprise_id=lot.entreprise_id, lot_transit_id=lot.id).aggregate(
            total=Sum('quantite_restante')
        ).get('total')
        or Decimal('0')
    )
    if remaining <= 0:
        lot.statut = LotTransit.Statut.CLOTURE
        lot.save(update_fields=['statut'])

