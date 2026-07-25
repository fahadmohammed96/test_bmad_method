"""Importi in centesimi di euro interi (`_cent`), mai float (spine Consistency)."""

from decimal import ROUND_HALF_UP, Decimal


def eur_to_cent(value: Decimal | str) -> int:
    """Converte un importo in euro in centesimi interi, half-up al centesimo."""
    if isinstance(value, float):
        raise TypeError("importi float vietati: usare Decimal o stringa decimale")
    amount = Decimal(value)
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
