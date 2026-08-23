"""Tax rates by jurisdiction."""

from decimal import Decimal

_RATES = {
    "FR": Decimal("0.20"),
    "UK": Decimal("0.20"),
    "US-CA": Decimal("0.0725"),
}

_DEFAULT_RATE = Decimal("0")


def rate_for(jurisdiction: str) -> Decimal:
    """Return the VAT/sales-tax rate for ``jurisdiction``, or zero if unknown."""
    return _RATES.get(jurisdiction, _DEFAULT_RATE)
