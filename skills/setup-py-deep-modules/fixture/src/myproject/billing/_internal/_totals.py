"""Totalling: the behaviour the package exists to provide."""

from ._invoice import Invoice
from ._money import apply_rate
from ._tax import rate_for


def total_due(invoice: Invoice) -> int:
    """Return what ``invoice`` costs, in cents, tax included."""
    subtotal = sum(item.unit_price_cents * item.quantity for item in invoice.items)
    return subtotal + apply_rate(subtotal, rate_for(invoice.jurisdiction))
