"""Application code: a loose module at the root package level.

Modules sitting here are unconstrained themselves — no interface is required of
them — but they are still bound by every package's interface, so they reach
``billing`` and ``notifications`` through their public surfaces like anyone else.
"""

from myproject.billing import Invoice, LineItem
from myproject.notifications import invoice_ready


def demo() -> str:
    """Build a small invoice and return the notification for it."""
    invoice = Invoice(
        jurisdiction="FR",
        items=(LineItem(description="Consulting", unit_price_cents=25_000, quantity=3),),
    )
    return invoice_ready(invoice)
