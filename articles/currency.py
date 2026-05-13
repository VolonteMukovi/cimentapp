from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from articles.models import Devise


DEFAULT_CURRENCY_CODE = 'USD'
MONEY_QUANT = Decimal('0.01')


def normalize_currency_code(value: object | None) -> str:
    return str(value or '').strip().upper()[:10]


def get_primary_devise(entreprise_id: int | None) -> Devise | None:
    if entreprise_id is None:
        return None
    return (
        Devise.objects.filter(entreprise_id=entreprise_id, principale=True, actif=True).order_by('code').first()
        or Devise.objects.filter(entreprise_id=entreprise_id, actif=True).order_by('code').first()
    )


def get_primary_currency_code(entreprise_id: int | None) -> str:
    primary = get_primary_devise(entreprise_id)
    return primary.code if primary else DEFAULT_CURRENCY_CODE


def has_currency_configuration(entreprise_id: int | None) -> bool:
    if entreprise_id is None:
        return False
    return Devise.objects.filter(entreprise_id=entreprise_id, actif=True).exists()


def resolve_transaction_currency(entreprise_id: int | None, code: object | None = None) -> str:
    normalized = normalize_currency_code(code)
    primary_code = get_primary_currency_code(entreprise_id)
    if not normalized:
        return primary_code
    if not has_currency_configuration(entreprise_id):
        return normalized
    if Devise.objects.filter(entreprise_id=entreprise_id, code=normalized, actif=True).exists():
        return normalized
    raise ValueError(f'Devise non configuree: {normalized}.')


def get_rate_to_primary(entreprise_id: int | None, code: object | None = None) -> Decimal:
    currency_code = normalize_currency_code(code) or get_primary_currency_code(entreprise_id)
    primary_code = get_primary_currency_code(entreprise_id)
    if currency_code == primary_code:
        return Decimal('1')
    if not has_currency_configuration(entreprise_id):
        return Decimal('1')
    devise = Devise.objects.filter(entreprise_id=entreprise_id, code=currency_code, actif=True).first()
    if not devise:
        return Decimal('1')
    return devise.taux_vers_principale or Decimal('1')


def to_primary_amount(entreprise_id: int | None, amount: object, code: object | None = None) -> Decimal:
    try:
        value = Decimal(str(amount or '0'))
    except Exception:
        value = Decimal('0')
    rate = get_rate_to_primary(entreprise_id, code)
    return (value * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
