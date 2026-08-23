"""Money arithmetic in integer cents, to keep rounding decidable."""

from decimal import ROUND_HALF_UP, Decimal


def apply_rate(cents: int, rate: Decimal) -> int:
    """Return ``cents * rate``, rounded half-up to whole cents."""
    scaled = Decimal(cents) * rate
    return int(scaled.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_cents(cents: int) -> str:
    """Render ``cents`` as a plain decimal amount, e.g. ``"12.34"``."""
    return f"{cents // 100}.{cents % 100:02d}"
