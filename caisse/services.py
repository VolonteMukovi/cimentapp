from __future__ import annotations

from decimal import Decimal

from articles.currency import get_primary_currency_code, to_primary_amount
from caisse.models import MouvementCaisse


def signed_primary_amount(entreprise_id: int, mouvement: MouvementCaisse) -> Decimal:
    amount = to_primary_amount(entreprise_id, mouvement.montant, getattr(mouvement, 'devise', '') or None)
    if mouvement.type == MouvementCaisse.Type.SORTIE:
        return -amount
    return amount


def cash_balances_by_caisse(entreprise_id: int, caisse_id: int | None = None) -> dict[int, Decimal]:
    qs = MouvementCaisse.objects.filter(entreprise_id=entreprise_id)
    if caisse_id is not None:
        qs = qs.filter(caisse_id=caisse_id)
    balances: dict[int, Decimal] = {}
    for mouvement in qs.only('caisse_id', 'type', 'montant', 'devise'):
        cid = int(mouvement.caisse_id)
        balances[cid] = balances.get(cid, Decimal('0')) + signed_primary_amount(entreprise_id, mouvement)
    return balances


def serialize_recent_movements(entreprise_id: int, caisse_id: int, limit: int = 10) -> list[dict]:
    primary_code = get_primary_currency_code(entreprise_id)
    rows = MouvementCaisse.objects.filter(entreprise_id=entreprise_id, caisse_id=caisse_id).order_by(
        '-date_mouvement',
        '-id',
    )[:limit]
    results = []
    for row in rows:
        results.append(
            {
                'id': row.id,
                'type': row.type,
                'montant': str(row.montant),
                'devise': row.devise or primary_code,
                'montant_principal': str(to_primary_amount(entreprise_id, row.montant, row.devise)),
                'devise_principale': primary_code,
                'date_mouvement': row.date_mouvement.isoformat(),
                'libelle': row.libelle,
                'source_type': row.source_type,
                'source_id': row.source_id,
            }
        )
    return results
